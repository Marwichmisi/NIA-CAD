"""Persistance de la liste de pièces par projet, avec validation explicite."""

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel

from nia_pcb.jobs import JobContext
from nia_pcb.parts import ChosenPart, PartRequirement, PartsList, RejectedPart
from nia_pcb.parts_catalog import PartsCatalog
from nia_pcb.projects import ProjectNotFound, ProjectRecord


class PartsView(BaseModel):
    project_id: str
    choisies: list[ChosenPart] = Field(default_factory=list)
    rejetees: list[RejectedPart] = Field(default_factory=list)
    validee: bool = False

    @property
    def chosen(self) -> list[ChosenPart]:
        return self.choisies

    @property
    def rejected(self) -> list[RejectedPart]:
        return self.rejetees


class PartsRequest(BaseModel):
    exigences: list[PartRequirement] = Field(min_length=1)


class PartsRecord(SQLModel, table=True):
    __tablename__ = "parts_lists"

    project_id: str = SqlField(primary_key=True, foreign_key="projects.id")
    payload_json: str = '{"chosen": [], "rejected": []}'
    validated: bool = False
    updated_at: datetime = SqlField(
        default_factory=lambda: datetime.now(UTC),
    )


class PartsNotFound(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(project_id)


class PartsStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save(self, project_id: str, parts: PartsList) -> PartsView:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            payload = parts.model_dump_json()
            row = session.get(PartsRecord, project_id)
            if row is None:
                row = PartsRecord(
                    project_id=project_id,
                    payload_json=payload,
                    validated=False,
                    updated_at=datetime.now(UTC),
                )
            else:
                row.payload_json = payload
                row.validated = False
                row.updated_at = datetime.now(UTC)
            session.add(row)
            session.commit()
            return self.read(project_id)

    def read(self, project_id: str) -> PartsView:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            row = session.get(PartsRecord, project_id)
            if row is None:
                return PartsView(project_id=project_id)
            parts = PartsList.model_validate_json(row.payload_json)
            return PartsView(
                project_id=project_id,
                choisies=parts.chosen,
                rejetees=parts.rejected,
                validee=bool(row.validated),
            )

    def validate(self, project_id: str) -> PartsView:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            row = session.get(PartsRecord, project_id)
            if row is None:
                raise PartsNotFound(project_id)
            row.validated = True
            row.updated_at = datetime.now(UTC)
            session.add(row)
            session.commit()
            return self.read(project_id)


def make_parts_step(
    store: PartsStore, catalog: PartsCatalog
) -> Callable[[JobContext], None]:
    def run(context: JobContext) -> None:
        import json as _json

        raw = context.inputs.get("exigences", "[]")
        try:
            data = _json.loads(raw)
        except Exception:
            raise RuntimeError("Les exigences pièces sont illisibles.")
        if not isinstance(data, list) or not data:
            raise RuntimeError("Indique au moins une exigence pièce.")
        try:
            requirements = [PartRequirement.model_validate(item) for item in data]
        except Exception:
            raise RuntimeError("Les exigences pièces sont invalides.")
        from nia_pcb.parts import select_parts

        candidates_by_ref: dict[str, list] = {}
        for req in requirements:
            query = (req.query or req.reference).strip()
            try:
                found = catalog.search(query)
            except Exception:
                found = []
            candidates_by_ref.setdefault(req.reference, []).extend(found or [])
        parts = select_parts(requirements, candidates_by_ref)
        store.save(context.project_id, parts)
        context.set_result(
            {
                "choisies": len(parts.chosen),
                "rejetees": len(parts.rejected),
            }
        )
        context.log(
            f"Pièces : {len(parts.chosen)} choisies, {len(parts.rejected)} rejetées."
        )

    return run
