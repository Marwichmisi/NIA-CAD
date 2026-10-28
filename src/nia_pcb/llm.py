"""Modèle de langage compatible OpenAI. La clé reste dans l'environnement."""

import json
import os
import urllib.error
import urllib.request


class OpenAICompatibleModel:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def complete(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self._model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode()
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode()
        except urllib.error.URLError as exc:
            raise RuntimeError("Le modèle n'a pas répondu.") from exc
        try:
            content = json.loads(raw)["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Le modèle n'a pas répondu.") from exc
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Le modèle n'a pas répondu.")
        return content


def model_from_environment() -> OpenAICompatibleModel | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()
    if not api_key or not model:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    return OpenAICompatibleModel(
        base_url=base_url or "https://api.openai.com/v1",
        api_key=api_key,
        model=model,
    )
