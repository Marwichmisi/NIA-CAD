"""Projets locaux : création, liste et réouverture, persistés dans SQLite."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, field_validator
from sqlalchemy import event
from sqlmodel import Field, Session, SQLModel, col, create_engine, select


class Project(BaseModel):
    id: str
    name: str
    status: Literal["brouillon"]
    created_at: datetime
    status_changed_at: datetime


class CreateProject(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Indique un nom de projet.")
        if len(cleaned) > 80:
            raise ValueError("Le nom tient en 80 caractères maximum.")
        return cleaned


class ProjectNotFound(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(project_id)


class ProjectRecord(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(primary_key=True)
    name: str
    status: str
    created_at: datetime
    status_changed_at: datetime


class StatusTransitionRecord(SQLModel, table=True):
    __tablename__ = "project_status_transitions"

    id: int | None = Field(default=None, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    status: str
    changed_at: datetime


class ProjectStore:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{database_path.resolve()}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def create(self, name: str) -> Project:
        changed_at = datetime.now(UTC)
        record = ProjectRecord(
            id=str(uuid4()),
            name=name,
            status="brouillon",
            created_at=changed_at,
            status_changed_at=changed_at,
        )
        transition = StatusTransitionRecord(
            project_id=record.id,
            status="brouillon",
            changed_at=changed_at,
        )
        with Session(self.engine) as session:
            session.add(record)
            session.add(transition)
            session.commit()
            session.refresh(record)
            return _to_project(record)

    def list_projects(self) -> list[Project]:
        with Session(self.engine) as session:
            records = session.exec(
                select(ProjectRecord).order_by(col(ProjectRecord.created_at).desc())
            ).all()
            return [_to_project(record) for record in records]

    def open(self, project_id: str) -> Project:
        with Session(self.engine) as session:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise ProjectNotFound(project_id)
            return _to_project(record)


def _to_project(record: ProjectRecord) -> Project:
    if record.status != "brouillon":
        raise RuntimeError(f"statut de projet inattendu : {record.status}")
    return Project(
        id=record.id,
        name=record.name,
        status=record.status,
        created_at=record.created_at,
        status_changed_at=record.status_changed_at,
    )
