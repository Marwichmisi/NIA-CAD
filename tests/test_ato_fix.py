"""Boucle contrôlée de correction atopile (ticket #20, spec #13).

Couture API : job corriger qui réessaie build + fix jusqu'au succès
ou arrêt propre (plafond, budget, arrêt manuel, irrécupérable).
Chaque modification crée une version retrouvable, le journal montre
les diffs, le rapport final est en français.
Seam DRC : extra_checks optionnel, point d'extension pour ticket #24.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app


class FakeBuilder:
    def __init__(self, bom=None, fail_first: str | None = None, always_fail: str = ""):
        self._bom = bom if bom is not None else [{"reference": "R1", "quantite": 1}]
        self._fail_first = fail_first
        self._always_fail = always_fail
        self.calls = 0

    def build(self, project_dir: Path):
        self.calls += 1
        if self._always_fail:
            raise RuntimeError(self._always_fail)
        if self._fail_first is not None and self.calls == 1:
            raise RuntimeError(self._fail_first)
        return {"bom": self._bom, "layout_updated": True}


class FakeFixer:
    def __init__(self, fixed_code: str, unrecoverable: str | None = None):
        self._fixed_code = fixed_code
        self._unrecoverable = unrecoverable
        self.calls: list[dict] = []

    def propose_fix(self, code: str, erreur: str, tentative: int) -> str:
        from nia_pcb.ato_fix import AtoUnrecoverable

        self.calls.append({"code": code, "erreur": erreur, "tentative": tentative})
        if self._unrecoverable is not None:
            raise AtoUnrecoverable(self._unrecoverable)
        # Retourne un code légèrement différent à chaque tentative.
        if tentative > 1:
            return self._fixed_code + f"\n# fix tentative {tentative}\n"
        return self._fixed_code


FIXED = (
    '#pragma experiment("BRIDGE_CONNECT")\n'
    "import ElectricPower\n"
    "import Resistor\n"
    "module Top:\n"
    "    power = new ElectricPower\n"
    "    assert power.voltage within 3.3V +/- 5%\n"
)

BROKEN = "module Top:\n    pass\n"


def _wait(client: TestClient, pid: str, jid: str, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/projects/{pid}/jobs/{jid}").json()
        if last["status"] in {"termine", "echec", "arrete"}:
            return last
        time.sleep(0.02)
    return last


def _project_with_code(client: TestClient, code: str) -> str:
    project = client.post("/api/projects", json={"name": "Capteur"}).json()
    pid = project["id"]
    put = client.put(f"/api/projects/{pid}/ato", json={"code": code})
    assert put.status_code == 200, put.text
    return pid


def test_corriger_succes_apres_une_correction_avec_diff_et_version(
    tmp_path: Path,
) -> None:
    builder = FakeBuilder(fail_first="empreinte introuvable pour U1")
    fixer = FakeFixer(FIXED)
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=builder, ato_fixer=fixer)
    ) as client:
        pid = _project_with_code(client, BROKEN)
        lance = client.post(f"/api/projects/{pid}/ato/corriger", json={})
        assert lance.status_code == 202, lance.text
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "termine", job
        journal = "\n".join(job["journal"])
        assert "Tentative" in journal
        assert "@@" in journal or "diff" in journal.lower() or "---" in journal
        versions = client.get(f"/api/projects/{pid}/ato/versions").json()
        # 1 version initiale (write) + au moins 1 correction = 2 versions.
        assert len(versions["versions"]) >= 2, versions
        bom = client.get(f"/api/projects/{pid}/ato/bom").json()
        assert len(bom["entrees"]) == 1


def test_corriger_plafond_configurable_stoppe_proprement_en_francais(
    tmp_path: Path,
) -> None:
    builder = FakeBuilder(always_fail="empreinte introuvable pour U1")
    fixer = FakeFixer(FIXED)
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=builder, ato_fixer=fixer)
    ) as client:
        pid = _project_with_code(client, BROKEN)
        lance = client.post(
            f"/api/projects/{pid}/ato/corriger", json={"max_iterations": 2}
        )
        assert lance.status_code == 202, lance.text
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "echec", job
        assert "2" in (job["error"] or ""), job["error"]
        assert "tentative" in (job["error"] or "").lower(), job["error"]
        assert builder.calls == 2, builder.calls
        assert len(fixer.calls) == 1


def test_corriger_budget_stoppe_proprement(tmp_path: Path) -> None:
    builder = FakeBuilder(always_fail="empreinte introuvable")
    fixer = FakeFixer(FIXED)
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=builder, ato_fixer=fixer)
    ) as client:
        pid = _project_with_code(client, BROKEN)
        client.put(
            "/api/settings",
            json={
                "llm_model": "m",
                "llm_base_url": "https://api.example.test/v1",
                "ato_max_iterations": 30,
                "routing_max_passes": 15,
                "retention_builds_days": 30,
                "retention_abandoned_days": 90,
                "project_token_budget": 100,
                "project_cost_budget_eur": 10.0,
            },
        )
        client.post(f"/api/projects/{pid}/costs", json={"tokens": 120, "cost_eur": 0.1})
        lance = client.post(f"/api/projects/{pid}/ato/corriger", json={})
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "echec", job
        assert "Budget" in (job["error"] or ""), job


def test_corriger_erreur_irrecuperable_expliquee_en_francais(tmp_path: Path) -> None:
    builder = FakeBuilder(always_fail="empreinte introuvable pour U1")
    fixer = FakeFixer(FIXED, unrecoverable="bibliothèque introuvable, abandon")
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=builder, ato_fixer=fixer)
    ) as client:
        pid = _project_with_code(client, BROKEN)
        lance = client.post(f"/api/projects/{pid}/ato/corriger", json={})
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "echec", job
        assert (
            "bibliothèque" in (job["error"] or "").lower()
            or "irrécupérable" in (job["error"] or "").lower()
        ), job["error"]


def test_corriger_mode_valide_affiche_diff_avant_application(tmp_path: Path) -> None:
    builder = FakeBuilder(fail_first="empreinte introuvable pour U1")
    fixer = FakeFixer(FIXED)
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=builder, ato_fixer=fixer)
    ) as client:
        pid = _project_with_code(client, BROKEN)
        lance = client.post(
            f"/api/projects/{pid}/ato/corriger", json={"mode": "valide"}
        )
        assert lance.status_code == 202, lance.text
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "termine", job
        journal = "\n".join(job["journal"])
        # En mode validé, la proposition est annoncée avant application.
        assert "Proposition" in journal or "proposition" in journal


def test_seam_drc_extra_check_rejette_puis_accepte(tmp_path: Path) -> None:
    """Le seam DRC (ticket #24) peut brancher un contrôle après le build."""
    from nia_pcb.ato_fix import make_ato_fix_step
    from nia_pcb.ato_project import AtoStore, projects_base_dir
    from nia_pcb.jobs import JobContext, JobStore
    from nia_pcb.projects import ProjectStore

    db = tmp_path / "nia.sqlite"
    store = ProjectStore(db)
    project = store.create("Capteur")
    ato = AtoStore(store.engine, projects_base_dir(db))
    ato.write(project.id, BROKEN, "initial")

    builder = FakeBuilder()
    fixer = FakeFixer(FIXED)
    calls = {"n": 0}

    def drc_check(_project_dir: Path) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("court-circuit détecté entre 3V3 et GND")

    step = make_ato_fix_step(
        ato, builder, fixer, engine=store.engine, extra_checks=[drc_check]
    )
    jobs = JobStore(store.engine)
    record = jobs.create(project.id, "corriger", {})
    # Marque en cours pour que abort_if_requested ne bloque pas.
    from sqlmodel import Session

    from nia_pcb.jobs import JobRecord

    with Session(store.engine) as session:
        row = session.get(JobRecord, record.id)
        assert row is not None
        row.status = "en_cours"
        session.add(row)
        session.commit()

    import threading

    context = JobContext(jobs, record.id, {}, threading.Event(), project.id)
    step(context)
    assert calls["n"] == 2
    assert len(fixer.calls) >= 1
