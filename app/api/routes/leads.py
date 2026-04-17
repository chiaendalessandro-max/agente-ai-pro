import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import apply_rate_limit, get_current_user
from app.core.cache import TTLCache
from app.core.database import get_db
from app.models.company import Company
from app.models.lead import Lead
from app.models.user import User
from app.schemas.lead import AnalyzeCompanyIn, LeadItemOut, ScoreLeadIn, SearchGlobalIn
from app.services.analyzer_service import analyze_company
from app.services.lead_engine import search_global
from app.services.scoring_service import score_lead


router = APIRouter(dependencies=[Depends(apply_rate_limit)])
cache = TTLCache(ttl_seconds=180, max_items=300)


def _temperature_from_lead(lead: Lead) -> str:
    note = (lead.notes or "").strip().upper()
    if note.startswith("TEMP:HOT"):
        return "HOT"
    if note.startswith("TEMP:COLD"):
        return "COLD"
    if note.startswith("TEMP:WARM"):
        return "WARM"
    if lead.score >= 70:
        return "HOT"
    if lead.score >= 40:
        return "WARM"
    return "COLD"


@router.post("/search-global")
async def search_global_endpoint(
    payload: SearchGlobalIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cache_key = hashlib.sha256(f"{user.id}:{payload.model_dump_json()}".encode("utf-8")).hexdigest()
    hit = cache.get(cache_key)
    if hit is not None:
        return hit

    try:
        results = await search_global(payload.query, payload.country, payload.sector, payload.limit)
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Search provider temporarily unavailable. Retry in a few seconds.",
        )
    saved = 0
    for item in results:
        existing_company_q = await db.execute(select(Company).where(Company.domain == item["domain"]))
        company = existing_company_q.scalar_one_or_none()
        if not company:
            company = Company(
                domain=item["domain"],
                name=item["name"],
                website=item["website"],
                country=item["country"],
                sector=item["sector"],
                size_estimate=item["size_estimate"],
                description=item["description"],
                international_presence=item["international_presence"],
                value_signals=item["value_signals"],
            )
            db.add(company)
            await db.flush()

        lead_q = await db.execute(select(Lead).where(Lead.user_id == user.id, Lead.company_id == company.id))
        lead = lead_q.scalar_one_or_none()
        if not lead:
            lead = Lead(
                user_id=user.id,
                company_id=company.id,
                source_query=payload.query,
                contact_email=item["contact_email"],
                contact_phone=item["contact_phone"],
                contact_page=item["contact_page"],
                score=item["score"],
                classification=item["classification"],
            )
            db.add(lead)
            saved += 1
        else:
            lead.score = item["score"]
            lead.classification = item["classification"]
            lead.contact_email = item["contact_email"]
            lead.contact_phone = item["contact_phone"]
            lead.contact_page = item["contact_page"]
    await db.commit()
    out = {"saved": saved, "results": results}
    cache.set(cache_key, out)
    return out


@router.post("/analyze-company")
async def analyze_company_endpoint(
    payload: AnalyzeCompanyIn, user: User = Depends(get_current_user)
) -> dict:
    _ = user
    try:
        return await analyze_company(payload.website)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:300])


@router.post("/score-lead")
async def score_lead_endpoint(payload: ScoreLeadIn, user: User = Depends(get_current_user)) -> dict:
    _ = user
    score, classification = score_lead(payload.model_dump())
    return {"score": score, "classification": classification}


@router.get("/leads", response_model=list[LeadItemOut])
async def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LeadItemOut]:
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.user_id == user.id)
        .order_by(Lead.score.desc(), Lead.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()
    return [
        LeadItemOut(
            id=l.id,
            company_name=c.name,
            website=c.website,
            score=l.score,
            classification=l.classification,
            temperature=_temperature_from_lead(l),
            sector=c.sector,
            country=c.country,
            contact_email=l.contact_email,
            contact_phone=l.contact_phone,
        )
        for l, c in rows
    ]


@router.get("/leads/{lead_id}")
async def lead_detail(lead_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.id == lead_id, Lead.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    l, c = row
    return {
        "id": l.id,
        "company_name": c.name,
        "website": c.website,
        "country": c.country,
        "sector": c.sector,
        "size_estimate": c.size_estimate,
        "description": c.description,
        "value_signals": c.value_signals,
        "score": l.score,
        "classification": l.classification,
        "temperature": _temperature_from_lead(l),
        "contact_email": l.contact_email,
        "contact_phone": l.contact_phone,
        "contact_page": l.contact_page,
    }


@router.patch("/leads/{lead_id}/temperature")
async def set_lead_temperature(
    lead_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    value = str(payload.get("temperature", "")).upper()
    if value not in {"HOT", "WARM", "COLD"}:
        raise HTTPException(status_code=400, detail="temperature must be HOT/WARM/COLD")
    result = await db.execute(select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.notes = f"TEMP:{value}"
    await db.commit()
    return {"ok": True, "temperature": value}
