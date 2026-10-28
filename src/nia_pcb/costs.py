"""Coûts par projet et cumul, alerte à 80 % et garde au plafond."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel, select

from nia_pcb.projects import ProjectNotFound, ProjectRecord
from nia_pcb.secrets import redact_text
from nia_pcb.settings import SettingsStore


class RecordCost(BaseModel):
    tokens: int
    cost_eur: float
    note: str = ""

    @field_validator("tokens")
    @classmethod
    def clean_tokens(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Indique un nombre entier de jetons.")
        if value < 0:
            raise ValueError("Les jetons ne peuvent pas être négatifs.")
        return value

    @field_validator("cost_eur")
    @classmethod
    def clean_cost(cls, value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Indique un coût positif ou nul.")
        if float(value) < 0:
            raise ValueError("Le coût ne peut pas être négatif.")
        return float(value)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 500:
            raise ValueError("La note tient en 500 caractères maximum.")
        return redact_text(cleaned)


class CostSummary(BaseModel):
    project_id: str
    project_tokens: int
    project_cost: float
    total_tokens: int
    total_cost: float
    token_budget: int
    cost_budget: float
    alert_80: bool
    over_budget: bool


class CostBreakdown(BaseModel):
    project_id: str
    project_name: str = ""
    tokens: int
    cost: float


class CostsTotals(BaseModel):
    total_tokens: int
    total_cost: float
    projects: list[CostBreakdown] = []


class CostRecord(SQLModel, table=True):
    __tablename__ = "costs"

    id: int | None = SqlField(default=None, primary_key=True)
    project_id: str = SqlField(foreign_key="projects.id", index=True)
    tokens: int
    cost_eur: float
    note: str = ""
    created_at: datetime


class CostStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def record(
        self, project_id: str, tokens: int, cost_eur: float, note: str = ""
    ) -> CostSummary:
        body = RecordCost(tokens=tokens, cost_eur=cost_eur, note=note)
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            session.add(
                CostRecord(
                    project_id=project_id,
                    tokens=body.tokens,
                    cost_eur=body.cost_eur,
                    note=body.note,
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
        return self.summary(project_id)

    def summary(self, project_id: str) -> CostSummary:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            project_tokens = (
                session.exec(
                    select(func.coalesce(func.sum(CostRecord.tokens), 0)).where(
                        CostRecord.project_id == project_id
                    )
                ).one()
                or 0
            )
            project_cost = (
                session.exec(
                    select(func.coalesce(func.sum(CostRecord.cost_eur), 0.0)).where(
                        CostRecord.project_id == project_id
                    )
                ).one()
                or 0.0
            )
            total_tokens = (
                session.exec(
                    select(func.coalesce(func.sum(CostRecord.tokens), 0))
                ).one()
                or 0
            )
            total_cost = (
                session.exec(
                    select(func.coalesce(func.sum(CostRecord.cost_eur), 0.0))
                ).one()
                or 0.0
            )
        settings = SettingsStore(self.engine).get()
        token_budget = settings.project_token_budget
        cost_budget = settings.project_cost_budget_eur
        alert_80 = (int(project_tokens) >= 0.8 * token_budget) or (
            float(project_cost) >= 0.8 * cost_budget
        )
        over_budget = (int(project_tokens) >= token_budget) or (
            float(project_cost) >= cost_budget
        )
        return CostSummary(
            project_id=project_id,
            project_tokens=int(project_tokens),
            project_cost=float(project_cost),
            total_tokens=int(total_tokens),
            total_cost=float(total_cost),
            token_budget=token_budget,
            cost_budget=cost_budget,
            alert_80=bool(alert_80),
            over_budget=bool(over_budget),
        )

    def totals(self) -> tuple[int, float]:
        with Session(self.engine) as session:
            total_tokens = (
                session.exec(
                    select(func.coalesce(func.sum(CostRecord.tokens), 0))
                ).one()
                or 0
            )
            total_cost = (
                session.exec(
                    select(func.coalesce(func.sum(CostRecord.cost_eur), 0.0))
                ).one()
                or 0.0
            )
        return int(total_tokens), float(total_cost)

    def per_project(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = session.exec(
                select(
                    CostRecord.project_id,
                    func.coalesce(func.sum(CostRecord.tokens), 0),
                    func.coalesce(func.sum(CostRecord.cost_eur), 0.0),
                ).group_by(CostRecord.project_id)
            ).all()
            return [
                {
                    "project_id": project_id,
                    "tokens": int(tokens),
                    "cost": float(cost),
                }
                for project_id, tokens, cost in rows
            ]
