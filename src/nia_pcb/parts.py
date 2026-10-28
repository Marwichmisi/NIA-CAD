"""Liste de pièces commandable JLCPCB/LCSC (ticket #18, spec #13).

Ordre de préférence : Basic JLCPCB, stock, datasheet, footprint, modèle 3D.
Seuil de stock : max(10, 2 x quantité du projet).
"""

from pydantic import BaseModel, field_validator


class PartCandidate(BaseModel):
    lcsc: str
    mpn: str
    manufacturer: str
    description: str = ""
    is_basic: bool = False
    stock: int = 0
    datasheet_url: str | None = None
    footprint: str | None = None
    has_3d: bool = False

    @field_validator("lcsc", "mpn", "manufacturer")
    @classmethod
    def clean_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Référence pièce incomplète.")
        return cleaned

    @field_validator("stock")
    @classmethod
    def clean_stock(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Indique un stock entier.")
        if value < 0:
            raise ValueError("Le stock ne peut pas être négatif.")
        return value


class PartRequirement(BaseModel):
    reference: str
    quantity: int
    critical: bool = False
    query: str = ""

    @field_validator("reference")
    @classmethod
    def clean_reference(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Indique une référence.")
        return cleaned

    @field_validator("quantity")
    @classmethod
    def clean_quantity(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("Indique une quantité positive.")
        return value


class ChosenPart(BaseModel):
    reference: str
    quantity: int
    threshold: int
    critical: bool
    part: PartCandidate
    alternative: PartCandidate | None = None


class RejectedPart(BaseModel):
    reference: str
    quantity: int
    raison: str

    @property
    def reason(self) -> str:
        return self.raison


class PartsList(BaseModel):
    chosen: list[ChosenPart] = []
    rejected: list[RejectedPart] = []


def stock_threshold(quantity: int) -> int:
    return max(10, 2 * quantity)


def has_reliable_footprint(candidate: PartCandidate) -> bool:
    return bool(candidate.footprint and candidate.footprint.strip())


def has_datasheet(candidate: PartCandidate) -> bool:
    return bool(candidate.datasheet_url and candidate.datasheet_url.strip())


def _sort_key(candidate: PartCandidate) -> tuple:
    return (
        not candidate.is_basic,
        -candidate.stock,
        not has_datasheet(candidate),
        not has_reliable_footprint(candidate),
        not candidate.has_3d,
        candidate.lcsc,
    )


def select_parts(
    requirements: list[PartRequirement],
    candidates_by_reference: dict[str, list[PartCandidate]],
) -> PartsList:
    chosen: list[ChosenPart] = []
    rejected: list[RejectedPart] = []
    for req in requirements:
        threshold = stock_threshold(req.quantity)
        candidates = list(candidates_by_reference.get(req.reference, []))
        if not candidates:
            rejected.append(
                RejectedPart(
                    reference=req.reference,
                    quantity=req.quantity,
                    raison="Aucun candidat trouvé pour cette référence.",
                )
            )
            continue
        with_footprint = [c for c in candidates if has_reliable_footprint(c)]
        if not with_footprint:
            rejected.append(
                RejectedPart(
                    reference=req.reference,
                    quantity=req.quantity,
                    raison=(
                        "Pièce rejetée : aucun footprint fiable "
                        f"parmi {len(candidates)} candidat(s)."
                    ),
                )
            )
            continue
        stocked = [c for c in with_footprint if c.stock >= threshold]
        if not stocked:
            best = max(with_footprint, key=lambda c: c.stock)
            rejected.append(
                RejectedPart(
                    reference=req.reference,
                    quantity=req.quantity,
                    raison=(
                        f"Pièce rejetée : stock insuffisant "
                        f"(meilleur {best.stock}, seuil {threshold})."
                    ),
                )
            )
            continue
        ranked = sorted(stocked, key=_sort_key)
        picked = ranked[0]
        alternative = ranked[1] if len(ranked) > 1 else None
        if req.critical and alternative is None:
            rejected.append(
                RejectedPart(
                    reference=req.reference,
                    quantity=req.quantity,
                    raison=(
                        "Pièce critique sans alternative : "
                        f"{picked.lcsc} seul candidat au seuil {threshold}."
                    ),
                )
            )
            continue
        chosen.append(
            ChosenPart(
                reference=req.reference,
                quantity=req.quantity,
                threshold=threshold,
                critical=req.critical,
                part=picked,
                alternative=alternative,
            )
        )
    return PartsList(chosen=chosen, rejected=rejected)
