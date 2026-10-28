"""Réglages non secrets synchronisés entre l'interface et la configuration."""

import os
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy.engine import Engine
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel

from nia_pcb.secrets import has_jlcpcb_key, has_llm_key

FACTORY_DEFAULTS: dict[str, Any] = {
    "llm_model": "muse-spark-1.3",
    "llm_base_url": "https://api.openai.com/v1",
    "ato_max_iterations": 30,
    "routing_max_passes": 15,
    "retention_builds_days": 30,
    "retention_abandoned_days": 90,
    "project_token_budget": 200000,
    "project_cost_budget_eur": 5.0,
}


class PublicSettings(BaseModel):
    llm_model: str
    llm_base_url: str
    ato_max_iterations: int
    routing_max_passes: int
    retention_builds_days: int
    retention_abandoned_days: int
    project_token_budget: int
    project_cost_budget_eur: float
    has_llm_key: bool
    has_jlcpcb_key: bool


class SettingsUpdate(BaseModel):
    llm_model: str
    llm_base_url: str
    ato_max_iterations: int
    routing_max_passes: int
    retention_builds_days: int
    retention_abandoned_days: int
    project_token_budget: int
    project_cost_budget_eur: float

    @field_validator("llm_model")
    @classmethod
    def clean_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Indique un modèle.")
        if len(cleaned) > 80:
            raise ValueError("Le modèle tient en 80 caractères maximum.")
        return cleaned

    @field_validator("llm_base_url")
    @classmethod
    def clean_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            raise ValueError("Indique une URL de base.")
        if not (
            cleaned.startswith("http://") or cleaned.startswith("https://")
        ):
            raise ValueError("L'URL de base doit commencer par http(s)://.")
        if len(cleaned) > 200:
            raise ValueError("L'URL de base tient en 200 caractères maximum.")
        return cleaned

    @field_validator(
        "ato_max_iterations",
        "routing_max_passes",
        "retention_builds_days",
        "retention_abandoned_days",
        "project_token_budget",
    )
    @classmethod
    def positive_int(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Indique un entier positif.")
        if value <= 0:
            raise ValueError("Indique un entier positif.")
        return value

    @field_validator("project_cost_budget_eur")
    @classmethod
    def positive_cost(cls, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Indique un budget positif.")
        if float(value) <= 0:
            raise ValueError("Indique un budget positif.")
        return float(value)


class SettingsRecord(SQLModel, table=True):
    __tablename__ = "settings"

    id: int = SqlField(default=1, primary_key=True)
    llm_model: str = FACTORY_DEFAULTS["llm_model"]
    llm_base_url: str = FACTORY_DEFAULTS["llm_base_url"]
    ato_max_iterations: int = FACTORY_DEFAULTS["ato_max_iterations"]
    routing_max_passes: int = FACTORY_DEFAULTS["routing_max_passes"]
    retention_builds_days: int = FACTORY_DEFAULTS["retention_builds_days"]
    retention_abandoned_days: int = FACTORY_DEFAULTS["retention_abandoned_days"]
    project_token_budget: int = FACTORY_DEFAULTS["project_token_budget"]
    project_cost_budget_eur: float = FACTORY_DEFAULTS["project_cost_budget_eur"]


class SettingsStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self) -> PublicSettings:
        with Session(self.engine) as session:
            record = session.get(SettingsRecord, 1)
            values = dict(FACTORY_DEFAULTS)
            if record is not None:
                values.update(_record_values(record))
            else:
                env_model = os.environ.get("OPENAI_MODEL", "").strip()
                if env_model:
                    values["llm_model"] = env_model[:80]
                env_base = os.environ.get("OPENAI_BASE_URL", "").strip()
                if env_base.startswith(("http://", "https://")):
                    values["llm_base_url"] = env_base.rstrip("/")[:200]
            return PublicSettings(
                **values,
                has_llm_key=has_llm_key(),
                has_jlcpcb_key=has_jlcpcb_key(),
            )

    def update(self, body: SettingsUpdate) -> PublicSettings:
        with Session(self.engine) as session:
            record = session.get(SettingsRecord, 1)
            if record is None:
                record = SettingsRecord(id=1, **body.model_dump())
            else:
                for key, value in body.model_dump().items():
                    setattr(record, key, value)
            session.add(record)
            session.commit()
        return self.get()

    def reset(self) -> PublicSettings:
        with Session(self.engine) as session:
            record = session.get(SettingsRecord, 1)
            if record is None:
                record = SettingsRecord(id=1)
            else:
                for key, value in FACTORY_DEFAULTS.items():
                    setattr(record, key, value)
            session.add(record)
            session.commit()
        return self.get()


def _record_values(record: SettingsRecord) -> dict[str, Any]:
    return {
        "llm_model": record.llm_model,
        "llm_base_url": record.llm_base_url,
        "ato_max_iterations": record.ato_max_iterations,
        "routing_max_passes": record.routing_max_passes,
        "retention_builds_days": record.retention_builds_days,
        "retention_abandoned_days": record.retention_abandoned_days,
        "project_token_budget": record.project_token_budget,
        "project_cost_budget_eur": record.project_cost_budget_eur,
    }
