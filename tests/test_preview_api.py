"""Aperçu 2D/3D lié au projet et à sa version (ticket #22, spec #13).

Couture API : lecture de l'aperçu vide, génération via job (SVG couches +
GLB + sans-modèle-3D), lecture liée à la version courante, garde-fou projet
inexistant.
"""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app


class FauxGenerateur:
    """Double déterministe de la chaîne KiCad (SVG + GLB)."""

    def __init__(self):
        self.appels: list[str] = []

    def build(self, project_dir: Path):
        self.appels.append(str(project_dir))
        prefix = '<svg xmlns="http://www.w3.org/2000/svg">'
        couches = {
            "F.Cu": f"{prefix}<rect width='10' height='10'/></svg>",
            "B.Cu": f"{prefix}<circle r='5'/></svg>",
            "F.SilkS": f"{prefix}<text>TOP</text></svg>",
            "Edge.Cuts": f"{prefix}<rect width='20' height='20'/></svg>",
        }
        return {
            "couches": couches,
            "glb": b"GLB-faux",
            "pieces_sans_modele_3d": ["U1"],
        }


def _attendre(client: TestClient, project_id: str, job_id: str) -> dict:
    echeance = time.monotonic() + 5
    dernier: dict = {}
    while time.monotonic() < echeance:
        dernier = client.get(f"/api/projects/{project_id}/jobs/{job_id}").json()
        if dernier["status"] in {"termine", "echec"}:
            return dernier
        time.sleep(0.02)
    return dernier


def test_apercu_vide_puis_genere_lie_a_version(tmp_path: Path) -> None:
    generateur = FauxGenerateur()
    with TestClient(
        create_app(tmp_path / "nia.sqlite", preview_builder=generateur)
    ) as client:
        projet = client.post("/api/projects", json={"name": "Capteur"}).json()
        pid = projet["id"]

        code = (
            '#pragma experiment("BRIDGE_CONNECT")\n'
            "module Top:\n"
            "    pass\n"
        )
        client.put(f"/api/projects/{pid}/ato", json={"code": code})

        vide = client.get(f"/api/projects/{pid}/apercu")
        assert vide.status_code == 200
        assert vide.json()["couches"] == []
        assert vide.json()["modele_3d_disponible"] is False
        assert vide.json()["version"] == 0
        assert vide.json()["version_courante"] == 1
        assert vide.json()["a_jour"] is False

        lance = client.post(f"/api/projects/{pid}/apercu/generer")
        assert lance.status_code == 202
        job = _attendre(client, pid, lance.json()["id"])
        assert job["status"] == "termine"

        apercu = client.get(f"/api/projects/{pid}/apercu")
        assert apercu.status_code == 200
        corps = apercu.json()
        assert corps["version"] == 1
        assert {c["id"] for c in corps["couches"]} == {
            "F.Cu",
            "B.Cu",
            "F.SilkS",
            "Edge.Cuts",
        }
        assert corps["modele_3d_disponible"] is True
        assert corps["pieces_sans_modele_3d"] == ["U1"]

        modele = client.get(f"/api/projects/{pid}/apercu/modele")
        assert modele.status_code == 200
        assert modele.content == b"GLB-faux"

        # Nouvelle version .ato : l'aperçu reste lié à l'ancienne version.
        client.put(f"/api/projects/{pid}/ato", json={"code": code + "\n"})
        apercu2 = client.get(f"/api/projects/{pid}/apercu").json()
        assert apercu2["version"] == 1
        assert apercu2["version_courante"] == 2
        assert apercu2["a_jour"] is False


def test_apercu_projet_inexistant_404(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        reponse = client.get("/api/projects/inconnu/apercu")
        assert reponse.status_code == 404
