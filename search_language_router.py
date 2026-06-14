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


def _pick_main_keyword(bank: dict[str, list[str]], sector: str, *, premium: bool) -> str:
    keywords = list(bank.get("keywords") or [])
    if premium:
        premium_q = bank.get("premium_queries") or []
        if premium_q:
            return (premium_q[0] or "").strip()
    sec = (sector or "").strip().lower()
    if sec:
        for pool_name in ("keywords", "synonyms", "business_queries"):
            for kw in bank.get(pool_name) or []:
                k = (kw or "").strip()
                if not k:
                    continue
                kl = k.lower()
                if sec in kl or kl in sec:
                    return k
    if keywords:
        return (keywords[0] or "").strip()
    for pool_name in ("business_queries", "synonyms"):
        for kw in bank.get(pool_name) or []:
            k = (kw or "").strip()
            if k:
                return k
    return ""


def build_search_params(
    language: str,
    user_query: str,
    country: str,
    sector: str,
    *,
    mode: str = "normal",
) -> tuple[str, str, str]:
    """
    Costruisce i parametri di ricerca dal file lingua selezionato:
    query organizzazione pulita + keyword principale.
    Ritorna (lang_code, organization_query, main_keyword).
    """
    code = normalize_search_language(language)
    mod = load_queries_module(code)
    bank = getattr(mod, "QUERY_BANK", None)
    q = (user_query or "").strip()
    mode_n = (mode or "normal").strip().lower()
    premium = mode_n == "premium"

    if not isinstance(bank, dict):
        return code, q, (sector or "").strip()

    main_kw = _pick_main_keyword(bank, sector or q, premium=premium)
    if not main_kw:
        main_kw = (sector or "").strip()

    org_query = q or main_kw
    return code, org_query, main_kw
