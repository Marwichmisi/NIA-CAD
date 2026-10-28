"""Application HTTP : créer, lister et rouvrir un projet."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request

from nia_pcb.projects import CreateProject, Project, ProjectNotFound, ProjectStore


def create_app(database_path: Path) -> FastAPI:
    store = ProjectStore(database_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        store.close()

    app = FastAPI(title="NIA PCB", lifespan=lifespan)
    app.state.projects = store
    app.include_router(router)
    return app


def get_store(request: Request) -> ProjectStore:
    return request.app.state.projects


StoreDep = Annotated[ProjectStore, Depends(get_store)]

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", status_code=201)
def create_project(body: CreateProject, store: StoreDep) -> Project:
    return store.create(body.name)


@router.get("")
def list_projects(store: StoreDep) -> list[Project]:
    return store.list_projects()


@router.get("/{project_id}")
def open_project(project_id: str, store: StoreDep) -> Project:
    try:
        return store.open(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail="Ce projet n'existe pas.") from None
