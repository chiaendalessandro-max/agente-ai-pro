from urllib.parse import urlparse

from duckduckgo_search import DDGS

from app.services.analyzer_service import analyze_company
from app.services.scoring_service import score_lead


def build_queries(seed: str, country: str = "", sector: str = "") -> list[str]:
    base = f"{seed.strip()} {sector.strip()}".strip()
    c = country.strip()
    return [
        f"{base} official website {c}".strip(),
        f"{base} enterprise solutions global".strip(),
        f"{base} corporate services".strip(),
        f"{base} site officiel entreprise".strip(),
        f"{base} sitio oficial empresa".strip(),
        f"{base} unternehmen offizielle website".strip(),
        f"{base} contatti azienda".strip(),
    ]


def _valid(url: str) -> bool:
    d = urlparse(url).netloc.lower()
    if not d:
        return False
    blocked = ("linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com")
    return not any(b in d for b in blocked)


async def search_global(seed: str, country: str, sector: str, limit: int) -> list[dict]:
    queries = build_queries(seed, country, sector)
    seen: set[str] = set()
    websites: list[str] = []

    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    for item in ddgs.text(q, max_results=12):
                        url = item.get("href") or item.get("url") or ""
                        if not _valid(url):
                            continue
                        domain = urlparse(url).netloc.lower().replace("www.", "")
                        if domain in seen:
                            continue
                        seen.add(domain)
                        websites.append(f"https://{domain}")
                        if len(websites) >= limit:
                            break
                except Exception:
                    continue
                if len(websites) >= limit:
                    break
    except Exception:
        # Keep app stable when search providers throttle/fail.
        websites = []

    leads: list[dict] = []
    for site in websites:
        try:
            analyzed = await analyze_company(site)
            score, classification = score_lead(
                {
                    "website": analyzed["website"],
                    "description": analyzed["description"],
                    "sector": analyzed["sector"],
                    "size_estimate": analyzed["size_estimate"],
                    "international_presence": analyzed["international_presence"],
                    "has_corporate_email": bool(analyzed["contact_email"]),
                    "has_phone": bool(analyzed["contact_phone"]),
                }
            )
            analyzed["score"] = score
            analyzed["classification"] = classification
            analyzed["source_query"] = seed
            leads.append(analyzed)
        except Exception:
            continue

    leads.sort(key=lambda x: x.get("score", 0), reverse=True)
    return leads
