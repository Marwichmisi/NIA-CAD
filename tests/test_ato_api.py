"""Projet atopile initial qui se construit (ticket #19, spec #13).

Couture API : lecture/écriture du .ato, versions locales,
job construire (BOM/layout ou échec expliqué + journal),
garde-fou aucune écriture hors dossier projet.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app


class FakeBuilder:
    """Double déterministe de `ato build --target rapide`."""

    def __init__(self, bom=None, layout_updated=True):
        self._bom = bom if bom is not None else [
            {"reference": "R1", "lcsc": "C25804", "quantite": 1},
            {"reference": "C1", "lcsc": "C15905", "quantite": 1},
        ]
        self._layout_updated = layout_updated
        self.calls: list[str] = []

    def build(self, project_dir: Path):
        self.calls.append(str(project_dir))
        code = (project_dir / "main.ato").read_text(encoding="utf-8")
        assert "module" in code
        return {"bom": self._bom, "layout_updated": self._layout_updated}


def _wait(client: TestClient, project_id: str, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/projects/{project_id}/jobs/{job_id}").json()
        if last["status"] in {"termine", "echec"}:
            return last
        time.sleep(0.02)
    return last


def test_ato_vide_puis_ecriture_puis_relecture_et_version(tmp_path: Path) -> None:
    builder = FakeBuilder()
    with TestClient(create_app(tmp_path / "nia.sqlite", ato_builder=builder)) as client:
        project = client.post("/api/projects", json={"name": "Capteur"}).json()
        pid = project["id"]

        vide = client.get(f"/api/projects/{pid}/ato")
        assert vide.status_code == 200
        assert vide.json()["existe"] is False

        code = (
            '#pragma experiment("BRIDGE_CONNECT")\n'
            "import ElectricPower\n"
            "import Resistor\n"
            "import Capacitor\n"
            "module Top:\n"
            "    power = new ElectricPower\n"
            "    assert power.voltage within 3.3V +/- 5%\n"
        )
        ecrit = client.put(f"/api/projects/{pid}/ato", json={"code": code})
        assert ecrit.status_code == 200
        assert ecrit.json()["version"] == 1

        relu = client.get(f"/api/projects/{pid}/ato")
        assert relu.status_code == 200
        assert relu.json()["code"] == code
        assert relu.json()["version"] == 1

        versions = client.get(f"/api/projects/{pid}/ato/versions")
        assert versions.status_code == 200
        assert len(versions.json()["versions"]) == 1

        # La première version est enregistrée localement.
        assert (tmp_path / "projects" / pid / "main.ato").is_file()


def test_ecriture_hors_dossier_projet_refusee(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        project = client.post("/api/projects", json={"name": "Capteur"}).json()
        pid = project["id"]

        tentative = client.put(
            f"/api/projects/{pid}/ato/fichier",
            json={"chemin": "../echappe.ato", "code": "module X:\n    pass\n"},
        )
        assert tentative.status_code == 422
        assert not (tmp_path / "echappe.ato").exists()


def test_construire_produit_bom_et_layout_avec_journal(tmp_path: Path) -> None:
    builder = FakeBuilder()
    with TestClient(create_app(tmp_path / "nia.sqlite", ato_builder=builder)) as client:
        project = client.post("/api/projects", json={"name": "Capteur"}).json()
        pid = project["id"]

        code = (
            '#pragma experiment("BRIDGE_CONNECT")\n'
            "import ElectricPower\n"
            "import Resistor\n"
            "module Top:\n"
            "    power = new ElectricPower\n"
            "    assert power.voltage within 3.3V +/- 5%\n"
        )
        client.put(f"/api/projects/{pid}/ato", json={"code": code})

        lance = client.post(f"/api/projects/{pid}/ato/construire")
        assert lance.status_code == 202
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "termine"
        assert job["journal"], "le journal de construction reste visible"
        assert job["result"]["layout_updated"] is True

        bom = client.get(f"/api/projects/{pid}/ato/bom")
        assert bom.status_code == 200
        assert len(bom.json()["entrees"]) == 2

        layout = client.get(f"/api/projects/{pid}/ato")
        assert layout.json()["layout_a_jour"] is True


def test_construire_explique_echec_en_francais(tmp_path: Path) -> None:
    class EchecBuilder:
        def build(self, project_dir: Path):
            raise RuntimeError("empreinte introuvable pour U1")

    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=EchecBuilder())
    ) as client:
        project = client.post("/api/projects", json={"name": "Capteur"}).json()
        pid = project["id"]
        client.put(
            f"/api/projects/{pid}/ato",
            json={"code": "module Top:\n    pass\n"},
        )
        lance = client.post(f"/api/projects/{pid}/ato/construire")
        job = _wait(client, pid, lance.json()["id"])

        assert job["status"] == "echec"
        assert "empreinte" in job["error"]
