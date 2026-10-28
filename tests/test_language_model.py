"""L'adaptateur du modèle lit une complétion et ne révèle pas la clé."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nia_pcb.llm import OpenAICompatibleModel


def test_completion_returns_the_model_text_without_the_secret() -> None:
    seen: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode()
            seen["path"] = self.path
            seen["authorization"] = self.headers.get("Authorization", "")
            seen["body"] = body
            payload = json.dumps(
                {"choices": [{"message": {"content": '{"decision":"refus"}'}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        model = OpenAICompatibleModel(
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="sk-test-secret",
            model="modele-test",
        )
        text = model.complete("Décris une carte capteur.")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert text == '{"decision":"refus"}'
    assert seen["path"] == "/v1/chat/completions"
    assert seen["authorization"] == "Bearer sk-test-secret"
    assert "sk-test-secret" not in text
    sent = json.loads(seen["body"])
    assert sent["model"] == "modele-test"
    assert sent["messages"][0]["content"] == "Décris une carte capteur."


def test_a_broken_model_response_is_explained_without_the_secret() -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            payload = b'{"choices":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        model = OpenAICompatibleModel(
            base_url=f"http://127.0.0.1:{port}/v1/",
            api_key="sk-test-secret",
            model="modele-test",
        )
        try:
            model.complete("Décris une carte capteur.")
        except RuntimeError as exc:
            message = str(exc)
        else:
            raise AssertionError("le modèle aurait dû échouer")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert message == "Le modèle n'a pas répondu."
    assert "sk-test-secret" not in message
