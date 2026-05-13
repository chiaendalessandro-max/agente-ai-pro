"""Router lingua: carica un solo modulo `search_queries_<lang>` per richiesta."""

from __future__ import annotations

import importlib
from typing import Any

_ALLOWED = frozenset({"it", "en", "fr", "de", "es"})


def normalize_search_language(lang: str | None) -> str:
    code = (lang or "en").strip().lower()[:2]
    return code if code in _ALLOWED else "en"


def load_queries_module(language: str) -> Any:
    """Import dinamico: viene eseguito solo `import search_queries_<code>`."""
    code = normalize_search_language(language)
    return importlib.import_module(f"search_queries_{code}")


def build_apollo_query_strings(
    language: str,
    user_query: str,
    country: str,
    sector: str,
    *,
    mode: str = "normal",
    max_strings: int = 8,
) -> tuple[str, list[str]]:
    """
    Costruisce la lista ordinata di stringhe da inviare ad Apollo.
    Ordine: query utente → (premium se mode premium) → business → keywords → sinonimi;
    eventuale suffisso paese solo se c'è spazio sotto il tetto.
    """
    code = normalize_search_language(language)
    mod = load_queries_module(code)
    bank = getattr(mod, "QUERY_BANK", None)
    q = (user_query or "").strip()
    if not isinstance(bank, dict):
        return code, ([q] if q else [])

    mode_n = (mode or "normal").strip().lower()
    ordered_pool: list[str] = []
    if q:
        ordered_pool.append(q)
    if mode_n == "premium":
        ordered_pool.extend(bank.get("premium_queries") or [])
    ordered_pool.extend(bank.get("business_queries") or [])
    ordered_pool.extend(bank.get("keywords") or [])
    ordered_pool.extend(bank.get("synonyms") or [])

    seen: set[str] = set()
    out: list[str] = []
    q_key = " ".join(q.lower().split()) if q else ""

    for i, raw in enumerate(ordered_pool):
        s = (raw or "").strip()
        if not s:
            continue
        key = " ".join(s.lower().split())
        if q_key and key == q_key and i > 0:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_strings:
            return code, out

    c = (country or "").strip()
    if c and q and len(out) < max_strings:
        extra = f"{q} {c}"
        ek = " ".join(extra.lower().split())
        if ek not in seen:
            out.append(extra)

    sec = (sector or "").strip()
    if sec and q and len(out) < max_strings:
        extra2 = f"{q} {sec}"
        ek2 = " ".join(extra2.lower().split())
        if ek2 not in seen:
            out.append(extra2)

    return code, out[:max_strings]
