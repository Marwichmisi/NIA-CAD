"""Réglages synchronisés, reset usine, secrets masqués, budget avec alerte et garde."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from nia_pcb.app import create_app


def test_settings_sync_and_reset_to_factory(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        initial = client.get("/api/settings")
        assert initial.status_code == 200
        body = initial.json()
        assert body["ato_max_iterations"] == 30
        assert body["routing_max_passes"] == 15

        updated = client.put(
            "/api/settings",
            json={
                "llm_model": "modele-test",
                "llm_base_url": "https://api.example.test/v1",
                "ato_max_iterations": 12,
                "routing_max_passes": 5,
                "retention_builds_days": 10,
                "retention_abandoned_days": 20,
                "project_token_budget": 1000,
                "project_cost_budget_eur": 2.5,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["ato_max_iterations"] == 12

        reread = client.get("/api/settings")
        assert reread.json()["ato_max_iterations"] == 12
        assert reread.json()["llm_model"] == "modele-test"

        reset = client.post("/api/settings/reset")
        assert reset.status_code == 200
        assert reset.json()["ato_max_iterations"] == 30
        assert reset.json()["routing_max_passes"] == 15

        after_reset = client.get("/api/settings")
        assert after_reset.json()["ato_max_iterations"] == 30


def test_settings_never_expose_secrets(
    tmp_path: Path, monkeypatch  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-ultra-secret-12345")
    monkeypatch.setenv("JLCPCB_API_KEY", "jlc-test-ultra-secret-67890")
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        body = client.get("/api/settings").json()
        dumped = str(body)
        assert "sk-test-ultra-secret-12345" not in dumped
        assert "jlc-test-ultra-secret-67890" not in dumped
        assert body["has_llm_key"] is True
        assert body["has_jlcpcb_key"] is True
        assert "api_key" not in dumped.lower() or "has_" in dumped.lower()
        # Aucune valeur secrète dans les clés du payload
        for value in body.values():
            assert value != "sk-test-ultra-secret-12345"
            assert value != "jlc-test-ultra-secret-67890"


def test_journal_redacts_secrets(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    secret = "sk-journal-secret-99999"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    def step(context):  # type: ignore[no-untyped-def]
        context.log(f"appel avec {secret} dedans")

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "P"}).json()
        launched = client.post(
            f"/api/projects/{project['id']}/jobs",
            json={"step": "fabrication"},
        )
        job_id = launched.json()["id"]
        finished = _wait(client, project["id"], job_id)
        assert finished["status"] == "termine"
        assert secret not in str(finished["journal"])
        assert "***" in str(finished["journal"])


def test_costs_alert_at_80_percent_and_block_at_ceiling(tmp_path: Path) -> None:
    def step(context):  # type: ignore[no-untyped-def]
        context.log("ok")

    with TestClient(
        create_app(tmp_path / "nia.sqlite", steps={"fabrication": step})
    ) as client:
        project = client.post("/api/projects", json={"name": "P"}).json()
        pid = project["id"]
        client.put(
            "/api/settings",
            json={
                "llm_model": "m",
                "llm_base_url": "https://api.example.test/v1",
                "ato_max_iterations": 30,
                "routing_max_passes": 15,
                "retention_builds_days": 30,
                "retention_abandoned_days": 90,
                "project_token_budget": 1000,
                "project_cost_budget_eur": 10.0,
            },
        )
        # 850 tokens = 85 % -> alerte sans blocage
        recorded = client.post(
            f"/api/projects/{pid}/costs", json={"tokens": 850, "cost_eur": 1.0}
        )
        assert recorded.status_code == 201
        summary = client.get(f"/api/projects/{pid}/costs").json()
        assert summary["project_tokens"] == 850
        assert summary["alert_80"] is True
        assert summary["over_budget"] is False

        allowed = client.post(
            f"/api/projects/{pid}/jobs",
            json={"step": "fabrication", "inputs": {"run": "1"}},
        )
        assert _wait(client, pid, allowed.json()["id"])["status"] == "termine"

        # Dépassement du plafond tokens
        client.post(f"/api/projects/{pid}/costs", json={"tokens": 200, "cost_eur": 0.5})
        over = client.get(f"/api/projects/{pid}/costs").json()
        assert over["project_tokens"] == 1050
        assert over["over_budget"] is True

        blocked = client.post(
            f"/api/projects/{pid}/jobs",
            json={"step": "fabrication", "inputs": {"run": "2"}},
        )
        blocked_job = _wait(client, pid, blocked.json()["id"])
        assert blocked_job["status"] == "echec"
        assert "Budget" in (blocked_job["error"] or "")

        # Dépassement manuel explicite et journalisé
        forced = client.post(
            f"/api/projects/{pid}/jobs",
            json={
                "step": "fabrication",
                "inputs": {"run": "3", "allow_over_budget": "true"},
            },
        )
        forced_job = _wait(client, pid, forced.json()["id"])
        assert forced_job["status"] == "termine"
        assert any(
            "autorisé" in message for message in forced_job["journal"]
        ), forced_job["journal"]


def test_costs_cumul_across_projects(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        first = client.post("/api/projects", json={"name": "Une"}).json()
        second = client.post("/api/projects", json={"name": "Deux"}).json()
        client.post(
            f"/api/projects/{first['id']}/costs", json={"tokens": 100, "cost_eur": 1.0}
        )
        client.post(
            f"/api/projects/{second['id']}/costs", json={"tokens": 50, "cost_eur": 0.5}
        )
        first_summary = client.get(f"/api/projects/{first['id']}/costs").json()
        assert first_summary["project_tokens"] == 100
        assert first_summary["total_tokens"] == 150
        assert first_summary["total_cost"] == 1.5


def _wait(client: TestClient, project_id: str, job_id: str):  # type: ignore[no-untyped-def]
    last = {}
    for _ in range(100):
        last = client.get(f"/api/projects/{project_id}/jobs/{job_id}").json()
        if last["status"] in {"termine", "echec", "arrete"}:
            return last
        time.sleep(0.02)
    raise AssertionError(last)
