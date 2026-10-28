"""Transformer une demande en spécification retrouvable, avant toute conception."""

import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from nia_pcb.app import create_app

CAPTEUR = {
    "decision": "specification",
    "name": "Capteur seuil",
    "blocks": [{"name": "Microcontrôleur", "role": "Lit le capteur et décide"}],
    "rails": [{"name": "3V3", "voltage_v": 3.3, "current_a": 0.2}],
    "interfaces": ["I2C"],
    "dimensions": {"max_width_mm": 50, "max_height_mm": 30},
    "layers": 2,
    "budget": {"max_amount": 15, "currency": "EUR"},
    "assumptions": ["Alimentation USB 5 V ramenée en 3,3 V"],
}

DEMANDE = "Carte ESP32, capteur I2C, USB, 50x30 mm, 2 couches, 15 euros."


class ScriptedModel:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.replies:
            raise RuntimeError("aucune réponse scriptée")
        return self.replies.pop(0)


def test_autonomous_demand_becomes_a_spec_with_assumptions_and_no_questions(
    tmp_path: Path,
) -> None:
    model = ScriptedModel([json.dumps(CAPTEUR)])
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project = client.post("/api/projects", json={"name": "Brouillon"}).json()
        launched = client.post(
            f"/api/projects/{project['id']}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        assert launched.status_code == 202
        job = _wait(client, project["id"], launched.json()["id"])
        spec = client.get(f"/api/projects/{project['id']}/specification")
        conversation = client.get(f"/api/projects/{project['id']}/conversation")

    assert job["status"] == "termine"
    assert spec.status_code == 200
    assert spec.json() == {
        "state": "prete",
        "specification": {
            "name": "Capteur seuil",
            "blocks": [{"name": "Microcontrôleur", "role": "Lit le capteur et décide"}],
            "rails": [{"name": "3V3", "voltage_v": 3.3, "current_a": 0.2}],
            "interfaces": ["I2C"],
            "dimensions": {"max_width_mm": 50, "max_height_mm": 30},
            "layers": 2,
            "budget": {"max_amount": 15, "currency": "EUR"},
            "mode": "autonome",
            "assumptions": ["Alimentation USB 5 V ramenée en 3,3 V"],
        },
    }
    assert conversation.json()["messages"] == [
        {"role": "maker", "content": DEMANDE},
        {
            "role": "agent",
            "content": (
                "Spécification prête.\n"
                "Hypothèses :\n"
                "- Alimentation USB 5 V ramenée en 3,3 V"
            ),
        },
    ]
    assert "autonome" in model.prompts[0]
    assert DEMANDE in model.prompts[0]
    assert "?" not in conversation.json()["messages"][1]["content"]


def test_out_of_scope_demand_is_refused_with_an_explanation(tmp_path: Path) -> None:
    explanation = (
        "La v1 ne prend pas en charge le HDMI : c'est une liaison haute vitesse."
    )
    model = ScriptedModel(
        [json.dumps({"decision": "refus", "explication": explanation})]
    )
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project = client.post("/api/projects", json={"name": "Brouillon"}).json()
        launched = client.post(
            f"/api/projects/{project['id']}/demandes",
            json={
                "text": "Carte avec une sortie HDMI vers un écran.",
                "mode": "autonome",
            },
        )
        job = _wait(client, project["id"], launched.json()["id"])
        spec = client.get(f"/api/projects/{project['id']}/specification")
        conversation = client.get(f"/api/projects/{project['id']}/conversation")

    assert job["status"] == "termine"
    assert spec.json() == {"state": "refusee", "explanation": explanation}
    assert conversation.json()["messages"][1] == {
        "role": "agent",
        "content": explanation,
    }


def test_validated_mode_asks_once_then_builds_the_spec(tmp_path: Path) -> None:
    questions = [
        "Quelle est la tension d'alimentation ?",
        "Quel courant le capteur consomme-t-il ?",
    ]
    model = ScriptedModel(
        [
            json.dumps({"decision": "questions", "questions": questions}),
            json.dumps(CAPTEUR),
        ]
    )
    vague = "Une carte capteur, je ne sais pas encore l'alimentation."
    answer = "USB 5 V, capteur 20 mA."
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project = client.post("/api/projects", json={"name": "Brouillon"}).json()
        project_id = project["id"]
        first = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": vague, "mode": "valide"},
        )
        first_job = _wait(client, project_id, first.json()["id"])
        asked = client.get(f"/api/projects/{project_id}/specification")
        second = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": answer, "mode": "valide"},
        )
        second_job = _wait(client, project_id, second.json()["id"])
        ready = client.get(f"/api/projects/{project_id}/specification")
        conversation = client.get(f"/api/projects/{project_id}/conversation")

    assert first_job["status"] == "termine"
    assert asked.json() == {"state": "questions", "questions": questions}
    assert second_job["status"] == "termine"
    specification = ready.json()["specification"]
    assert specification["mode"] == "valide"
    assert specification["name"] == "Capteur seuil"
    assert specification["layers"] == 2
    assert [message["content"] for message in conversation.json()["messages"]] == [
        vague,
        "\n".join(questions),
        answer,
        "Spécification prête.\nHypothèses :\n- Alimentation USB 5 V ramenée en 3,3 V",
    ]
    assert questions[0] in model.prompts[1]
    assert answer in model.prompts[1]


def test_a_second_question_round_keeps_the_first(tmp_path: Path) -> None:
    first = "Quelle est la tension d'alimentation ?"
    answer = "USB 5 V."
    model = ScriptedModel(
        [
            json.dumps({"decision": "questions", "questions": [first]}),
            json.dumps({"decision": "questions", "questions": ["Quel connecteur ?"]}),
        ]
    )
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project_id = _project_id(client)
        client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": "Une carte capteur.", "mode": "valide"},
        )
        _wait_latest(client, project_id)
        second = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": answer, "mode": "valide"},
        )
        job = _wait(client, project_id, second.json()["id"])
        spec = client.get(f"/api/projects/{project_id}/specification")
        messages = client.get(f"/api/projects/{project_id}/conversation").json()[
            "messages"
        ]

    assert job["status"] == "echec"
    assert job["error"] == "Le mode validé n'accepte qu'un seul round de questions."
    assert spec.json() == {"state": "questions", "questions": [first]}
    assert [message["content"] for message in messages] == [
        "Une carte capteur.",
        first,
        answer,
        "Le mode validé n'accepte qu'un seul round de questions.",
    ]


def test_autonomous_mode_rejects_questions_from_the_model(tmp_path: Path) -> None:
    model = ScriptedModel(
        [json.dumps({"decision": "questions", "questions": ["Quelle tension ?"]})]
    )
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project_id = _project_id(client)
        launched = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        job = _wait(client, project_id, launched.json()["id"])
        spec = client.get(f"/api/projects/{project_id}/specification")

    assert job["status"] == "echec"
    assert job["error"] == "Le mode autonome ne pose pas de questions."
    assert spec.json() == {"state": "absente"}


def test_a_ready_spec_can_be_edited_before_design(tmp_path: Path) -> None:
    model = ScriptedModel([json.dumps(CAPTEUR)])
    edited = {
        "name": "Capteur révisé",
        "blocks": [{"name": "Microcontrôleur", "role": "Lit le capteur et décide"}],
        "rails": [{"name": "3V3", "voltage_v": 3.3, "current_a": 0.5}],
        "interfaces": ["I2C", "USB"],
        "dimensions": {"max_width_mm": 40, "max_height_mm": 30},
        "layers": 4,
        "budget": {"max_amount": 20, "currency": "EUR"},
        "mode": "valide",
        "assumptions": ["Boîtier plus petit"],
    }
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project_id = _project_id(client)
        launched = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        _wait(client, project_id, launched.json()["id"])
        updated = client.patch(
            f"/api/projects/{project_id}/specification",
            json=edited,
        )
        reread = client.get(f"/api/projects/{project_id}/specification")
        conversation = client.get(f"/api/projects/{project_id}/conversation")

    assert updated.status_code == 200
    assert updated.json() == {"state": "prete", "specification": edited}
    assert reread.json() == updated.json()
    assert len(conversation.json()["messages"]) == 2


def test_unready_spec_cannot_be_edited(tmp_path: Path) -> None:
    app = create_app(tmp_path / "nia.sqlite", model=ScriptedModel([]))
    with TestClient(app) as client:
        project_id = _project_id(client)
        edited = client.patch(
            f"/api/projects/{project_id}/specification",
            json=_ready_body(),
        )
        invalid = client.patch(
            f"/api/projects/{project_id}/specification",
            json={**_ready_body(), "layers": 3},
        )

    assert edited.status_code == 409
    assert edited.json()["detail"] == "La spécification n'est pas encore modifiable."
    assert invalid.status_code == 422


def test_malformed_model_output_is_explained(tmp_path: Path) -> None:
    model = ScriptedModel(["ce n'est pas du JSON"])
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project_id = _project_id(client)
        launched = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        job = _wait(client, project_id, launched.json()["id"])
        spec = client.get(f"/api/projects/{project_id}/specification")
        messages = client.get(f"/api/projects/{project_id}/conversation").json()[
            "messages"
        ]

    assert job["status"] == "echec"
    assert job["error"] == (
        "La réponse du modèle n'est pas une spécification exploitable."
    )
    assert spec.json() == {"state": "absente"}
    assert messages[-1]["content"] == job["error"]


def test_conversation_and_spec_survive_a_restart(tmp_path: Path) -> None:
    database = tmp_path / "nia.sqlite"
    with TestClient(
        create_app(database, model=ScriptedModel([json.dumps(CAPTEUR)]))
    ) as client:
        project_id = _project_id(client)
        launched = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        _wait(client, project_id, launched.json()["id"])
        spec = client.get(f"/api/projects/{project_id}/specification").json()
        conversation = client.get(f"/api/projects/{project_id}/conversation").json()

    with TestClient(create_app(database, model=ScriptedModel([]))) as client:
        reopened_spec = client.get(f"/api/projects/{project_id}/specification")
        reopened_conversation = client.get(f"/api/projects/{project_id}/conversation")

    assert reopened_spec.json() == spec
    assert reopened_conversation.json() == conversation


def test_a_corrected_demand_replaces_a_refusal(tmp_path: Path) -> None:
    model = ScriptedModel(
        [
            json.dumps({"decision": "refus", "explication": "Le HDMI est hors v1."}),
            json.dumps(CAPTEUR),
        ]
    )
    with TestClient(create_app(tmp_path / "nia.sqlite", model=model)) as client:
        project_id = _project_id(client)
        first = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": "Une carte HDMI.", "mode": "autonome"},
        )
        _wait(client, project_id, first.json()["id"])
        second = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        _wait(client, project_id, second.json()["id"])
        spec = client.get(f"/api/projects/{project_id}/specification")

    assert spec.json()["state"] == "prete"
    assert spec.json()["specification"]["name"] == "Capteur seuil"


def test_missing_project_is_explained(tmp_path: Path) -> None:
    app = create_app(tmp_path / "nia.sqlite", model=ScriptedModel([]))
    with TestClient(app) as client:
        missing = client.post(
            "/api/projects/projet-absent/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        spec = client.get("/api/projects/projet-absent/specification")
        conversation = client.get("/api/projects/projet-absent/conversation")

    assert missing.status_code == 404
    assert missing.json()["detail"] == "Ce projet n'existe pas."
    assert spec.status_code == 404
    assert conversation.status_code == 404


def test_blank_demand_is_refused(tmp_path: Path) -> None:
    app = create_app(tmp_path / "nia.sqlite", model=ScriptedModel([]))
    with TestClient(app) as client:
        project_id = _project_id(client)
        refused = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": "   ", "mode": "autonome"},
        )

    assert refused.status_code == 422


def test_demand_without_a_configured_model_is_explained(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        project_id = _project_id(client)
        launched = client.post(
            f"/api/projects/{project_id}/demandes",
            json={"text": DEMANDE, "mode": "autonome"},
        )
        job = _wait(client, project_id, launched.json()["id"])

    assert job["status"] == "echec"
    assert job["error"] == "Aucun modèle n'est configuré."


def test_spec_is_absent_before_any_demand(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "nia.sqlite")) as client:
        project_id = _project_id(client)
        spec = client.get(f"/api/projects/{project_id}/specification")
        conversation = client.get(f"/api/projects/{project_id}/conversation")

    assert spec.json() == {"state": "absente"}
    assert conversation.json() == {"messages": []}


def _project_id(client: TestClient) -> str:
    created = client.post("/api/projects", json={"name": "Brouillon"})
    assert created.status_code == 201
    return created.json()["id"]


def _ready_body() -> dict[str, Any]:
    body = {key: value for key, value in CAPTEUR.items() if key != "decision"}
    body["mode"] = "autonome"
    return body


def _wait_latest(client: TestClient, project_id: str) -> dict[str, object]:
    latest = client.get(f"/api/projects/{project_id}/jobs/latest")
    assert latest.status_code == 200
    return _wait(client, project_id, latest.json()["id"])


def _wait(client: TestClient, project_id: str, job_id: str) -> dict[str, object]:
    last: dict[str, object] = {}
    for _ in range(50):
        response = client.get(f"/api/projects/{project_id}/jobs/{job_id}")
        last = response.json()
        if last["status"] in {"termine", "echec", "arrete"}:
            return last
        time.sleep(0.02)
    raise AssertionError(last)
