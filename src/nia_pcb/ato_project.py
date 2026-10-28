"""Projet atopile initial qui se construit (ticket #19, spec #13).

Stockage local par projet : main.ato, ato.yaml, bom.json, build.json.
Aucune écriture hors du dossier du projet. Versions git locales best-effort
+ table SQLite pour la première version enregistrée localement.
"""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, field_validator
from sqlalchemy.engine import Engine
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel, col, func, select

from nia_pcb.jobs import JobContext
from nia_pcb.projects import ProjectNotFound, ProjectRecord


def projects_base_dir(database_path: Path) -> Path:
    override = os.environ.get("NIA_PROJECTS", "").strip()
    if override:
        return Path(override)
    return database_path.resolve().parent / "projects"


class AtoBuilder(Protocol):
    def build(self, project_dir: Path) -> dict[str, Any]: ...


class SubprocessAtoBuilder:
    """Adaptateur réel : `ato build` dans le conteneur."""

    def __init__(self, target: str = "rapide", timeout_s: int = 120) -> None:
        self._target = target
        self._timeout_s = timeout_s

    def build(self, project_dir: Path) -> dict[str, Any]:
        ato = shutil.which("ato")
        if ato is None:
            raise RuntimeError(
                "atopile n'est pas installé dans le conteneur : "
                "ajoute atopile + KiCad 10.x à l'image avant de construire."
            )
        try:
            completed = subprocess.run(
                [ato, "build", "--target", self._target],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("La construction atopile a dépassé le délai.") from exc
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip()[-2000:]
            raise RuntimeError(
                "La construction atopile a échoué. " + (tail or "Voir les journaux.")
            )
        bom = _read_bom_after_build(project_dir)
        return {"bom": bom, "layout_updated": True}


def _read_bom_after_build(project_dir: Path) -> list[dict[str, Any]]:
    for candidate in [
        project_dir / "build" / "bom.json",
        project_dir / "bom.json",
    ]:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and isinstance(data.get("entrees"), list):
                    return data["entrees"]
            except Exception:
                continue
    # Sans artefact BOM lisible, on explique au lieu de mentir.
    raise RuntimeError(
        "Construction terminée mais BOM introuvable : "
        "vérifie la cible rapide (manifest/BOM/layout) du projet."
    )


class AtoView(BaseModel):
    project_id: str
    existe: bool = False
    code: str = ""
    version: int = 0
    mis_a_jour_le: str | None = None
    layout_a_jour: bool = False


class AtoVersions(BaseModel):
    project_id: str
    versions: list[dict[str, Any]] = []


class BomView(BaseModel):
    project_id: str
    entrees: list[dict[str, Any]] = []
    mis_a_jour_le: str | None = None


class WriteAto(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le code .ato est vide.")
        if len(value) > 200_000:
            raise ValueError("Le code .ato tient en 200 000 caractères maximum.")
        return value


class WriteAtoFile(BaseModel):
    chemin: str
    code: str

    @field_validator("chemin")
    @classmethod
    def clean_path(cls, value: str) -> str:
        cleaned = value.strip().replace("\\", "/")
        if not cleaned:
            raise ValueError("Indique un chemin.")
        return cleaned

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le code .ato est vide.")
        return value


class AtoVersionRecord(SQLModel, table=True):
    __tablename__ = "ato_versions"

    id: int | None = SqlField(default=None, primary_key=True)
    project_id: str = SqlField(foreign_key="projects.id", index=True)
    version: int
    message: str = ""
    created_at: datetime


class AtoStore:
    def __init__(self, engine: Engine, base_dir: Path) -> None:
        self.engine = engine
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        candidate = (self.base_dir / project_id).resolve()
        base = self.base_dir.resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError("Chemin hors du dossier du projet.")
        return candidate

    def _require_project(self, project_id: str) -> Path:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
        return self.project_dir(project_id)

    def resolve_inside(self, project_id: str, relative: str) -> Path:
        project_dir = self._require_project(project_id)
        cleaned = relative.strip().replace("\\", "/")
        if not cleaned or cleaned.startswith("/") or ".." in cleaned.split("/"):
            raise ValueError("Écriture refusée : hors du dossier du projet.")
        candidate = (project_dir / cleaned).resolve()
        if candidate != project_dir and project_dir not in candidate.parents:
            raise ValueError("Écriture refusée : hors du dossier du projet.")
        return candidate

    def read(self, project_id: str) -> AtoView:
        project_dir = self._require_project(project_id)
        main = project_dir / "main.ato"
        if not main.is_file():
            return AtoView(project_id=project_id)
        version = self._latest_version(project_id)
        build = self._read_build(project_dir)
        return AtoView(
            project_id=project_id,
            existe=True,
            code=main.read_text(encoding="utf-8"),
            version=version,
            mis_a_jour_le=_iso(main.stat().st_mtime),
            layout_a_jour=bool(build.get("layout_updated", False)),
        )

    def write(self, project_id: str, code: str, message: str = "") -> AtoView:
        body = WriteAto(code=code)
        project_dir = self._require_project(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.ato").write_text(body.code, encoding="utf-8")
        ato_yaml = project_dir / "ato.yaml"
        if not ato_yaml.is_file():
            ato_yaml.write_text(_ATO_YAML, encoding="utf-8")
        version = self._record_version(project_id, message or "Écriture du .ato")
        _git_commit_best_effort(project_dir, message or f"ato v{version}")
        return self.read(project_id)

    def write_file(self, project_id: str, relative: str, code: str) -> AtoView:
        body = WriteAtoFile(chemin=relative, code=code)
        target = self.resolve_inside(project_id, body.chemin)
        if target.suffix != ".ato":
            raise ValueError("Seuls les fichiers .ato sont acceptés.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.code, encoding="utf-8")
        version = self._record_version(project_id, f"Écriture {body.chemin}")
        _git_commit_best_effort(
            self.project_dir(project_id), f"ato v{version} {body.chemin}"
        )
        return self.read(project_id)

    def ensure_initial(self, project_id: str) -> AtoView:
        view = self.read(project_id)
        if view.existe:
            return view
        return self.write(project_id, _INITIAL_ATO, "Projet atopile initial")

    def versions(self, project_id: str) -> AtoVersions:
        self._require_project(project_id)
        with Session(self.engine) as session:
            rows = session.exec(
                select(AtoVersionRecord)
                .where(AtoVersionRecord.project_id == project_id)
                .order_by(col(AtoVersionRecord.version))
            ).all()
            return AtoVersions(
                project_id=project_id,
                versions=[
                    {
                        "version": row.version,
                        "message": row.message,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ],
            )

    def save_build(
        self, project_id: str, bom: list[dict[str, Any]], layout_updated: bool
    ) -> None:
        project_dir = self._require_project(project_id)
        (project_dir / "bom.json").write_text(
            json.dumps(bom, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (project_dir / "build.json").write_text(
            json.dumps(
                {
                    "layout_updated": layout_updated,
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def read_bom(self, project_id: str) -> BomView:
        project_dir = self._require_project(project_id)
        bom_file = project_dir / "bom.json"
        if not bom_file.is_file():
            return BomView(project_id=project_id)
        try:
            entries = json.loads(bom_file.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []
        return BomView(
            project_id=project_id,
            entrees=entries,
            mis_a_jour_le=_iso(bom_file.stat().st_mtime),
        )

    def _latest_version(self, project_id: str) -> int:
        with Session(self.engine) as session:
            return _max_version(session, project_id)

    def _record_version(self, project_id: str, message: str) -> int:
        with Session(self.engine) as session:
            nxt = _max_version(session, project_id) + 1
            session.add(
                AtoVersionRecord(
                    project_id=project_id,
                    version=nxt,
                    message=message[:500],
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
            return nxt

    def _read_build(self, project_dir: Path) -> dict[str, Any]:
        build_file = project_dir / "build.json"
        if not build_file.is_file():
            return {}
        try:
            data = json.loads(build_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def make_ato_build_step(
    store: AtoStore, builder: AtoBuilder | None
) -> Any:
    def run(context: JobContext) -> None:
        active: AtoBuilder = builder or SubprocessAtoBuilder()
        context.log("Lecture du projet atopile…")
        view = store.ensure_initial(context.project_id)
        context.log(f"Projet atopile v{view.version} : construction rapide…")
        context.progress(1, 3)
        try:
            outcome = active.build(store.project_dir(context.project_id))
        except Exception as exc:
            message = str(exc).strip() or "La construction a échoué."
            context.log(f"Échec : {message}")
            raise RuntimeError(message) from exc
        bom = outcome.get("bom", [])
        if not isinstance(bom, list):
            raise RuntimeError("La construction n'a pas produit de BOM lisible.")
        layout = bool(outcome.get("layout_updated", False))
        store.save_build(context.project_id, bom, layout)
        context.set_result({"bom": len(bom), "layout_updated": layout})
        context.progress(3, 3)
        context.log(
            f"Construction rapide : BOM {len(bom)} ligne(s), "
            + ("layout à jour." if layout else "layout inchangé.")
        )

    return run


def _iso(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, UTC).isoformat()


def _max_version(session: Session, project_id: str) -> int:
    value = session.exec(
        select(func.coalesce(func.max(AtoVersionRecord.version), 0)).where(
            AtoVersionRecord.project_id == project_id
        )
    ).one()
    return int(value or 0)


def _git_commit_best_effort(project_dir: Path, message: str) -> None:
    git = shutil.which("git")
    if git is None:
        return
    try:
        if not (project_dir / ".git").exists():
            subprocess.run(
                [git, "init", "-q"],
                cwd=str(project_dir),
                capture_output=True,
                timeout=10,
            )
        subprocess.run(
            [git, "add", "main.ato", "ato.yaml"],
            cwd=str(project_dir),
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            [git, "-c", "user.name=nia", "-c", "user.email=nia@local", "commit", "-q",
             "-m", message],
            cwd=str(project_dir),
            capture_output=True,
            timeout=10,
        )
    except Exception:
        return


_INITIAL_ATO = '''#pragma experiment("BRIDGE_CONNECT")

import ElectricPower
import Resistor
import Capacitor

module Top:
    """Carte initiale NIA : rail 3V3 découplé, prête pour `ato build`.

    Requirements:
    - R1: Rail 3V3 découplé près des charges.
    """

    power_3v3 = new ElectricPower
    assert power_3v3.voltage within 3.3V +/- 5%

    decoup_100n = new Capacitor
    decoup_100n.capacitance = 100nF +/- 20%
    decoup_100n.package = "0402"
    power_3v3.hv ~> decoup_100n ~> power_3v3.lv

    decoup_1u = new Capacitor
    decoup_1u.capacitance = 1uF +/- 20%
    decoup_1u.package = "0603"
    power_3v3.hv ~> decoup_1u ~> power_3v3.lv

    pull_10k = new Resistor
    pull_10k.resistance = 10kohm +/- 5%
    pull_10k.package = "0402"
    power_3v3.hv ~> pull_10k ~> power_3v3.lv
'''

_ATO_YAML = """# Projet atopile NIA PCB (ticket #19).
entrypoint: main.ato
targets:
  rapide:
    description: BOM, manifest, variables, datasheets et layout à jour.
"""
