"""Boucle contrôlée de correction atopile (ticket #20, spec #13).

Chaque échec de `ato build` déclenche une proposition de fix qui est
enregistrée comme nouvelle version locale. Arrêts propres : succès,
plafond configurable (30 par défaut), budget, arrêt manuel, erreur
irrécupérable. Rapport final en français. Diff affiché avant application
en mode validé, après en mode autonome.
Seam DRC : `extra_checks` optionnel, point d'extension pour ticket #24.
"""

import difflib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from nia_pcb.ato_project import AtoBuilder, AtoStore, SubprocessAtoBuilder
from nia_pcb.jobs import JobContext


class AtoUnrecoverable(Exception):
    """Le fix est impossible, il faut arrêter proprement."""


class AtoFixer(Protocol):
    def propose_fix(self, code: str, erreur: str, tentative: int) -> str: ...


def _prompt_path() -> Path:
    override = os.environ.get("NIA_PROMPTS", "").strip()
    if override:
        return Path(override) / "ato_fix.md"
    return Path(__file__).resolve().parents[2] / "prompts" / "ato_fix.md"


class LlmAtoFixer:
    """Adaptateur LLM : propose un fichier main.ato corrigé complet."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def propose_fix(self, code: str, erreur: str, tentative: int) -> str:
        path = _prompt_path()
        if not path.is_file():
            raise RuntimeError("Le gabarit de correction .ato est introuvable.")
        template = path.read_text(encoding="utf-8")
        prompt = (
            template.replace("{code}", code)
            .replace("{erreur}", erreur)
            .replace("{tentative}", str(tentative))
        )
        try:
            raw = self._model.complete(prompt)
        except AtoUnrecoverable:
            raise
        except Exception as exc:
            raise RuntimeError("Le modèle n'a pas répondu.") from exc
        fixed = _extract_code(raw)
        if not fixed.strip():
            raise RuntimeError("Le modèle n'a pas proposé de correction exploitable.")
        return fixed


def _extract_code(raw: str) -> str:
    text = raw.strip()
    if text.upper().startswith("IRRECUPERABLE:"):
        raise AtoUnrecoverable(text.split(":", 1)[1].strip() or "correction impossible")
    if "```" in text:
        # Prend le premier bloc fencé, avec ou sans langage.
        parts = text.split("```")
        for chunk in parts[1::2]:
            body = chunk.strip()
            # Retire une éventuelle première ligne de langage (ato, txt...).
            lines = body.splitlines()
            if lines and lines[0].strip().lower() in {"ato", ".ato", "text", "txt"}:
                body = "\n".join(lines[1:])
            if body.strip():
                return body.strip()
        return ""
    return text


def _diff(old: str, new: str, limit: int = 4000) -> str:
    lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="avant (main.ato)",
            tofile="après (main.ato)",
            lineterm="",
        )
    )
    body = "\n".join(lines).strip()
    if not body:
        return "(aucune différence visible)"
    if len(body) > limit:
        return body[:limit] + "\n…(diff tronqué)"
    return body


def _parse_max_iterations(inputs: dict[str, str], default: int) -> int:
    raw = inputs.get("max_iterations", "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            raise RuntimeError("Le plafond d'itérations doit être un entier positif.")
        if value <= 0 or value > 100:
            raise RuntimeError("Le plafond d'itérations doit être entre 1 et 100.")
        return value
    if default <= 0:
        return 30
    return min(default, 100)


def _over_budget_explicit(inputs: dict[str, str]) -> bool:
    raw = inputs.get("allow_over_budget")
    if raw is True:  # type: ignore[comparison-overlap]
        return True
    return str(raw or "").strip().lower() in {"true", "1", "oui", "yes"}


def make_ato_fix_step(
    store: AtoStore,
    builder: AtoBuilder | None,
    fixer: AtoFixer | None = None,
    engine: Any = None,
    extra_checks: list[Callable[[Path], None]] | None = None,
) -> Any:
    checks = list(extra_checks or [])

    def run(context: JobContext) -> None:
        active_builder: AtoBuilder = builder or SubprocessAtoBuilder()
        active_fixer = fixer
        if active_fixer is None:
            # Le modèle est injecté via create_app ; sans modèle, on échoue en français.
            raise RuntimeError(
                "Aucun modèle n'est configuré pour corriger le projet. "
                "Configure la clé LLM puis relance."
            )
        # Plafond : réglage global, surcharge possible par job.
        default_max = 30
        if engine is not None:
            try:
                from nia_pcb.settings import SettingsStore

                default_max = SettingsStore(engine).get().ato_max_iterations
            except Exception:
                default_max = 30
        max_iterations = _parse_max_iterations(context.inputs, default_max)
        mode = context.inputs.get("mode", "autonome").strip().lower()
        if mode not in {"autonome", "valide"}:
            mode = "autonome"

        context.log(f"Correction en boucle contrôlée : plafond {max_iterations}.")
        view = store.ensure_initial(context.project_id)
        current = view.code
        project_dir = store.project_dir(context.project_id)
        last_error = ""
        override_signale = False

        for tentative in range(1, max_iterations + 1):
            context.abort_if_requested()
            if engine is not None:
                try:
                    from nia_pcb.costs import CostStore

                    if CostStore(engine).summary(context.project_id).over_budget:
                        if not _over_budget_explicit(context.inputs):
                            raise RuntimeError(
                                "Budget projet dépassé. "
                                "Relance avec un dépassement explicite "
                                "ou augmente le budget."
                            )
                        if not override_signale:
                            context.log("Dépassement budgétaire autorisé manuellement.")
                            override_signale = True
                except RuntimeError:
                    raise
                except Exception:
                    # Budget illisible : on continue, la garde reste au démarrage.
                    pass
            context.log(f"Tentative {tentative}/{max_iterations} : construction…")
            context.progress(tentative - 1, max_iterations)
            try:
                outcome = active_builder.build(project_dir)
                bom = outcome.get("bom", [])
                if not isinstance(bom, list):
                    raise RuntimeError(
                        "La construction n'a pas produit de BOM lisible."
                    )
                for check in checks:
                    check(project_dir)
                layout = bool(outcome.get("layout_updated", False))
                store.save_build(context.project_id, bom, layout)
            except Exception as exc:
                # Arrêt manuel : on laisse le runner marquer arrete.
                from nia_pcb.jobs import JobStopped, WorkerHalted

                if isinstance(exc, (JobStopped, WorkerHalted)):
                    raise
                # Budget levé ci-dessus : on propage tel quel.
                message = str(exc).strip()
                if message.startswith("Budget projet dépassé"):
                    raise
                last_error = message or "La construction a échoué."
                context.log(f"Échec tentative {tentative} : {last_error}")
                if tentative >= max_iterations:
                    break
                context.abort_if_requested()
                try:
                    nouveau = active_fixer.propose_fix(current, last_error, tentative)
                except AtoUnrecoverable as ue:
                    detail = str(ue).strip() or "cause inconnue"
                    raise RuntimeError(
                        "Correction impossible (erreur irrécupérable) : "
                        f"{detail}. Reprends le code .ato à la main, "
                        "vérifie les imports et les empreintes."
                    ) from ue
                except RuntimeError:
                    raise
                except Exception as fexc:
                    raise RuntimeError(
                        "Le modèle n'a pas proposé de correction exploitable : "
                        f"{str(fexc).strip() or 'réessaie'}. "
                        "Reprends le code .ato à la main."
                    ) from fexc
                if not nouveau.strip():
                    raise RuntimeError(
                        "Correction impossible (erreur irrécupérable) : "
                        "le modèle propose un code vide. "
                        "Reprends le code .ato à la main."
                    )
                if nouveau.strip() == current.strip():
                    raise RuntimeError(
                        "Correction impossible (erreur irrécupérable) : "
                        "le modèle propose un code identique. "
                        "Reprends le code .ato à la main."
                    )
                diff = _diff(current, nouveau)
                if mode == "valide":
                    context.log(
                        "Proposition de correction "
                        f"(tentative {tentative}, avant application) :\n{diff}"
                    )
                written = store.write(
                    context.project_id,
                    nouveau,
                    f"Correction ato tentative {tentative} : {last_error[:200]}",
                )
                current = written.code
                project_dir = store.project_dir(context.project_id)
                if mode != "valide":
                    context.log(
                        "Correction appliquée "
                        f"(tentative {tentative}, v{written.version}) :\n{diff}"
                    )
                else:
                    context.log(
                        "Correction appliquée "
                        f"(tentative {tentative}, v{written.version})."
                    )
                continue
            # Succès : build + contrôles verts.
            final_view = store.read(context.project_id)
            context.set_result(
                {
                    "iterations": tentative,
                    "version": final_view.version,
                    "bom": len(bom),
                    "layout_updated": layout,
                }
            )
            context.progress(max_iterations, max_iterations)
            context.log(
                f"Construction réussie après {tentative} tentative(s) "
                f"(v{final_view.version}, BOM {len(bom)} ligne(s))."
            )
            return

        raise RuntimeError(
            f"La correction s'est arrêtée après {max_iterations} tentative(s) "
            "sans construction réussie. "
            f"Dernier échec : {last_error or 'inconnu'}. "
            "Vérifie le code .ato, les imports et les empreintes, "
            "puis relance avec un plafond plus élevé."
        )

    return run
