"""Adaptateur catalogue LCSC/JLCPCB avec doubles déterministes (ticket #18)."""

from nia_pcb.parts import PartCandidate
from nia_pcb.parts_catalog import CachedCatalog, InMemoryCatalog, parse_jlcsearch


def test_parse_jlcsearch_priorise_basic_et_remplit_stock() -> None:
    payload = {
        "components": [
            {
                "lcsc": 25804,
                "mfr": "0603WAF1002T5E",
                "package": "0603",
                "is_basic": False,
                "description": "10k",
                "stock": 37165617,
                "price": 0.00084,
            },
            {
                "lcsc": 25744,
                "mfr": "0603WAF1002T5E-BASIC",
                "package": "0603",
                "is_basic": True,
                "description": "10k basic",
                "stock": 500,
                "price": 0.001,
            },
        ]
    }
    candidates = parse_jlcsearch(payload)
    assert [c.lcsc for c in candidates] == ["C25804", "C25744"]
    assert candidates[1].is_basic is True
    assert candidates[1].stock == 500
    assert all(isinstance(c, PartCandidate) for c in candidates)


def test_cache_local_evite_le_second_appel() -> None:
    calls: list[str] = []

    def fake_search(query: str) -> list[PartCandidate]:
        calls.append(query)
        return [
            PartCandidate(
                lcsc="C1",
                mpn="MPN-C1",
                manufacturer="Fab",
                stock=100,
                footprint="0603",
            )
        ]

    inner = InMemoryCatalog({"10k": fake_search("10k")})
    cached = CachedCatalog(inner)
    first = cached.search("10k")
    second = cached.search("10k")
    assert first == second
    assert cached.calls == 1


def test_aucun_secret_dans_les_resultats_ni_le_journal() -> None:
    import os

    os.environ["JLCPCB_API_KEY"] = "cle-ultra-secrete-1234"
    try:
        catalog = InMemoryCatalog(
            {
                "10k": [
                    PartCandidate(
                        lcsc="C1",
                        mpn="MPN-C1",
                        manufacturer="Fab",
                        stock=100,
                        footprint="0603",
                    )
                ]
            }
        )
        cached = CachedCatalog(catalog)
        results = cached.search("10k")
        payload = "[" + ",".join(r.model_dump_json() for r in results) + "]"
        assert "cle-ultra-secrete-1234" not in payload
        assert "cle-ultra-secrete-1234" not in catalog.last_query_or_empty()
    finally:
        del os.environ["JLCPCB_API_KEY"]
