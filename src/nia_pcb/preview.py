"""Aperçu 2D/3D lié au projet et à sa version (ticket #22, spec #13).

Stockage local par projet : preview/meta.json, preview/<couche>.svg,
preview/board.glb. Aucune écriture hors du dossier du projet.
"""

import json
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine
from sqlmodel import Session

from nia_pcb.jobs import JobContext
from nia_pcb.projects import ProjectNotFound, ProjectRecord

COUCHES = [
    ("F.Cu", "Cuivre haut"),
    ("B.Cu", "Cuivre bas"),
    ("F.SilkS", "Sérigraphie"),
    ("Edge.Cuts", "Contour"),
]

COUCHE_IDS = [couche_id for couche_id, _ in COUCHES]
COUCHE_LABELS = dict(COUCHES)


class PreviewCouche(BaseModel):
    id: str
    label: str
    svg: str


class PreviewView(BaseModel):
    project_id: str
    version: int = 0
    version_courante: int = 0
    a_jour: bool = True
    layout_a_jour: bool = False
    couches: list[PreviewCouche] = Field(default_factory=list)
    modele_3d_disponible: bool = False
    modele_3d_url: str | None = None
    pieces_sans_modele_3d: list[str] = Field(default_factory=list)
    mis_a_jour_le: str | None = None


class PreviewBuilder(Protocol):
    def build(self, project_dir: Path) -> dict[str, Any]: ...


class SubprocessPreviewBuilder:
    """Adaptateur réel : `kicad-cli pcb export svg` + `glb` dans le conteneur."""

    def __init__(self, timeout_s: int = 120) -> None:
        self._timeout_s = timeout_s

    def build(self, project_dir: Path) -> dict[str, Any]:
        pcb = _trouver_pcb(project_dir)
        if pcb is None:
            raise RuntimeError(
                "Aucun layout KiCad trouvé : lance une construction "
                "avec layout avant de générer l'aperçu."
            )
        kicad = shutil.which("kicad-cli")
        if kicad is None:
            raise RuntimeError(
                "kicad-cli n'est pas installé dans le conteneur : "
                "ajoute KiCad 10.x à l'image avant de générer l'aperçu."
            )
        couches: dict[str, str] = {}
        for couche_id in COUCHE_IDS:
            couches[couche_id] = _exporter_svg(
                kicad, pcb, couche_id, self._timeout_s
            )
        glb = _exporter_glb(kicad, pcb, self._timeout_s)
        manquantes = _lister_sans_modele_3d(project_dir)
        return {
            "couches": couches,
            "glb": glb,
            "pieces_sans_modele_3d": manquantes,
        }


def _trouver_pcb(project_dir: Path) -> Path | None:
    candidats = sorted(project_dir.glob("elec/layout/*.kicad_pcb"))
    if candidats:
        return candidats[0]
    copies = sorted(project_dir.glob("build/**/*.kicad_pcb"))
    if copies:
        return copies[0]
    directs = sorted(project_dir.glob("*.kicad_pcb"))
    if directs:
        return directs[0]
    return None


def _exporter_svg(
    kicad: str, pcb: Path, couche: str, timeout_s: int
) -> str:
    try:
        termine = subprocess.run(
            [
                kicad,
                "pcb",
                "export",
                "svg",
                "--layers",
                couche,
                "-o",
                "-",
                str(pcb),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Export SVG {couche} trop long (dépassement du délai)."
        ) from exc
    if termine.returncode != 0:
        detail = (termine.stderr or termine.stdout or "").strip()[-500:]
        raise RuntimeError(
            f"Export SVG {couche} impossible. " + (detail or "Voir les journaux.")
        )
    svg = termine.stdout.strip()
    if "<svg" not in svg:
        raise RuntimeError(f"Export SVG {couche} vide ou illisible.")
    return svg


def _exporter_glb(kicad: str, pcb: Path, timeout_s: int) -> bytes | None:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as tmp:
        sortie = Path(tmp.name)
    try:
        try:
            termine = subprocess.run(
                [kicad, "pcb", "export", "glb", "-o", str(sortie), str(pcb)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Export GLB trop long (dépassement du délai)."
            ) from exc
        if termine.returncode != 0:
            # GLB manquant : on signale sans bloquer l'aperçu 2D.
            return None
        if not sortie.is_file() or sortie.stat().st_size == 0:
            return None
        return sortie.read_bytes()
    finally:
        try:
            sortie.unlink(missing_ok=True)
        except Exception:
            pass


def _lister_sans_modele_3d(project_dir: Path) -> list[str]:
    # La liste fiable vient de la BOM (has_3d / footprint sans modèle).
    # En l'absence de BOM, on ne ment pas : liste vide.
    bom_candidats = [
        project_dir / "bom.json",
        project_dir / "build" / "bom.json",
    ]
    for candidat in bom_candidats:
        if not candidat.is_file():
            continue
        try:
            donnees = json.loads(candidat.read_text(encoding="utf-8"))
        except Exception:
            continue
        entrees = donnees if isinstance(donnees, list) else donnees.get("entrees", [])
        if not isinstance(entrees, list):
            continue
        manquantes: list[str] = []
        for entree in entrees:
            if not isinstance(entree, dict):
                continue
            reference = str(entree.get("reference", "")).strip()
            if not reference:
                continue
            possede = entree.get("has_3d", entree.get("possede_modele_3d", True))
            if possede is False:
                manquantes.append(reference)
        return sorted(set(manquantes))
    return []


class PreviewStore:
    def __init__(
        self, engine: Engine, base_dir: Path, ato_store: Any = None
    ) -> None:
        self.engine = engine
        self.base_dir = base_dir
        self._ato = ato_store
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _dossier_projet(self, project_id: str) -> Path:
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
        if self._ato is not None:
            return self._ato.project_dir(project_id)
        base = self.base_dir.resolve()
        candidat = (self.base_dir / project_id).resolve()
        if candidat != base and base not in candidat.parents:
            raise ValueError("Chemin hors du dossier du projet.")
        return candidat

    def _dossier_apercu(self, project_id: str) -> Path:
        return self._dossier_projet(project_id) / "preview"

    def _version_courante(self, project_id: str) -> int:
        if self._ato is None:
            return 0
        try:
            return int(self._ato.read(project_id).version)
        except Exception:
            return 0

    def _layout_a_jour(self, project_id: str) -> bool:
        if self._ato is None:
            return False
        try:
            return bool(self._ato.read(project_id).layout_a_jour)
        except Exception:
            return False

    def save(
        self,
        project_id: str,
        version: int,
        couches: dict[str, str],
        glb: bytes | None,
        pieces_sans_modele_3d: list[str],
    ) -> PreviewView:
        dossier = self._dossier_apercu(project_id)
        dossier.mkdir(parents=True, exist_ok=True)
        propres: dict[str, str] = {}
        for couche_id in COUCHE_IDS:
            svg = couches.get(couche_id, "")
            if isinstance(svg, str) and "<svg" in svg:
                propres[couche_id] = svg
                (dossier / f"{couche_id}.svg").write_text(svg, encoding="utf-8")
        if glb:
            (dossier / "board.glb").write_bytes(glb)
        # Sinon on conserve le dernier GLB connu : une régénération
        # 2D-OK / GLB-KO ne doit pas détruire le dernier bon modèle 3D.
        (dossier / "meta.json").write_text(
            json.dumps(
                {
                    "version": int(version),
                    "pieces_sans_modele_3d": sorted(set(pieces_sans_modele_3d)),
                    "mis_a_jour_le": datetime.now(UTC).isoformat(),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return self.read(project_id)

    def read(self, project_id: str) -> PreviewView:
        dossier = self._dossier_apercu(project_id)
        version_courante = self._version_courante(project_id)
        layout = self._layout_a_jour(project_id)
        meta_path = dossier / "meta.json"
        if not meta_path.is_file():
            return PreviewView(
                project_id=project_id,
                version=0,
                version_courante=version_courante,
                a_jour=(0 == version_courante),
                layout_a_jour=layout,
            )
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        version = int(meta.get("version", 0) or 0)
        couches: list[PreviewCouche] = []
        for couche_id in COUCHE_IDS:
            svg_path = dossier / f"{couche_id}.svg"
            if not svg_path.is_file():
                continue
            try:
                svg = svg_path.read_text(encoding="utf-8")
            except Exception:
                continue
            if "<svg" not in svg:
                continue
            couches.append(
                PreviewCouche(
                    id=couche_id,
                    label=COUCHE_LABELS[couche_id],
                    svg=svg,
                )
            )
        glb_path = dossier / "board.glb"
        disponible = glb_path.is_file() and glb_path.stat().st_size > 0
        manquantes = meta.get("pieces_sans_modele_3d", [])
        if not isinstance(manquantes, list):
            manquantes = []
        return PreviewView(
            project_id=project_id,
            version=version,
            version_courante=version_courante,
            a_jour=(version == version_courante),
            layout_a_jour=layout,
            couches=couches,
            modele_3d_disponible=bool(disponible),
            modele_3d_url=(
                f"/api/projects/{project_id}/apercu/modele"
                if disponible
                else None
            ),
            pieces_sans_modele_3d=[str(item) for item in manquantes],
            mis_a_jour_le=meta.get("mis_a_jour_le"),
        )

    def read_glb(self, project_id: str) -> bytes:
        dossier = self._dossier_apercu(project_id)
        glb_path = dossier / "board.glb"
        if not glb_path.is_file():
            raise FileNotFoundError("Aucun modèle 3D pour ce projet.")
        return glb_path.read_bytes()


def make_preview_step(
    store: PreviewStore, builder: PreviewBuilder | None
) -> Callable[[JobContext], None]:
    def run(context: JobContext) -> None:
        actif: PreviewBuilder = builder or SubprocessPreviewBuilder()
        context.log("Recherche du layout pour l'aperçu…")
        context.progress(1, 3)
        dossier = store._dossier_projet(context.project_id)
        try:
            resultat = actif.build(dossier)
        except Exception as exc:
            message = str(exc).strip() or "La génération de l'aperçu a échoué."
            context.log(f"Échec : {message}")
            raise RuntimeError(message) from exc
        couches = resultat.get("couches", {})
        if not isinstance(couches, dict) or not couches:
            raise RuntimeError("La génération n'a produit aucune couche SVG.")
        glb = resultat.get("glb")
        if glb is not None and not isinstance(glb, (bytes, bytearray)):
            raise RuntimeError("Le modèle 3D produit est illisible.")
        manquantes = resultat.get("pieces_sans_modele_3d", [])
        if not isinstance(manquantes, list):
            manquantes = []
        version = store._version_courante(context.project_id)
        context.progress(2, 3)
        context.log(
            f"Aperçu v{version} : {len([c for c in couches if c in COUCHE_IDS])} "
            "couche(s), " + ("GLB prêt." if glb else "sans GLB.")
        )
        store.save(
            context.project_id,
            version,
            {str(k): str(v) for k, v in couches.items()},
            bytes(glb) if glb is not None else None,
            [str(item) for item in manquantes],
        )
        context.set_result(
            {
                "version": version,
                "couches": len(couches),
                "modele_3d": bool(glb),
                "sans_modele_3d": len(manquantes),
            }
        )
        context.progress(3, 3)
        context.log("Aperçu 2D/3D à jour et lié à la version courante.")

    return run
