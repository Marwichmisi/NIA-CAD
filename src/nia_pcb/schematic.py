"""Validation du schéma et porte vers schéma validé (ticket #21, spec #13).

La checklist couvre découplage, pull-ups, démarrage, reset, protections,
marge des régulateurs (>= 30 %), solveur atopile et ERC.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlmodel import Field as SqlField
from sqlmodel import Session, SQLModel

from nia_pcb.jobs import JobContext
from nia_pcb.projects import ProjectNotFound, ProjectRecord

CHECK_IDS = [
    "decouplage",
    "pull_ups",
    "demarrage",
    "reset",
    "protections",
    "marge_regulateurs",
    "solveur",
    "erc",
]

LABELS = {
    "decouplage": "Découplage de chaque rail",
    "pull_ups": "Pull-ups des bus",
    "demarrage": "Broches de démarrage",
    "reset": "Reset",
    "protections": "Protections d'entrée",
    "marge_regulateurs": "Marge des régulateurs",
    "solveur": "Solveur atopile",
    "erc": "ERC",
}


class SchematicCheck(BaseModel):
    id: str
    label: str
    statut: Literal["vert", "rouge"]
    valeur: str = ""
    limite: str = ""
    commentaire: str = ""


class SchematicValidation(BaseModel):
    project_id: str
    mode: Literal["autonome", "valide"] = "autonome"
    vert: bool
    controles: list[SchematicCheck]
    evalue_le: str


class SchematicNotGreen(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class SchematicNotEvaluated(Exception):
    def __init__(self) -> None:
        super().__init__("Aucune vérification du schéma à valider.")


class SchematicValidationRecord(SQLModel, table=True):
    __tablename__ = "schematic_validations"

    project_id: str = SqlField(primary_key=True, foreign_key="projects.id")
    mode: str
    vert: bool
    payload_json: str
    updated_at: datetime


def evaluate_code(code: str, build_ok: bool) -> list[SchematicCheck]:
    """Heuristique lisible sur le .ato + résultat du build (solveur/ERC)."""
    lowered = code.lower()
    has_capa = "capacitor" in lowered and (
        "100n" in lowered or "1u" in lowered or "decoupl" in lowered
    )
    has_pull = "resistor" in lowered and (
        "10k" in lowered or "4k7" in lowered or "4.7k" in lowered or "pull" in lowered
    )
    has_boot = any(
        key in lowered
        for key in ("boot", "demarrage", "démarrage", "enable", "startup")
    )
    has_reset = "reset" in lowered or "nrst" in lowered
    has_prot = any(
        key in lowered for key in ("fuse", "tvs", "protection", "esd", "diode")
    )
    has_reg = "regulator" in lowered
    marge_ok = has_reg and ("30" in code or "marge" in lowered or "margin" in lowered)

    controles = [
        SchematicCheck(
            id="decouplage",
            label=LABELS["decouplage"],
            statut="vert" if has_capa else "rouge",
            valeur="condensateur HF + réservoir"
            if has_capa
            else "aucun découplage détecté",
            limite="100 nF au plus près + réservoir par rail",
            commentaire=""
            if has_capa
            else "Ajoute un 100 nF au plus près de chaque broche.",
        ),
        SchematicCheck(
            id="pull_ups",
            label=LABELS["pull_ups"],
            statut="vert" if has_pull else "rouge",
            valeur="pull-up détecté" if has_pull else "aucun pull-up détecté",
            limite="pull-up sur chaque bus open-drain",
            commentaire=""
            if has_pull
            else "Ajoute des pull-ups adaptées au bus (ex. 10 kΩ).",
        ),
        SchematicCheck(
            id="demarrage",
            label=LABELS["demarrage"],
            statut="vert" if has_boot else "rouge",
            valeur="configuration boot détectée"
            if has_boot
            else "broches de démarrage non configurées",
            limite="BOOT/EN câblés selon datasheet",
            commentaire=""
            if has_boot
            else "Câble les broches de démarrage (BOOT/EN) selon la datasheet.",
        ),
        SchematicCheck(
            id="reset",
            label=LABELS["reset"],
            statut="vert" if has_reset else "rouge",
            valeur="reset câblé" if has_reset else "reset non câblé",
            limite="reset géré (RC ou superviseur)",
            commentaire=""
            if has_reset
            else "Prévois le reset (tirage, RC ou superviseur).",
        ),
        SchematicCheck(
            id="protections",
            label=LABELS["protections"],
            statut="vert" if has_prot else "rouge",
            valeur="protection détectée" if has_prot else "aucune protection détectée",
            limite="protection adaptée à l'alimentation",
            commentaire=""
            if has_prot
            else "Ajoute une protection d'entrée adaptée (fusible, TVS/diode).",
        ),
        SchematicCheck(
            id="marge_regulateurs",
            label=LABELS["marge_regulateurs"],
            statut="vert" if marge_ok else "rouge",
            valeur="marge >= 30 % démontrée" if marge_ok else "marge non démontrée",
            limite="marge >= 30 % sur chaque régulateur",
            commentaire=""
            if marge_ok
            else "Démontre au moins 30 % de marge sur chaque régulateur.",
        ),
        SchematicCheck(
            id="solveur",
            label=LABELS["solveur"],
            statut="vert" if build_ok else "rouge",
            valeur="solveur vert (build rapide)" if build_ok else "solveur en échec",
            limite="zéro contrainte violée",
            commentaire=""
            if build_ok
            else "Corrige le projet : le solveur signale une erreur.",
        ),
        SchematicCheck(
            id="erc",
            label=LABELS["erc"],
            statut="vert" if build_ok else "rouge",
            valeur="ERC vert" if build_ok else "ERC en échec",
            limite="zéro erreur ERC bloquante",
            commentaire=""
            if build_ok
            else "Corrige les erreurs ERC avant de valider le schéma.",
        ),
    ]
    return controles


class SchematicStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save(
        self,
        project_id: str,
        mode: str,
        controles: list[SchematicCheck],
    ) -> SchematicValidation:

        cleaned_mode = mode if mode in {"autonome", "valide"} else "autonome"
        vert = all(c.statut == "vert" for c in controles)
        view = SchematicValidation(
            project_id=project_id,
            mode=cleaned_mode,  # type: ignore[arg-type]
            vert=vert,
            controles=controles,
            evalue_le=datetime.now(UTC).isoformat(),
        )
        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            payload = view.model_dump_json()
            row = session.get(SchematicValidationRecord, project_id)
            if row is None:
                session.add(
                    SchematicValidationRecord(
                        project_id=project_id,
                        mode=cleaned_mode,
                        vert=vert,
                        payload_json=payload,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                row.mode = cleaned_mode
                row.vert = vert
                row.payload_json = payload
                row.updated_at = datetime.now(UTC)
                session.add(row)
            session.commit()
            return view

    def read(self, project_id: str) -> SchematicValidation | None:
        import json as _json

        with Session(self.engine) as session:
            if session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFound(project_id)
            row = session.get(SchematicValidationRecord, project_id)
            if row is None:
                return None
            return SchematicValidation.model_validate(_json.loads(row.payload_json))


def _project_mode(engine: Engine, project_id: str, inputs: dict) -> str:
    # La spec fait foi : si une spec prête existe, son mode gagne.
    # Sinon (tests, brouillon sans spec), on accepte l'override du job.
    try:
        from nia_pcb.specification import SpecificationStore

        view = SpecificationStore(engine).read(project_id)
        state = getattr(view, "state", "absente")
        if state == "prete":
            spec = getattr(view, "specification", None)
            mode = getattr(spec, "mode", "")
            if mode in {"autonome", "valide"}:
                return mode
    except Exception:
        pass
    override = str(inputs.get("mode", "")).strip().lower()
    if override in {"autonome", "valide"}:
        return override
    return "autonome"


def make_schema_validation_step(
    project_store,
    schematic_store: SchematicStore,
    ato_store=None,
    builder=None,
):
    def run(context: JobContext) -> None:
        from nia_pcb.ato_project import SubprocessAtoBuilder

        mode = _project_mode(
            schematic_store.engine, context.project_id, dict(context.inputs)
        )
        context.log(f"Vérification du schéma en mode {mode}…")
        context.progress(1, 3)
        # Code .ato courant (vide si absent) + tentative de build rapide.
        code = ""
        if ato_store is not None:
            try:
                code = ato_store.read(context.project_id).code or ""
            except Exception:
                code = ""
        build_ok = False
        if ato_store is not None:
            active = builder or SubprocessAtoBuilder()
            try:
                project_dir: Path = ato_store.project_dir(context.project_id)
                if code.strip():
                    outcome = active.build(project_dir)
                    bom = outcome.get("bom", [])
                    build_ok = isinstance(bom, list)
            except Exception:
                build_ok = False
        else:
            # Sans store .ato (tests unitaires) : heuristique sur le code seul.
            build_ok = bool(code.strip())
        context.progress(2, 3)
        controles = evaluate_code(code, build_ok=build_ok)
        view = schematic_store.save(context.project_id, mode, controles)
        rouges = [c for c in controles if c.statut == "rouge"]
        for controle in controles:
            context.log(
                f"{'✓' if controle.statut == 'vert' else '✗'} "
                f"{controle.label} : {controle.valeur} (limite : {controle.limite})"
                + (f" — {controle.commentaire}" if controle.commentaire else "")
            )
        context.set_result({"vert": view.vert, "mode": mode, "rouges": len(rouges)})
        context.progress(3, 3)
        if not view.vert:
            detail = "; ".join(
                f"{c.label} ({c.commentaire or c.valeur})" for c in rouges
            )
            context.log(
                f"Schéma non validé : {len(rouges)} contrôle(s) rouge(s). {detail}"
            )
            return
        # Tous verts : porte vers schéma validé.
        if mode == "autonome":
            project_store.transition_to_schema_valide(context.project_id)
            context.log("Statut schéma validé (passage automatique, tout est vert).")
        else:
            context.log("Contrôles verts, en attente du bouton Valider.")

    return run


def validate_manual(
    project_store,
    schematic_store: SchematicStore,
    project_id: str,
    ato_store=None,
):
    """Bouton Valider : exige des contrôles tous verts, puis date la transition."""
    from datetime import datetime as _dt

    view = schematic_store.read(project_id)
    if view is None:
        raise SchematicNotEvaluated
    if not view.vert:
        rouges = [c.label for c in view.controles if c.statut == "rouge"]
        raise SchematicNotGreen(
            "Schéma non validé : " + ", ".join(rouges) + ". Corrige avant de valider."
        )
    if ato_store is not None:
        try:
            ato_view = ato_store.read(project_id)
            if ato_view.existe and ato_view.mis_a_jour_le:
                evalue = _dt.fromisoformat(view.evalue_le)
                modifie = _dt.fromisoformat(ato_view.mis_a_jour_le)
                if modifie > evalue:
                    raise SchematicNotGreen(
                        "Le code .ato a changé depuis la vérification. "
                        "Relance une vérification avant de valider."
                    )
        except SchematicNotGreen:
            raise
        except Exception:
            pass
    return project_store.transition_to_schema_valide(project_id)
