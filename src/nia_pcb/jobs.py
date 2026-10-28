"""Jobs : lancement immédiat, exécution dans un worker, suivi et reprise."""

import hashlib
import json
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel, col, select

from nia_pcb.projects import ProjectNotFound, ProjectRecord

JobStatus = Literal["en_attente", "en_cours", "arrete", "termine", "echec"]


class LaunchJob(BaseModel):
    step: str
    inputs: dict[str, str] = Field(default_factory=dict)

    @field_validator("step")
    @classmethod
    def clean_step(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Indique une étape.")
        if len(cleaned) > 80:
            raise ValueError("L'étape tient en 80 caractères maximum.")
        return cleaned


class JobProgress(BaseModel):
    done: int
    total: int


class Job(BaseModel):
    id: str
    project_id: str
    step: str
    status: JobStatus
    checkpoint: str | None = None
    progress: JobProgress | None = None
    journal: list[str] = Field(default_factory=list)
    error: str | None = None


class JobNotFound(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(job_id)


class ProjectHasNoJob(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(project_id)


class JobNotStoppable(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(job_id)


class JobNotResumable(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(job_id)


class JobStopped(BaseException):
    """L'utilisateur a arrêté le job. N'est pas une erreur de l'étape."""


class WorkerHalted(BaseException):
    """Le worker s'arrête. Le job reste en cours pour être repris."""


class JobEvent:
    def __init__(self, event_id: int, kind: str, payload: dict[str, object]) -> None:
        self.id = event_id
        self.kind = kind
        self.payload = payload


class JobRecord(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = SqlField(primary_key=True)
    project_id: str = SqlField(foreign_key="projects.id", index=True)
    step: str
    inputs_json: str
    idempotency_key: str = SqlField(unique=True, index=True)
    status: str = SqlField(index=True)
    journal_json: str = "[]"
    checkpoints_json: str = "[]"
    progress_done: int | None = None
    progress_total: int | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobEventRecord(SQLModel, table=True):
    __tablename__ = "job_events"

    id: int | None = SqlField(default=None, primary_key=True)
    job_id: str = SqlField(foreign_key="jobs.id", index=True)
    kind: str
    payload_json: str


class JobStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create(self, project_id: str, step: str, inputs: Mapping[str, str]) -> Job:
        now = _now()
        key = _fingerprint(project_id, step, inputs)
        record = JobRecord(
            id=str(uuid4()),
            project_id=project_id,
            step=step,
            inputs_json=json.dumps(dict(inputs), sort_keys=True),
            idempotency_key=key,
            status="en_attente",
            journal_json="[]",
            checkpoints_json="[]",
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            existing = _existing_job(session, key)
            if existing is not None:
                return existing
            session.add(record)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raced = _existing_job(session, key)
                if raced is None:
                    raise
                return raced
            session.refresh(record)
            return _to_job(record)

    def claim_next(self, project_id: str) -> str | None:
        with Session(self.engine) as session:
            record = session.exec(
                select(JobRecord)
                .where(JobRecord.project_id == project_id)
                .where(col(JobRecord.status).in_(["en_attente", "en_cours"]))
                .order_by(col(JobRecord.created_at))
            ).first()
            if record is None:
                return None
            record.status = "en_cours"
            record.updated_at = _now()
            session.add(record)
            session.commit()
            return record.id

    def projects_with_open_jobs(self) -> list[str]:
        with Session(self.engine) as session:
            rows = session.exec(
                select(JobRecord.project_id).where(
                    col(JobRecord.status).in_(["en_attente", "en_cours"])
                )
            ).all()
            return list(dict.fromkeys(rows))

    def read(self, project_id: str, job_id: str) -> Job:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            record = session.get(JobRecord, job_id)
            if record is None or record.project_id != project_id:
                raise JobNotFound(job_id)
            return _to_job(record)

    def latest(self, project_id: str) -> Job:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            record = session.exec(
                select(JobRecord)
                .where(JobRecord.project_id == project_id)
                .order_by(col(JobRecord.created_at).desc())
            ).first()
            if record is None:
                raise ProjectHasNoJob(project_id)
            return _to_job(record)

    def events_after(self, job_id: str, last_id: int) -> list[JobEvent]:
        with Session(self.engine) as session:
            rows = session.exec(
                select(JobEventRecord)
                .where(JobEventRecord.job_id == job_id)
                .where(col(JobEventRecord.id) > last_id)
                .order_by(col(JobEventRecord.id))
            ).all()
            return [
                JobEvent(
                    event_id=row.id or 0,
                    kind=row.kind,
                    payload=json.loads(row.payload_json),
                )
                for row in rows
            ]

    def append_journal(self, job_id: str, message: str) -> None:
        self._record_event(job_id, "journal", {"message": message}, message=message)

    def set_progress(self, job_id: str, done: int, total: int) -> None:
        self._record_event(
            job_id,
            "progression",
            {"done": done, "total": total},
            progress=(done, total),
        )

    def _record_event(
        self,
        job_id: str,
        kind: str,
        payload: dict[str, object],
        message: str | None = None,
        progress: tuple[int, int] | None = None,
    ) -> None:
        with Session(self.engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                return
            if message is not None:
                journal = json.loads(record.journal_json)
                journal.append(message)
                record.journal_json = json.dumps(journal, ensure_ascii=False)
            if progress is not None:
                record.progress_done, record.progress_total = progress
            record.updated_at = _now()
            session.add(record)
            session.add(
                JobEventRecord(
                    job_id=job_id,
                    kind=kind,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
            )
            session.commit()

    def status_of(self, job_id: str) -> str:
        return self.get(job_id).status

    def checkpoints(self, job_id: str) -> list[str]:
        return json.loads(self.get(job_id).checkpoints_json)

    def add_checkpoint(self, job_id: str, name: str) -> None:
        with Session(self.engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                return
            done = json.loads(record.checkpoints_json)
            if name not in done:
                done.append(name)
            record.checkpoints_json = json.dumps(done, ensure_ascii=False)
            record.updated_at = _now()
            session.add(record)
            session.commit()

    def request_stop(self, project_id: str, job_id: str) -> Job:
        with Session(self.engine) as session:
            record = self._locked(session, project_id, job_id)
            if record.status not in {"en_attente", "en_cours"}:
                raise JobNotStoppable(job_id)
            record.status = "arrete"
            record.updated_at = _now()
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_job(record)

    def request_resume(self, project_id: str, job_id: str) -> Job:
        with Session(self.engine) as session:
            record = self._locked(session, project_id, job_id)
            if record.status != "arrete":
                raise JobNotResumable(job_id)
            record.status = "en_attente"
            record.updated_at = _now()
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_job(record)

    def _locked(self, session: Session, project_id: str, job_id: str) -> JobRecord:
        if session.get(ProjectRecord, project_id) is None:
            raise ProjectNotFound(project_id)
        record = session.get(JobRecord, job_id)
        if record is None or record.project_id != project_id:
            raise JobNotFound(job_id)
        return record

    def get(self, job_id: str) -> JobRecord:
        with Session(self.engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                raise KeyError(job_id)
            session.expunge(record)
            return record

    def complete(self, job_id: str) -> None:
        self._set_status(job_id, "termine")

    def fail(self, job_id: str, message: str) -> None:
        with Session(self.engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None or record.status != "en_cours":
                return
            record.status = "echec"
            record.error = message
            record.updated_at = _now()
            session.add(record)
            session.commit()

    def _set_status(self, job_id: str, status: JobStatus) -> None:
        with Session(self.engine) as session:
            record = session.get(JobRecord, job_id)
            if record is None or record.status != "en_cours":
                return
            record.status = status
            record.updated_at = _now()
            session.add(record)
            session.commit()


class JobContext:
    """Ce que voit une étape pendant qu'elle tourne."""

    def __init__(
        self,
        store: JobStore,
        job_id: str,
        inputs: Mapping[str, str],
        halt: threading.Event,
    ) -> None:
        self.inputs = dict(inputs)
        self._store = store
        self._job_id = job_id
        self._halt = halt
        self._done = set(store.checkpoints(job_id))

    def log(self, message: str) -> None:
        cleaned = message.strip()
        if cleaned:
            self._store.append_journal(self._job_id, cleaned)

    def progress(self, done: int, total: int) -> None:
        self._store.set_progress(self._job_id, done, total)

    def effect(self, name: str, action: Callable[[], None]) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Un effet a besoin d'un nom.")
        if cleaned in self._done:
            return
        self.abort_if_requested()
        action()
        self._store.add_checkpoint(self._job_id, cleaned)
        self._done.add(cleaned)
        self.abort_if_requested()

    def abort_if_requested(self) -> None:
        if self._halt.is_set():
            raise WorkerHalted
        if self._store.status_of(self._job_id) == "arrete":
            raise JobStopped


class JobRunner:
    def __init__(
        self,
        engine: Engine,
        steps: Mapping[str, Callable[[JobContext], None]],
    ) -> None:
        self.steps = dict(steps)
        self._store = JobStore(engine)
        self._halt = threading.Event()
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._wakes: dict[str, threading.Event] = {}

    def start(self) -> None:
        for project_id in self._store.projects_with_open_jobs():
            self._ensure_worker(project_id)

    def halt(self) -> None:
        self._halt.set()
        with self._lock:
            wakes = list(self._wakes.values())
            threads = list(self._threads.values())
        for wake in wakes:
            wake.set()
        for thread in threads:
            thread.join(timeout=2)

    def launch(self, project_id: str, step: str, inputs: Mapping[str, str]) -> Job:
        job = self._store.create(project_id, step, inputs)
        self._ensure_worker(project_id)
        return job

    def _ensure_worker(self, project_id: str) -> None:
        with self._lock:
            current = self._threads.get(project_id)
            if current is not None and current.is_alive():
                self._wakes[project_id].set()
                return
            wake = threading.Event()
            self._wakes[project_id] = wake
            thread = threading.Thread(
                target=self._loop,
                args=(project_id, wake),
                name=f"nia-jobs-{project_id[:8]}",
                daemon=True,
            )
            self._threads[project_id] = thread
            thread.start()

    def _loop(self, project_id: str, wake: threading.Event) -> None:
        while not self._halt.is_set():
            job_id = self._store.claim_next(project_id)
            if job_id is None:
                wake.wait(0.05)
                wake.clear()
                continue
            self._execute(job_id)

    def _execute(self, job_id: str) -> None:
        record = self._store.get(job_id)
        step = self.steps.get(record.step)
        if step is None:
            self._store.fail(job_id, "Cette étape n'est pas disponible.")
            return
        context = JobContext(
            self._store,
            job_id,
            json.loads(record.inputs_json),
            self._halt,
        )
        try:
            step(context)
        except JobStopped:
            return
        except WorkerHalted:
            return
        except Exception as exc:
            self._store.fail(job_id, str(exc).strip() or "L'étape a échoué.")
            return
        if self._halt.is_set() or self._store.status_of(job_id) != "en_cours":
            return
        self._store.complete(job_id)

    def stop(self, project_id: str, job_id: str) -> Job:
        return self._store.request_stop(project_id, job_id)

    def resume(self, project_id: str, job_id: str) -> Job:
        job = self._store.request_resume(project_id, job_id)
        self._ensure_worker(project_id)
        return job

    def read(self, project_id: str, job_id: str) -> Job:
        return self._store.read(project_id, job_id)

    def latest(self, project_id: str) -> Job:
        return self._store.latest(project_id)

    def events_after(
        self, project_id: str, job_id: str, last_id: int
    ) -> list[JobEvent]:
        self.read(project_id, job_id)
        return self._store.events_after(job_id, last_id)


def _now() -> datetime:
    return datetime.now(UTC)


def _fingerprint(project_id: str, step: str, inputs: Mapping[str, str]) -> str:
    payload = json.dumps(
        {"inputs": dict(inputs), "project_id": project_id, "step": step},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _existing_job(session: Session, key: str) -> Job | None:
    record = session.exec(
        select(JobRecord).where(JobRecord.idempotency_key == key)
    ).first()
    if record is None:
        return None
    return _to_job(record)


def _to_job(record: JobRecord) -> Job:
    if record.status not in {"en_attente", "en_cours", "arrete", "termine", "echec"}:
        raise RuntimeError(f"statut de job inattendu : {record.status}")
    done = json.loads(record.checkpoints_json)
    progress = None
    if record.progress_done is not None and record.progress_total is not None:
        progress = JobProgress(done=record.progress_done, total=record.progress_total)
    return Job(
        id=record.id,
        project_id=record.project_id,
        step=record.step,
        status=record.status,
        checkpoint=done[-1] if done else None,
        progress=progress,
        journal=json.loads(record.journal_json),
        error=record.error,
    )
