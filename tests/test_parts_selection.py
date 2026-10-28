"""Sélection ordonnancée Basic > stock > datasheet > footprint > 3D (ticket #18)."""

from nia_pcb.parts import (
    PartCandidate,
    PartRequirement,
    select_parts,
    stock_threshold,
)


def _candidate(lcsc: str, **overrides) -> PartCandidate:
    base = {
        "lcsc": lcsc,
        "mpn": f"MPN-{lcsc}",
        "manufacturer": "Fab",
        "description": "condensateur 100nF 50V",
        "is_basic": False,
        "stock": 100,
        "datasheet_url": "https://exemple.test/datasheet.pdf",
        "footprint": "C_0603_1608Metric",
        "has_3d": True,
    }
    base.update(overrides)
    return PartCandidate(**base)


def test_seuil_stock_est_le_maximum_entre_10_et_deux_fois_la_quantite() -> None:
    assert stock_threshold(3) == 10
    assert stock_threshold(5) == 10
    assert stock_threshold(6) == 12
    assert stock_threshold(20) == 40


def test_basic_passe_avant_stock_superieur() -> None:
    req = [PartRequirement(reference="C1", quantity=2, critical=False, query="100nF")]
    cands = {
        "C1": [
            _candidate("C1", is_basic=False, stock=50000),
            _candidate("C2", is_basic=True, stock=100),
        ]
    }
    result = select_parts(req, cands)
    assert len(result.chosen) == 1
    assert result.chosen[0].part.lcsc == "C2"
    assert result.rejected == []


def test_stock_sous_le_seuil_rejette_avec_raison_visible() -> None:
    req = [PartRequirement(reference="R1", quantity=10, critical=False, query="10k")]
    cands = {"R1": [_candidate("C10", stock=5)]}
    result = select_parts(req, cands)
    assert result.chosen == []
    assert len(result.rejected) == 1
    assert "20" in result.rejected[0].reason
    assert result.rejected[0].reference == "R1"


def test_sans_footprint_fiable_rejette_avec_raison_visible() -> None:
    req = [PartRequirement(reference="U1", quantity=1, critical=True, query="ESP32")]
    cands = {
        "U1": [
            _candidate("C20", footprint=None, stock=500),
            _candidate("C21", footprint="  ", stock=500),
        ]
    }
    result = select_parts(req, cands)
    assert result.chosen == []
    assert len(result.rejected) == 1
    assert "footprint" in result.rejected[0].reason.lower()


def test_critique_exige_une_alternative_sinon_rejet() -> None:
    req = [PartRequirement(reference="U1", quantity=1, critical=True, query="ESP32")]
    cands = {"U1": [_candidate("C30", is_basic=True, stock=500)]}
    result = select_parts(req, cands)
    assert result.chosen == []
    assert len(result.rejected) == 1
    assert "alternative" in result.rejected[0].reason.lower()

    cands["U1"].append(_candidate("C31", is_basic=True, stock=400))
    result = select_parts(req, cands)
    assert len(result.chosen) == 1
    assert result.chosen[0].alternative is not None
    assert result.chosen[0].alternative.lcsc == "C31"


def test_ordre_complet_basic_stock_datasheet_footprint_3d() -> None:
    req = [PartRequirement(reference="C1", quantity=1, critical=False, query="100nF")]
    cands = {
        "C1": [
            _candidate(
                "C40", is_basic=True, stock=50, datasheet_url=None, has_3d=False
            ),
            _candidate("C41", is_basic=True, stock=50, has_3d=True),
        ]
    }
    result = select_parts(req, cands)
    assert result.chosen[0].part.lcsc == "C41"
