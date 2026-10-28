"""Lancer un job sans bloquer la requête, puis le suivre."""

import json
import threading
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from nia_pcb.app import create_app


def test_launch_returns_a_job_id_without_waiting_for_the_work(tmp_path: Path) -> None:
    release = threading.Event()

    def step(_context: object) -> None:
        release.wait()

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        try:
            launched = client.post(
                f"/api/projects/{project['id']}/jobs",
                json={"step": "fabrication", "inputs": {"couches": "2"}},
            )
        finally:
            release.set()

    assert launched.status_code == 202
    body = launched.json()
    assert body["id"]
    assert body["project_id"] == project["id"]
    assert body["step"] == "fabrication"
    assert body["status"] in {"en_attente", "en_cours"}


def test_journal_streams_live_and_stays_readable_by_polling(tmp_path: Path) -> None:
    started = threading.Event()
    continue_step = threading.Event()

    def step(context: Any) -> None:
        context.log("Première passe")
        context.progress(1, 2)
        started.set()
        continue_step.wait()
        context.log("Deuxième passe")
        context.progress(2, 2)

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        try:
            launched = client.post(
                f"/api/projects/{project['id']}/jobs",
                json={"step": "fabrication"},
            )
            assert launched.status_code == 202
            job_id = launched.json()["id"]
            assert started.wait(2)

            snapshot = client.get(f"/api/projects/{project['id']}/jobs/{job_id}")
            assert snapshot.status_code == 200
            assert snapshot.json()["journal"] == ["Première passe"]
            assert snapshot.json()["progress"] == {"done": 1, "total": 2}

            seen: dict[str, object] = {}

            def read_stream() -> None:
                with client.stream(
                    "GET",
                    f"/api/projects/{project['id']}/jobs/{job_id}/events",
                ) as response:
                    seen["status"] = response.status_code
                    chunks: list[str] = []
                    for chunk in response.iter_text():
                        chunks.append(chunk)
                        if _journal_messages("".join(chunks)) == ["Première passe"]:
                            seen["raw"] = "".join(chunks)
                            return

            reader = threading.Thread(target=read_stream)
            reader.start()
            reader.join(2)
            assert not reader.is_alive()
            assert seen["status"] == 200
            assert _journal_messages(str(seen["raw"])) == ["Première passe"]
        finally:
            continue_step.set()
            reader_cleanup = locals().get("reader")
            if isinstance(reader_cleanup, threading.Thread):
                reader_cleanup.join(2)

        deadline = time.monotonic() + 2
        finished = None
        while time.monotonic() < deadline:
            finished = client.get(f"/api/projects/{project['id']}/jobs/{job_id}").json()
            if finished["status"] == "termine":
                break
            time.sleep(0.02)

    assert finished is not None
    assert finished["status"] == "termine"
    assert finished["journal"] == ["Première passe", "Deuxième passe"]
    assert finished["progress"] == {"done": 2, "total": 2}


def _journal_messages(raw: str) -> list[str]:
    messages: list[str] = []
    for block in raw.split("\n\n"):
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if event == "journal" and isinstance(data, dict):
            messages.append(data["message"])
    return messages


def test_stop_then_resume_does_not_repeat_a_finished_effect(tmp_path: Path) -> None:
    effects: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    def step(context: Any) -> None:
        def releve() -> None:
            effects.append("releve")
            context.log("Relevé terminé")

        context.effect("releve", releve)
        entered.set()
        while not release.is_set():
            context.abort_if_requested()
            time.sleep(0.01)

        def route() -> None:
            effects.append("route")
            context.log("Routage terminé")

        context.effect("route", route)

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        launched = client.post(
            f"/api/projects/{project['id']}/jobs",
            json={"step": "fabrication"},
        )
        job_id = launched.json()["id"]
        assert entered.wait(2)

        stopped = client.post(f"/api/projects/{project['id']}/jobs/{job_id}/stop")
        release.set()

    assert stopped.status_code == 200
    assert stopped.json()["status"] == "arrete"
    assert stopped.json()["checkpoint"] == "releve"
    assert stopped.json()["journal"] == ["Relevé terminé"]
    assert effects == ["releve"]

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        resumed = client.post(
            f"/api/projects/{project['id']}/jobs/{job_id}/resume"
        )
        assert resumed.status_code == 200
        deadline = time.monotonic() + 2
        finished = resumed.json()
        while time.monotonic() < deadline:
            finished = client.get(
                f"/api/projects/{project['id']}/jobs/{job_id}"
            ).json()
            if finished["status"] == "termine":
                break
            time.sleep(0.02)

    assert finished["status"] == "termine"
    assert finished["checkpoint"] == "route"
    assert finished["journal"] == ["Relevé terminé", "Routage terminé"]
    assert effects == ["releve", "route"]


def test_restarted_worker_resumes_without_repeating_a_finished_effect(
    tmp_path: Path,
) -> None:
    effects: list[str] = []
    entered = threading.Event()
    release = threading.Event()

    def step(context: Any) -> None:
        context.effect("releve", lambda: effects.append("releve"))
        entered.set()
        while not release.is_set():
            context.abort_if_requested()
            time.sleep(0.01)
        context.effect("route", lambda: effects.append("route"))

    database = tmp_path / "nia.sqlite"
    with TestClient(create_app(database, steps={"fabrication": step})) as client:
        project = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        launched = client.post(
            f"/api/projects/{project['id']}/jobs",
            json={"step": "fabrication"},
        )
        job_id = launched.json()["id"]
        assert entered.wait(2)

    assert effects == ["releve"]

    release.set()
    with TestClient(create_app(database, steps={"fabrication": step})) as client:
        deadline = time.monotonic() + 2
        finished: dict[str, Any] = {}
        while time.monotonic() < deadline:
            finished = client.get(f"/api/projects/{project['id']}/jobs/{job_id}").json()
            if finished["status"] == "termine":
                break
            time.sleep(0.02)

    assert finished["status"] == "termine"
    assert finished["checkpoint"] == "route"
    assert effects == ["releve", "route"]


def test_a_failed_job_does_not_block_another_project(tmp_path: Path) -> None:
    release = threading.Event()
    started = threading.Event()

    def slow(_context: Any) -> None:
        started.set()
        release.wait()
        raise RuntimeError("Le routage a échoué.")

    def quick(context: Any) -> None:
        context.log("Carte prête")

    with TestClient(
        create_app(
            tmp_path / "nia.sqlite",
            steps={"lent": slow, "rapide": quick},
        )
    ) as client:
        first = client.post("/api/projects", json={"name": "Carte une"}).json()
        second = client.post("/api/projects", json={"name": "Carte deux"}).json()
        blocked = client.post(
            f"/api/projects/{first['id']}/jobs",
            json={"step": "lent"},
        ).json()
        assert started.wait(2)
        other = client.post(
            f"/api/projects/{second['id']}/jobs",
            json={"step": "rapide"},
        ).json()
        try:
            deadline = time.monotonic() + 2
            other_job: dict[str, Any] = {}
            while time.monotonic() < deadline:
                other_job = client.get(
                    f"/api/projects/{second['id']}/jobs/{other['id']}"
                ).json()
                if other_job["status"] == "termine":
                    break
                time.sleep(0.02)
            blocked_job = client.get(
                f"/api/projects/{first['id']}/jobs/{blocked['id']}"
            ).json()
            assert other_job["status"] == "termine"
            assert other_job["journal"] == ["Carte prête"]
            assert blocked_job["status"] == "en_cours"
        finally:
            release.set()

        deadline = time.monotonic() + 2
        failed: dict[str, Any] = {}
        while time.monotonic() < deadline:
            failed = client.get(
                f"/api/projects/{first['id']}/jobs/{blocked['id']}"
            ).json()
            if failed["status"] == "echec":
                break
            time.sleep(0.02)

    assert failed["status"] == "echec"
    assert failed["error"] == "Le routage a échoué."
    assert other_job["status"] == "termine"


def test_same_inputs_return_the_same_job_without_repeating_the_effect(
    tmp_path: Path,
) -> None:
    effects: list[str] = []

    def step(context: Any) -> None:
        context.effect("releve", lambda: effects.append("releve"))

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        body = {"step": "fabrication", "inputs": {"couches": "2"}}
        first = client.post(f"/api/projects/{project['id']}/jobs", json=body)
        assert first.status_code == 202
        job_id = first.json()["id"]
        deadline = time.monotonic() + 2
        finished: dict[str, Any] = {}
        while time.monotonic() < deadline:
            finished = client.get(f"/api/projects/{project['id']}/jobs/{job_id}").json()
            if finished["status"] == "termine":
                break
            time.sleep(0.02)
        again = client.post(f"/api/projects/{project['id']}/jobs", json=body)
        other = client.post(
            f"/api/projects/{project['id']}/jobs",
            json={"step": "fabrication", "inputs": {"couches": "4"}},
        )
        assert again.status_code == 202
        assert again.json()["id"] == job_id
        other_id = other.json()["id"]
        assert other_id != job_id
        while time.monotonic() < deadline + 2:
            other_job = client.get(
                f"/api/projects/{project['id']}/jobs/{other_id}"
            ).json()
            if other_job["status"] == "termine":
                break
            time.sleep(0.02)

    assert finished["status"] == "termine"
    assert effects == ["releve", "releve"]


def test_latest_job_is_the_one_the_interface_follows(tmp_path: Path) -> None:
    def step(context: Any) -> None:
        context.log("fait")

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "Capteur seuil"}).json()
        missing = client.get(f"/api/projects/{project['id']}/jobs/latest")
        created = client.post(
            f"/api/projects/{project['id']}/jobs",
            json={"step": "fabrication", "inputs": {"couches": "2"}},
        ).json()
        latest = client.get(f"/api/projects/{project['id']}/jobs/latest")

    assert missing.status_code == 404
    assert missing.json()["detail"] == "Ce projet n'a pas de job."
    assert latest.status_code == 200
    assert latest.json()["id"] == created["id"]


