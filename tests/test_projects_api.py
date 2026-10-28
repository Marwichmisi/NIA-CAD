"""Créer, lister et rouvrir un projet local, puis le retrouver après redémarrage."""

from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app


def test_create_project_starts_as_brouillon_and_is_listed(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        created = client.post("/api/projects", json={"name": "  Capteur seuil  "})
        listed = client.get("/api/projects")

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Capteur seuil"
    assert body["status"] == "brouillon"
    assert body["status_changed_at"] == body["created_at"]
    assert listed.status_code == 200
    assert listed.json() == [body]


def test_reopen_returns_the_same_draft(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        created = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        opened = client.get(f"/api/projects/{created['id']}")

    assert opened.status_code == 200
    assert opened.json() == created


def test_missing_project_is_explained(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        missing = client.get("/api/projects/projet-absent")

    assert missing.status_code == 404
    assert missing.json()["detail"] == "Ce projet n'existe pas."


def test_blank_name_is_refused(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        refused = client.post("/api/projects", json={"name": "   "})

    assert refused.status_code == 422


def test_newest_project_is_listed_first(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        client.post("/api/projects", json={"name": "Carte une"})
        client.post("/api/projects", json={"name": "Carte deux"})
        names = [item["name"] for item in client.get("/api/projects").json()]

    assert names == ["Carte deux", "Carte une"]


def test_project_survives_restart_as_brouillon(tmp_path: Path) -> None:
    database = tmp_path / "nia.sqlite"
    with TestClient(create_app(database)) as client:
        created = client.post("/api/projects", json={"name": "Capteur seuil"}).json()

    with TestClient(create_app(database)) as client:
        opened = client.get(f"/api/projects/{created['id']}")
        listed = client.get("/api/projects")

    assert opened.status_code == 200
    assert opened.json() == created
    assert listed.json() == [created]


def test_project_response_exposes_only_the_public_fields(tmp_path: Path) -> None:
    schema = create_app(tmp_path / "nia.sqlite").openapi()["components"]["schemas"]
    assert set(schema["Project"]["properties"]) == {
        "id",
        "name",
        "status",
        "created_at",
        "status_changed_at",
    }
    assert schema["Project"]["properties"]["status"]["const"] == "brouillon"
