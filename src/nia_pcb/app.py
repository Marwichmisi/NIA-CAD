"""Application HTTP : projets locaux et jobs suivis en direct."""

import asyncio
from collections.abc import AsyncIterable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from nia_pcb.costs import CostStore, CostsTotals, CostSummary, RecordCost
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
from nia_pcb.parts_store import (
    PartsNotFound,
    PartsRequest,
    PartsStore,
    PartsView,
    make_parts_step,
)
from nia_pcb.projects import CreateProject, Project, ProjectNotFound, ProjectStore
from nia_pcb.settings import PublicSettings, SettingsStore, SettingsUpdate
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
    catalog=None,
) -> FastAPI:
    # Import tardif : enregistre la table parts_lists avant create_all.
    from nia_pcb import parts_store as _parts_store_module  # noqa: F401
    from nia_pcb.parts_catalog import CachedCatalog, JlcsearchCatalog

    store = ProjectStore(database_path)
    specifications = SpecificationStore(store.engine)
    parts = PartsStore(store.engine)
    default_catalog = CachedCatalog(catalog or JlcsearchCatalog())
    registered: dict[str, Callable[[JobContext], None]] = {
        "specification": make_specification_step(specifications, model),
        "pieces": make_parts_step(parts, default_catalog),
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
    app.state.parts = parts
    app.state.settings = SettingsStore(store.engine)
    app.state.costs = CostStore(store.engine)
    app.include_router(router)
    app.include_router(settings_router)
    app.include_router(costs_router)
    return app


def get_store(request: Request) -> ProjectStore:
    return request.app.state.projects


def get_jobs(request: Request) -> JobRunner:
    return request.app.state.jobs


def get_specifications(request: Request) -> SpecificationStore:
    return request.app.state.specifications


def get_settings(request: Request) -> SettingsStore:
    return request.app.state.settings


def get_costs(request: Request) -> CostStore:
    return request.app.state.costs


def get_parts(request: Request) -> PartsStore:
    return request.app.state.parts


StoreDep = Annotated[ProjectStore, Depends(get_store)]
JobsDep = Annotated[JobRunner, Depends(get_jobs)]
SpecificationsDep = Annotated[SpecificationStore, Depends(get_specifications)]
SettingsDep = Annotated[SettingsStore, Depends(get_settings)]
CostsDep = Annotated[CostStore, Depends(get_costs)]
PartsDep = Annotated[PartsStore, Depends(get_parts)]

router = APIRouter(prefix="/api/projects", tags=["projects"])

settings_router = APIRouter(prefix="/api/settings", tags=["settings"])

costs_router = APIRouter(prefix="/api/costs", tags=["costs"])


@settings_router.get("")
def read_settings(settings: SettingsDep) -> PublicSettings:
    return settings.get()


@settings_router.put("")
def update_settings(body: SettingsUpdate, settings: SettingsDep) -> PublicSettings:
    return settings.update(body)


@settings_router.post("/reset")
def reset_settings(settings: SettingsDep) -> PublicSettings:
    return settings.reset()


@costs_router.get("")
def read_totals(costs: CostsDep, store: StoreDep) -> CostsTotals:
    total_tokens, total_cost = costs.totals()
    breakdown = costs.per_project()
    names = {project.id: project.name for project in store.list_projects()}
    return CostsTotals(
        total_tokens=total_tokens,
        total_cost=total_cost,
        projects=[
            {
                "project_id": str(item["project_id"]),
                "project_name": names.get(str(item["project_id"]), ""),
                "tokens": int(item["tokens"]),
                "cost": float(item["cost"]),
            }
            for item in breakdown
        ],
    )


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


@router.get("/{project_id}/costs")
def read_costs(project_id: str, costs: CostsDep) -> CostSummary:
    try:
        return costs.summary(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.post("/{project_id}/costs", status_code=201)
def add_costs(project_id: str, body: RecordCost, costs: CostsDep) -> CostSummary:
    try:
        return costs.record(project_id, body.tokens, body.cost_eur, body.note)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.post("/{project_id}/pieces/rechercher", status_code=202)
def search_parts(
    project_id: str, body: PartsRequest, jobs: JobsDep, store: StoreDep
) -> Job:
    try:
        store.open(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    if "pieces" not in jobs.steps:
        raise HTTPException(status_code=422, detail="Cette étape n'est pas disponible.")
    try:
        return jobs.launch(
            project_id,
            "pieces",
            {"exigences": _exigences_json(body)},
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.get("/{project_id}/pieces")
def read_parts(project_id: str, parts: PartsDep) -> PartsView:
    try:
        return parts.read(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None


@router.post("/{project_id}/pieces/valider")
def validate_parts(project_id: str, parts: PartsDep) -> PartsView:
    try:
        return parts.validate(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
    except PartsNotFound:
        raise HTTPException(
            status_code=409, detail="Aucune liste de pièces à valider."
        ) from None


def _exigences_json(body: PartsRequest) -> str:
    import json as _json

    return _json.dumps([item.model_dump() for item in body.exigences])
