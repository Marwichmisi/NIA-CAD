"""Couture API pièces : recherche via job, lecture, validation (ticket #18)."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app
from nia_pcb.parts import PartCandidate
from nia_pcb.parts_catalog import InMemoryCatalog


def _catalog() -> InMemoryCatalog:
    return InMemoryCatalog(
        {
            "100nF": [
                PartCandidate(
                    lcsc="C100a",
                    mpn="CL10B104KB8NNNC",
                    manufacturer="Samsung",
                    description="100nF 50V",
                    is_basic=True,
                    stock=500,
                    datasheet_url="https://exemple.test/c100a.pdf",
                    footprint="C_0603_1608Metric",
                    has_3d=True,
                ),
                PartCandidate(
                    lcsc="C100b",
                    mpn="CL10B104KB8NNNC-ALT",
                    manufacturer="Samsung",
                    description="100nF 50V alt",
                    is_basic=True,
                    stock=400,
                    datasheet_url="https://exemple.test/c100b.pdf",
                    footprint="C_0603_1608Metric",
                    has_3d=True,
                ),
            ],
            "ESP32": [
                PartCandidate(
                    lcsc="CESP1",
                    mpn="ESP32-WROOM-32",
                    manufacturer="Espressif",
                    description="module WiFi",
                    is_basic=False,
                    stock=200,
                    datasheet_url="https://exemple.test/esp.pdf",
                    footprint="Module-ESP32",
                    has_3d=True,
                ),
                PartCandidate(
                    lcsc="CESP2",
                    mpn="ESP32-WROOM-32E",
                    manufacturer="Espressif",
                    description="module WiFi alt",
                    is_basic=False,
                    stock=150,
                    datasheet_url="https://exemple.test/esp2.pdf",
                    footprint="Module-ESP32",
                    has_3d=True,
                ),
            ],
            "10k": [
                PartCandidate(
                    lcsc="C10k",
                    mpn="RC0603-10K",
                    manufacturer="Yageo",
                    description="10k",
                    is_basic=True,
                    stock=2,
                    datasheet_url="https://exemple.test/10k.pdf",
                    footprint="R_0603_1608Metric",
                    has_3d=True,
                ),
            ],
        }
    )


def _wait(client: TestClient, project_id: str, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    last: dict = {}
    while time.monotonic() < deadline:
        last = client.get(f"/api/projects/{project_id}/jobs/{job_id}").json()
        if last["status"] in {"termine", "echec"}:
            return last
        time.sleep(0.02)
    return last


def test_recherche_liste_choisit_rejette_puis_valide(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite", catalog=_catalog())) as client:
        project = client.post("/api/projects", json={"name": "Capteur"}).json()
        pid = project["id"]

        launched = client.post(
            f"/api/projects/{pid}/pieces/rechercher",
            json={
                "exigences": [
                    {
                        "reference": "C1",
                        "quantity": 2,
                        "critical": False,
                        "query": "100nF",
                    },
                    {
                        "reference": "U1",
                        "quantity": 1,
                        "critical": True,
                        "query": "ESP32",
                    },
                    {
                        "reference": "R1",
                        "quantity": 10,
                        "critical": False,
                        "query": "10k",
                    },
                ]
            },
        )
        assert launched.status_code == 202
        job = _wait(client, pid, launched.json()["id"])
        assert job["status"] == "termine"

        vue = client.get(f"/api/projects/{pid}/pieces")
        assert vue.status_code == 200
        body = vue.json()
        assert body["validee"] is False
        choisis = {c["reference"]: c for c in body["choisies"]}
        rejetees = {r["reference"]: r for r in body["rejetees"]}
        assert choisis["C1"]["part"]["lcsc"] == "C100a"
        assert choisis["U1"]["alternative"]["lcsc"] == "CESP2"
        assert "R1" in rejetees
        assert rejetees["R1"]["raison"]

        valide = client.post(f"/api/projects/{pid}/pieces/valider")
        assert valide.status_code == 200
        assert valide.json()["validee"] is True
        relue = client.get(f"/api/projects/{pid}/pieces").json()
        assert relue["validee"] is True
