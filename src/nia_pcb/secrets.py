"""Secrets locaux : présence signalée, valeurs jamais exposées ni journalisées."""

import os
from typing import Any

SECRET_ENV_VARS = (
    "OPENAI_API_KEY",
    "MODEL_API_KEY",
    "JLCPCB_API_KEY",
    "LCSC_API_KEY",
)

MASK = "***"


def secret_values() -> list[str]:
    values: list[str] = []
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if len(value) >= 4 and value not in values:
            values.append(value)
    return values


def redact_text(text: str) -> str:
    cleaned = text
    for secret in secret_values():
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, MASK)
    return cleaned


def redact_value(payload: Any) -> Any:
    if isinstance(payload, str):
        return redact_text(payload)
    if isinstance(payload, dict):
        return {key: redact_value(item) for key, item in payload.items()}
    if isinstance(payload, list):
        return [redact_value(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_value(item) for item in payload)
    return payload


def has_llm_key() -> bool:
    return bool(
        os.environ.get("OPENAI_API_KEY", "").strip()
        or os.environ.get("MODEL_API_KEY", "").strip()
    )


def has_jlcpcb_key() -> bool:
    return bool(os.environ.get("JLCPCB_API_KEY", "").strip())
