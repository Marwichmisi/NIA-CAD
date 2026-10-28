"""Catalogue pièces : interface unique, cache local, sans secret en log."""

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Protocol

from nia_pcb.parts import PartCandidate
from nia_pcb.secrets import redact_text


class PartsCatalog(Protocol):
    def search(self, query: str) -> list[PartCandidate]: ...


class InMemoryCatalog:
    """Double déterministe pour les tests et la couture API."""

    def __init__(self, canned: dict[str, list[PartCandidate]]) -> None:
        self._canned = dict(canned)
        self._last_query = ""

    def search(self, query: str) -> list[PartCandidate]:
        cleaned = redact_text(query.strip())
        self._last_query = cleaned
        return list(self._canned.get(cleaned, []))

    def last_query_or_empty(self) -> str:
        return self._last_query


class CachedCatalog:
    """Cache local strict : un seul appel par requête distincte."""

    def __init__(self, inner: PartsCatalog) -> None:
        self._inner = inner
        self._cache: dict[str, list[PartCandidate]] = {}
        self.calls = 0

    def search(self, query: str) -> list[PartCandidate]:
        cleaned = redact_text(query.strip())
        if cleaned in self._cache:
            return list(self._cache[cleaned])
        self.calls += 1
        results = self._inner.search(cleaned)
        self._cache[cleaned] = list(results)
        return list(results)


def parse_jlcsearch(payload: dict) -> list[PartCandidate]:
    components = payload.get("components", [])
    candidates: list[PartCandidate] = []
    for row in components:
        try:
            lcsc_id = row.get("lcsc")
            mfr = str(row.get("mfr", "")).strip() or "inconnu"
            package = str(row.get("package", "")).strip() or None
            candidates.append(
                PartCandidate(
                    lcsc=f"C{lcsc_id}",
                    mpn=mfr,
                    manufacturer="LCSC",
                    description=str(row.get("description", "")),
                    is_basic=bool(row.get("is_basic", False)),
                    stock=int(row.get("stock", 0)),
                    datasheet_url=None,
                    footprint=package,
                    has_3d=False,
                )
            )
        except Exception:
            continue
    return candidates


class JlcsearchCatalog:
    """Adaptateur réel jlcsearch (source LCSC/JLCPCB, sans clé)."""

    def __init__(
        self,
        fetcher: Callable[[str], dict] | None = None,
    ) -> None:
        self._fetcher = fetcher or _fetch_jlcsearch

    def search(self, query: str) -> list[PartCandidate]:
        cleaned = redact_text(query.strip())
        if not cleaned:
            return []
        try:
            payload = self._fetcher(cleaned)
        except Exception:
            return []
        return parse_jlcsearch(payload)


def _fetch_jlcsearch(query: str, limit: int = 20) -> dict:
    params = urllib.parse.urlencode({"q": query, "limit": limit})
    url = f"https://jlcsearch.tscircuit.com/api/search?{params}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
