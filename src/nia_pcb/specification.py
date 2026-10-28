"""Spécification structurée : comprendre la demande avant toute conception."""

import json
import os
from pathlib import Path
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel, col, select

from nia_pcb.jobs import JobContext
from nia_pcb.projects import ProjectNotFound, ProjectRecord


def _prompt_path() -> Path:
    override = os.environ.get("NIA_PROMPTS", "").strip()
    if override:
        return Path(override) / "specification.md"
    return Path(__file__).resolve().parents[2] / "prompts" / "specification.md"


UNUSABLE = "La réponse du modèle n'est pas une spécification exploitable."
Mode = Literal["autonome", "valide"]


class LanguageModel(Protocol):
    def complete(self, prompt: str) -> str: ...


class UnusableModelOutput(Exception):
    def __init__(self, message: str = UNUSABLE) -> None:
        super().__init__(message)


class SpecificationNotEditable(Exception):
    def __init__(self) -> None:
        super().__init__("La spécification n'est pas encore modifiable.")


class Demand(BaseModel):
    text: str
    mode: Mode

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Décris la carte.")
        if len(cleaned) > 4000:
            raise ValueError("La demande tient en 4000 caractères maximum.")
        return cleaned


class Block(BaseModel):
    name: str
    role: str

    @field_validator("name", "role")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _required_text(value)


class Rail(BaseModel):
    name: str
    voltage_v: float
    current_a: float

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("voltage_v", "current_a")
    @classmethod
    def positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Indique une valeur positive.")
        return value


class Dimensions(BaseModel):
    max_width_mm: float
    max_height_mm: float

    @field_validator("max_width_mm", "max_height_mm")
    @classmethod
    def positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Indique une dimension positive.")
        return value


class Budget(BaseModel):
    max_amount: float
    currency: str

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("max_amount")
    @classmethod
    def positive_amount(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Indique un budget positif.")
        return value


class BoardSpecification(BaseModel):
    name: str
    blocks: list[Block] = Field(min_length=1)
    rails: list[Rail] = Field(min_length=1)
    interfaces: list[str]
    dimensions: Dimensions
    layers: Literal[1, 2, 4]
    budget: Budget
    mode: Mode
    assumptions: list[str]

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = _required_text(value)
        if len(cleaned) > 80:
            raise ValueError("Le nom tient en 80 caractères maximum.")
        return cleaned

    @field_validator("interfaces", "assumptions")
    @classmethod
    def clean_items(cls, value: list[str]) -> list[str]:
        return [_required_text(item) for item in value]


class ReadySpecification(BaseModel):
    state: Literal["prete"] = "prete"
    specification: BoardSpecification


class RefusedSpecification(BaseModel):
    state: Literal["refusee"] = "refusee"
    explanation: str

    @field_validator("explanation")
    @classmethod
    def clean_explanation(cls, value: str) -> str:
        return _required_text(value)


class PendingQuestions(BaseModel):
    state: Literal["questions"] = "questions"
    questions: list[str] = Field(min_length=1)

    @field_validator("questions")
    @classmethod
    def clean_questions(cls, value: list[str]) -> list[str]:
        return [_required_text(item) for item in value]


class AbsentSpecification(BaseModel):
    state: Literal["absente"] = "absente"


SavedSpecification = ReadySpecification | RefusedSpecification | PendingQuestions
SpecificationView = Annotated[
    ReadySpecification | RefusedSpecification | PendingQuestions | AbsentSpecification,
    Field(discriminator="state"),
]


class ConversationMessage(BaseModel):
    role: Literal["maker", "agent"]
    content: str


class Conversation(BaseModel):
    messages: list[ConversationMessage]


class MessageRecord(SQLModel, table=True):
    __tablename__ = "conversation_messages"

    id: str = SqlField(primary_key=True)
    project_id: str = SqlField(foreign_key="projects.id", index=True)
    position: int
    role: str
    content: str


class SpecificationRecord(SQLModel, table=True):
    __tablename__ = "specifications"

    project_id: str = SqlField(primary_key=True, foreign_key="projects.id")
    state: str
    payload_json: str


class SpecificationStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save(
        self,
        project_id: str,
        job_id: str,
        demand: str,
        agent: str,
        view: SavedSpecification,
    ) -> None:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            _write_messages(session, project_id, job_id, demand, agent)
            payload = view.model_dump_json()
            row = session.get(SpecificationRecord, project_id)
            if row is None:
                session.add(
                    SpecificationRecord(
                        project_id=project_id,
                        state=view.state,
                        payload_json=payload,
                    )
                )
            else:
                row.state = view.state
                row.payload_json = payload
                session.add(row)
            session.commit()

    def note(self, project_id: str, job_id: str, demand: str, agent: str) -> None:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            _write_messages(session, project_id, job_id, demand, agent)
            session.commit()

    def update(
        self, project_id: str, specification: BoardSpecification
    ) -> ReadySpecification:
        view = ReadySpecification(specification=specification)
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            row = session.get(SpecificationRecord, project_id)
            if row is None or row.state != "prete":
                raise SpecificationNotEditable
            row.state = view.state
            row.payload_json = view.model_dump_json()
            session.add(row)
            session.commit()
            return view

    def read(self, project_id: str) -> SpecificationView:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            row = session.get(SpecificationRecord, project_id)
            if row is None:
                return AbsentSpecification()
            return _view_from_json(row.payload_json)

    def conversation(self, project_id: str) -> Conversation:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            rows = session.exec(
                select(MessageRecord)
                .where(MessageRecord.project_id == project_id)
                .order_by(col(MessageRecord.position))
            ).all()
            return Conversation(
                messages=[
                    ConversationMessage(role=_role(row.role), content=row.content)
                    for row in rows
                ]
            )


def make_specification_step(store: SpecificationStore, model: LanguageModel | None):
    def run(context: JobContext) -> None:
        if model is None:
            raise RuntimeError("Aucun modèle n'est configuré.")
        text = context.inputs.get("text", "").strip()
        mode = context.inputs.get("mode", "")
        if mode not in {"autonome", "valide"}:
            raise RuntimeError("Le mode est autonome ou validé.")
        answering = store.read(context.project_id).state == "questions"
        prompt = _render_prompt(text, mode, store.conversation(context.project_id))
        try:
            outcome = _interpret(model.complete(prompt), mode, answering)
        except UnusableModelOutput as exc:
            store.note(context.project_id, context.job_id, text, str(exc))
            raise
        agent, journal = _outcome_text(outcome)
        store.save(context.project_id, context.job_id, text, agent, outcome)
        context.set_result({"state": outcome.state})
        context.log(journal)

    return run


def _interpret(raw: str, mode: str, answering: bool) -> SavedSpecification:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UnusableModelOutput from exc
    if not isinstance(data, dict):
        raise UnusableModelOutput
    decision = data.get("decision")
    if decision == "refus":
        return _refusal(data)
    if decision == "questions":
        return _questions(data, mode, answering)
    if decision == "specification":
        return ReadySpecification(specification=_specification(data, mode))
    raise UnusableModelOutput


def _questions(data: dict[str, object], mode: str, answering: bool) -> PendingQuestions:
    if mode == "autonome":
        raise UnusableModelOutput("Le mode autonome ne pose pas de questions.")
    if answering:
        raise UnusableModelOutput(
            "Le mode validé n'accepte qu'un seul round de questions."
        )
    try:
        return PendingQuestions.model_validate({"questions": data.get("questions")})
    except ValidationError as exc:
        raise UnusableModelOutput from exc


def _refusal(data: dict[str, object]) -> RefusedSpecification:
    try:
        return RefusedSpecification.model_validate(
            {"explanation": data.get("explication")}
        )
    except ValidationError as exc:
        raise UnusableModelOutput from exc


def _specification(data: dict[str, object], mode: str) -> BoardSpecification:
    try:
        specification = BoardSpecification.model_validate({**data, "mode": mode})
    except ValidationError as exc:
        raise UnusableModelOutput from exc
    if mode == "autonome" and not specification.assumptions:
        raise UnusableModelOutput
    return specification


def _view_from_json(payload: str) -> SpecificationView:
    data = json.loads(payload)
    state = data.get("state")
    if state == "prete":
        return ReadySpecification.model_validate(data)
    if state == "refusee":
        return RefusedSpecification.model_validate(data)
    if state == "questions":
        return PendingQuestions.model_validate(data)
    raise RuntimeError(f"état de spécification inattendu : {state}")


def _render_prompt(text: str, mode: str, conversation: Conversation) -> str:
    history = "\n".join(
        f"{message.role}: {message.content}" for message in conversation.messages
    )
    path = _prompt_path()
    if not path.is_file():
        raise RuntimeError("Le gabarit de spécification est introuvable.")
    template = path.read_text(encoding="utf-8")
    return (
        template.replace("{mode}", mode)
        .replace("{demande}", text)
        .replace("{conversation}", history or "(aucune)")
    )


def _outcome_text(outcome: SavedSpecification) -> tuple[str, str]:
    if isinstance(outcome, ReadySpecification):
        return _agent_text(outcome.specification), "Spécification prête."
    if isinstance(outcome, RefusedSpecification):
        return outcome.explanation, "Demande refusée : hors périmètre v1."
    return "\n".join(outcome.questions), "Questions de clarification."


def _agent_text(specification: BoardSpecification) -> str:
    lines = ["Spécification prête."]
    if specification.assumptions:
        lines.append("Hypothèses :")
        lines.extend(f"- {item}" for item in specification.assumptions)
    return "\n".join(lines)


def _required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Le texte est vide.")
    return cleaned


def _role(value: str) -> Literal["maker", "agent"]:
    if value == "maker":
        return "maker"
    if value == "agent":
        return "agent"
    raise RuntimeError(f"rôle de message inattendu : {value}")


def _write_messages(
    session: Session,
    project_id: str,
    job_id: str,
    demand: str,
    agent: str,
) -> None:
    _upsert_message(session, project_id, f"{job_id}:maker", "maker", demand)
    _upsert_message(session, project_id, f"{job_id}:agent", "agent", agent)


def _upsert_message(
    session: Session,
    project_id: str,
    message_id: str,
    role: str,
    content: str,
) -> None:
    row = session.get(MessageRecord, message_id)
    if row is None:
        current = session.exec(
            select(func.max(MessageRecord.position)).where(
                MessageRecord.project_id == project_id
            )
        ).one()
        session.add(
            MessageRecord(
                id=message_id,
                project_id=project_id,
                position=int(current or 0) + 1,
                role=role,
                content=content,
            )
        )
        session.flush()
        return
    row.content = content
    session.add(row)
