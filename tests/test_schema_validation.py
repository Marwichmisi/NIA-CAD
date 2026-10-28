"""Valider le schéma et débloquer le statut schéma validé (ticket #21, spec #13).

Couture API : vérification (job valider_schema), lecture validation,
bouton Valider manuel, transition datée, blocage si rouge.
Couture domaine : checklist 8 contrôles, marge régulateur 30 %.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app

CODE_VERT = """#pragma experiment("BRIDGE_CONNECT")
import ElectricPower
import Resistor
import Capacitor
import Regulator
import Fuse
module Top:
    power_3v3 = new ElectricPower
    assert power_3v3.voltage within 3.3V +/- 5%
    decoup_100n = new Capacitor
    decoup_100n.capacitance = 100nF +/- 20%
    pull_10k = new Resistor
    pull_10k.resistance = 10kohm +/- 5%
    boot_cfg = new Resistor
    rst_line = new ElectricLogic
    # demarrage boot EN enable
    # reset NRST
    # protection TVS ESD Fuse diode
    # Regulator marge 30% margin
    reg = new Regulator
"""

CODE_ROUGE = "module Top:\n    pass\n"


def _wait(client: TestClient, pid: str, jid: str, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/projects/{pid}/jobs/{jid}").json()
        if last["status"] in {"termine", "echec", "arrete"}:
            return last
        time.sleep(0.02)
    return last


def _project_id(client: TestClient) -> str:
    return client.post("/api/projects", json={"name": "Capteur"}).json()["id"]


class _OkBuilder:
    def build(self, project_dir: Path):
        return {"bom": [{"reference": "R1"}], "layout_updated": True}


class _KoBuilder:
    def build(self, project_dir: Path):
        raise RuntimeError("solveur : contrainte violée sur 3V3")


def test_verifier_tout_vert_en_autonome_bascule_en_schema_valide_date(
    tmp_path: Path,
) -> None:
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=_OkBuilder())
    ) as client:
        pid = _project_id(client)
        avant = client.get(f"/api/projects/{pid}").json()
        assert avant["status"] == "brouillon"
        client.put(f"/api/projects/{pid}/ato", json={"code": CODE_VERT})
        lance = client.post(
            f"/api/projects/{pid}/schema/verifier", json={"mode": "autonome"}
        )
        assert lance.status_code == 202, lance.text
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "termine", job
        assert job["result"]["vert"] is True
        validation = client.get(f"/api/projects/{pid}/schema").json()
        assert validation["vert"] is True
        assert len(validation["controles"]) == 8
        apres = client.get(f"/api/projects/{pid}").json()
        assert apres["status"] == "schema_valide"
        assert apres["status_changed_at"] >= avant["status_changed_at"]
        assert apres["status_changed_at"] >= apres["created_at"]


def test_rouge_empeche_le_passage_silencieux(tmp_path: Path) -> None:
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=_KoBuilder())
    ) as client:
        pid = _project_id(client)
        client.put(f"/api/projects/{pid}/ato", json={"code": CODE_ROUGE})
        lance = client.post(
            f"/api/projects/{pid}/schema/verifier", json={"mode": "autonome"}
        )
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "termine", job
        assert job["result"]["vert"] is False
        validation = client.get(f"/api/projects/{pid}/schema").json()
        assert validation["vert"] is False
        assert any(c["statut"] == "rouge" for c in validation["controles"])
        projet = client.get(f"/api/projects/{pid}").json()
        assert projet["status"] == "brouillon"
        # Le bouton Valider refuse aussi.
        refuse = client.post(f"/api/projects/{pid}/schema/valider")
        assert refuse.status_code == 409, refuse.text


def test_mode_valide_exige_le_bouton_valider(tmp_path: Path) -> None:
    with TestClient(
        create_app(tmp_path / "nia.sqlite", ato_builder=_OkBuilder())
    ) as client:
        pid = _project_id(client)
        client.put(f"/api/projects/{pid}/ato", json={"code": CODE_VERT})
        lance = client.post(
            f"/api/projects/{pid}/schema/verifier", json={"mode": "valide"}
        )
        job = _wait(client, pid, lance.json()["id"])
        assert job["status"] == "termine", job
        assert job["result"]["vert"] is True
        # Pas de bascule automatique en mode validé.
        assert client.get(f"/api/projects/{pid}").json()["status"] == "brouillon"
        valide = client.post(f"/api/projects/{pid}/schema/valider")
        assert valide.status_code == 200, valide.text
        assert valide.json()["status"] == "schema_valide"
        hist = client.get(f"/api/projects/{pid}/statuts").json()
        statuts = [t["status"] for t in hist["transitions"]]
        assert statuts == ["brouillon", "schema_valide"]
        assert all("changed_at" in t for t in hist["transitions"])


def test_checklist_couvre_les_huit_controles(tmp_path: Path) -> None:
    from nia_pcb.schematic import CHECK_IDS

    assert set(CHECK_IDS) == {
        "decouplage",
        "pull_ups",
        "demarrage",
        "reset",
        "protections",
        "marge_regulateurs",
        "solveur",
        "erc",
    }


def test_code_complet_est_vert_et_bloque_sans_rouge_silencieux(
    tmp_path: Path,
) -> None:
    from nia_pcb.schematic import evaluate_code

    controles = evaluate_code(CODE_VERT, build_ok=True)
    par_id = {c.id: c for c in controles}
    assert all(c.statut == "vert" for c in controles), par_id
    # Marge régulateur : limite explicite 30 %.
    assert "30" in par_id["marge_regulateurs"].limite

    rouges = evaluate_code(CODE_ROUGE, build_ok=False)
    assert any(c.statut == "rouge" for c in rouges)
