"""Application HTTP : projets locaux et jobs suivis en direct."""

import asyncio
from collections.abc import AsyncIterable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from nia_pcb.jobs import (
    Job,
    JobContext,
    JobNotFound,
    JobNotResumable,
    JobNotStoppable,
    JobRunner,
    LaunchJob,
    ProjectHasNoJob,
)
from nia_pcb.projects import CreateProject, Project, ProjectNotFound, ProjectStore
from nia_pcb.specification import (
    BoardSpecification,
    Conversation,
    Demand,
    LanguageModel,
    ReadySpecification,
    SpecificationNotEditable,
    SpecificationStore,
    SpecificationView,
    make_specification_step,
)


def create_app(
    database_path: Path,
    steps: dict[str, Callable[[JobContext], None]] | None = None,
    model: LanguageModel | None = None,
) -> FastAPI:
    store = ProjectStore(database_path)
    specifications = SpecificationStore(store.engine)
    registered: dict[str, Callable[[JobContext], None]] = {
        "specification": make_specification_step(specifications, model)
    }
    if steps:
        registered.update(steps)
    jobs = JobRunner(store.engine, registered)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        jobs.start()
        yield
        jobs.halt()
        store.close()

    app = FastAPI(title="NIA PCB", lifespan=lifespan)
    app.state.projects = store
    app.state.jobs = jobs
    app.state.specifications = specifications
    app.include_router(router)
    return app


def get_store(request: Request) -> ProjectStore:
    return request.app.state.projects


def get_jobs(request: Request) -> JobRunner:
    return request.app.state.jobs


def get_specifications(request: Request) -> SpecificationStore:
    return request.app.state.specifications


StoreDep = Annotated[ProjectStore, Depends(get_store)]
JobsDep = Annotated[JobRunner, Depends(get_jobs)]
SpecificationsDep = Annotated[SpecificationStore, Depends(get_specifications)]

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", status_code=201)
def create_project(body: CreateProject, store: StoreDep) -> Project:
    return store.create(body.name)


@router.get("")
def list_projects(store: StoreDep) -> list[Project]:
    return store.list_projects()


@router.post("/{project_id}/demandes", status_code=202)
def submit_demand(project_id: str, body: Demand, jobs: JobsDep) -> Job:
    try:
        return jobs.launch(
            project_id,
            "specification",
            {"text": body.text, "mode": body.mode},
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.get("/{project_id}/specification")
def read_specification(
    project_id: str, specifications: SpecificationsDep
) -> SpecificationView:
    try:
        return specifications.read(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.patch("/{project_id}/specification")
def edit_specification(
    project_id: str, body: BoardSpecification, specifications: SpecificationsDep
) -> ReadySpecification:
    try:
        return specifications.update(project_id, body)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except SpecificationNotEditable:
        raise HTTPException(
            status_code=409,
            detail="La spécification n'est pas encore modifiable.",
        ) from None


@router.get("/{project_id}/conversation")
def read_conversation(
    project_id: str, specifications: SpecificationsDep
) -> Conversation:
    try:
        return specifications.conversation(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.get("/{project_id}")
def open_project(project_id: str, store: StoreDep) -> Project:
    try:
        return store.open(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.post("/{project_id}/jobs", status_code=202)
def launch_job(project_id: str, body: LaunchJob, jobs: JobsDep) -> Job:
    if body.step not in jobs.steps:
        raise HTTPException(status_code=422, detail="Cette étape n'est pas disponible.")
    try:
        return jobs.launch(project_id, body.step, body.inputs)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.get("/{project_id}/jobs/latest")
def latest_job(project_id: str, jobs: JobsDep) -> Job:
    try:
        return jobs.latest(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except ProjectHasNoJob:
        raise HTTPException(
            status_code=404, detail="Ce projet n'a pas de job."
        ) from None


@router.get("/{project_id}/jobs/{job_id}")
def read_job(project_id: str, job_id: str, jobs: JobsDep) -> Job:
    try:
        return jobs.read(project_id, job_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Ce job n'existe pas.") from None


@router.get(
    "/{project_id}/jobs/{job_id}/events",
    response_class=EventSourceResponse,
)
async def stream_job(
    project_id: str, job_id: str, jobs: JobsDep
) -> AsyncIterable[ServerSentEvent]:
    try:
        jobs.read(project_id, job_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Ce job n'existe pas.") from None
    last_id = 0
    while True:
        events = await asyncio.to_thread(jobs.events_after, project_id, job_id, last_id)
        if not events:
            current = await asyncio.to_thread(jobs.read, project_id, job_id)
            if current.status in {"termine", "echec", "arrete"}:
                break
            await asyncio.sleep(0.05)
            continue
        for event in events:
            last_id = event.id
            yield ServerSentEvent(
                data=event.payload,
                event=event.kind,
                id=str(event.id),
            )


@router.post("/{project_id}/jobs/{job_id}/stop")
def stop_job(project_id: str, job_id: str, jobs: JobsDep) -> Job:
    try:
        return jobs.stop(project_id, job_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Ce job n'existe pas.") from None
    except JobNotStoppable:
        raise HTTPException(
            status_code=409, detail="Ce job ne peut pas être arrêté."
        ) from None


@router.post("/{project_id}/jobs/{job_id}/resume")
def resume_job(project_id: str, job_id: str, jobs: JobsDep) -> Job:
    try:
        return jobs.resume(project_id, job_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Ce job n'existe pas.") from None
    except JobNotResumable:
        raise HTTPException(
            status_code=409, detail="Ce job ne peut pas être repris."
        ) from None
