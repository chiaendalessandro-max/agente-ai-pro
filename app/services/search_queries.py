"""Query DDGS multi-lingua e multi-intento (ricerca aziende reale)."""
from __future__ import annotations

import re

from app.services.country_context import CountryContext


def build_search_queries(seed: str, sector: str, ctx: CountryContext | None, relaxed: bool = False) -> list[str]:
    s = (seed or "").strip()
    sec = (sector or "").strip()
    base = f"{s} {sec}".strip()
    out: list[str] = []

    if ctx and not relaxed:
        ne, nl = ctx.names_en, ctx.names_local
        italy, italia = ne[0], nl[0]
        out.extend(
            [
                f"{base} companies {italy} official website".strip(),
                f"{base} {italy} enterprise B2B".strip(),
                f"{base} {italy} industry".strip(),
                f"aziende {base} {italia} sito ufficiale".strip(),
                f"{s} aziende {italia} {sec}".strip() if sec else f"{s} aziende {italia}".strip(),
                f"{s} companies {italy} {sec}".strip() if sec else f"{s} companies {italy}".strip(),
                f"{s} {ne[1]} {italy} corporate".strip(),
                f"{base} fornitori {italia}".strip(),
                f"{base} imprese {italia} elenco".strip(),
                f"directory {base} {italia}".strip(),
                f"{s} {sec} {italy} manufacturers".strip() if sec else f"{s} manufacturers {italy}".strip(),
                f"list of {base} companies {italy}".strip(),
                f"{base} {italy} suppliers directory".strip(),
                f"{base} {italia} PMI professional".strip(),
                f"{s} {italy} {sec} services companies".strip() if sec else f"{s} professional services {italy}".strip(),
            ]
        )
    elif ctx and relaxed:
        out.extend(
            [
                f"{s} companies {ctx.names_en[0]}".strip(),
                f"{s} {ctx.names_en[0]} industry directory".strip(),
                f"{base} corporate website".strip(),
                f"{s} {sec} companies Europe".strip() if sec else f"{s} companies Europe".strip(),
                f"{base} SME {ctx.names_en[0]}".strip(),
            ]
        )
    else:
        out.extend(
            [
                f"{base} companies official website".strip(),
                f"{base} corporate global".strip(),
                f"{base} enterprise solutions".strip(),
                f"{base} B2B companies directory".strip(),
                f"list of {base} companies".strip(),
                f"{s} industry companies {sec}".strip() if sec else f"{s} industry companies".strip(),
            ]
        )

    cleaned: list[str] = []
    seen: set[str] = set()
    for q in out:
        q2 = re.sub(r"\s+", " ", q).strip()
        if len(q2) < 4 or q2.lower() in seen:
            continue
        seen.add(q2.lower())
        cleaned.append(q2[:300])
    return cleaned[:22]
