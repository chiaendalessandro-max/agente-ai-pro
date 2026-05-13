"""Rilevamento lingua query e varianti di testo per ricerca Apollo (multilingua + inglese di supporto)."""

from __future__ import annotations

import re
from typing import Iterable

import search_keywords_de as kw_de
import search_keywords_en as kw_en
import search_keywords_es as kw_es
import search_keywords_fr as kw_fr
import search_keywords_it as kw_it

_ALL_MODULES = (kw_it, kw_en, kw_fr, kw_de, kw_es)

# Segnali deboli ma utili senza dipendenze esterne
_IT_PARTICLES = frozenset(
    "il lo la i gli le un una uno di da con su per tra fra che non più".split()
)
_FR_PARTICLES = frozenset("le la les des un une du de et en pour avec sans".split())
_DE_PARTICLES = frozenset("der die das und oder mit von zu im am dem den des ein eine".split())
_ES_PARTICLES = frozenset("el la los las un una de del en con por para y o".split())
_EN_PARTICLES = frozenset("the and for with from into about company companies services".split())

_IT_BOOST = frozenset(
    "aviazione aziende italia italiano italiana società charter aerotaxi elenco operatori".split()
)
_EN_BOOST = frozenset(
    "private jet operators operator company companies business aviation air charter services italy uk usa".split()
)
_FR_BOOST = frozenset("affaires entreprise entreprises française france aviation charter".split())
_DE_BOOST = frozenset("luftfahrt deutschland unternehmen geschäftsfliegerei charterflug".split())
_ES_BOOST = frozenset("aviación españa empresas español charter negocios".split())


def _score_lang(text: str) -> dict[str, int]:
    t = (text or "").lower()
    scores = {"it": 0, "en": 0, "fr": 0, "de": 0, "es": 0}
    tokens = re.findall(r"[a-zà-ÿß]+", t, flags=re.I)
    for w in tokens:
        wl = w.lower()
        if wl in _IT_PARTICLES:
            scores["it"] += 1
        if wl in _FR_PARTICLES:
            scores["fr"] += 1
        if wl in _DE_PARTICLES:
            scores["de"] += 1
        if wl in _ES_PARTICLES:
            scores["es"] += 1
        if wl in _EN_PARTICLES:
            scores["en"] += 1
    for phrase in _IT_BOOST:
        if phrase in t:
            scores["it"] += 2
    for phrase in _EN_BOOST:
        if phrase in t:
            scores["en"] += 2
    for phrase in _FR_BOOST:
        if phrase in t:
            scores["fr"] += 2
    for phrase in _DE_BOOST:
        if phrase in t:
            scores["de"] += 2
    for phrase in _ES_BOOST:
        if phrase in t:
            scores["es"] += 2
    # Accenti tipici (euristica)
    if re.search(r"[àèéìòù]", t):
        scores["it"] += 2
    if re.search(r"[âêîôûœç]", t):
        scores["fr"] += 2
    if re.search(r"[äöüß]", t):
        scores["de"] += 2
    if re.search(r"[áíóúñ]", t):
        scores["es"] += 2
    return scores


def detect_query_language(text: str) -> str:
    """Ritorna codice lingua principale: it|en|fr|de|es (default en)."""
    scores = _score_lang(text)
    best = max(scores, key=lambda k: scores[k])
    if scores[best] <= 0:
        return "en"
    return best


def _iter_sector_keys() -> Iterable[str]:
    keys: set[str] = set()
    for mod in _ALL_MODULES:
        keys.update((mod.KEYWORDS or {}).keys())
    return keys


def _collect_terms_for_sectors(sector_keys: set[str], primary_lang: str) -> tuple[list[str], list[str]]:
    """Ritorna (termini_nativi, english_bridge) per dare priorità al ponte inglese su Apollo."""
    by_lang = {"it": kw_it, "en": kw_en, "fr": kw_fr, "de": kw_de, "es": kw_es}
    primary = by_lang.get(primary_lang, kw_en)
    native_out: list[str] = []
    bridge_out: list[str] = []
    for key in sector_keys:
        modules = (primary, kw_en) if primary_lang != "en" else (primary,)
        for mod in modules:
            block = (mod.KEYWORDS or {}).get(key)
            if not block:
                continue
            for field in ("sector_terms", "synonyms", "business_queries"):
                native_out.extend(block.get(field) or [])
            if getattr(mod, "LANG", "") != "en":
                bridge_out.extend(block.get("english_bridge") or [])
    return native_out, bridge_out


def _sectors_matching(text: str, sector_hint: str) -> set[str]:
    hay = f"{text} {sector_hint}".lower()
    matched: set[str] = set()
    for key in _iter_sector_keys():
        if key in hay:
            matched.add(key)
            continue
        for mod in _ALL_MODULES:
            block = (mod.KEYWORDS or {}).get(key) or {}
            for term in block.get("sector_terms") or []:
                if term.lower() in hay:
                    matched.add(key)
                    break
    return matched


def build_apollo_query_variants(query: str, country: str, sector: str) -> tuple[str, list[str]]:
    """
    Ritorna (lingua_rilevata, lista_query_apollo) max 8 stringhe uniche.
    Italiano/francese/tedesco/spagnolo: include sempre anche forme inglesi di supporto via dati KEYWORDS.
    """
    q = (query or "").strip()
    if not q:
        return "en", []
    lang = detect_query_language(f"{q} {sector or ''}")
    sectors = _sectors_matching(q, sector or "")
    merged: list[str] = [q]
    if sectors:
        native_terms, bridge_terms = _collect_terms_for_sectors(sectors, lang)
        if lang != "en":
            merged.extend(bridge_terms)
        merged.extend(native_terms)
    c = (country or "").strip()
    if c and len(merged) < 8:
        merged.append(f"{q} {c}")
        if terms:
            merged.append(f"{terms[0]} {c}")
    seen: set[str] = set()
    out: list[str] = []
    for item in merged:
        k = re.sub(r"\s+", " ", item).strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(item.strip())
        if len(out) >= 8:
            break
    return lang, out
