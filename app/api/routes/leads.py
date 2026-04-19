import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import apply_rate_limit, get_current_user
from app.core.cache import TTLCache
from app.core.database import get_db
from app.models.company import Company
from app.models.lead import Lead
from app.models.user import User
from app.schemas.lead import (
    AnalyzeCompanyIn,
    LeadItemOut,
    LeadTemperatureIn,
    ScoreLeadIn,
    SearchGlobalIn,
)
from app.services.analyzer_service import safe_analyze_company
from app.services.orchestrator_service import run_global_search
from app.services.scoring_service import score_lead


logger = logging.getLogger(__name__)


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
        packed = await run_global_search(payload.query, payload.country, payload.sector, payload.limit)
        results = list(packed.get("results") or [])
        meta = packed.get("meta") or {}
    except Exception as exc:
        logger.exception("search_global orchestration failed: %s", str(exc)[:300])
        raise HTTPException(status_code=503, detail="Ricerca temporaneamente non disponibile. Riprovare.") from exc

    saved = 0
    try:
        for item in results:
            domain = (item.get("domain") or "").strip()
            if not domain:
                continue
            existing_company_q = await db.execute(select(Company).where(Company.domain == domain))
            company = existing_company_q.scalar_one_or_none()
            if not company:
                company = Company(
                    domain=domain,
                    name=item.get("name") or domain,
                    website=item.get("website") or f"https://{domain}/",
                    country=item.get("country") or "GLOBAL",
                    sector=item.get("sector") or "General",
                    size_estimate=item.get("size_estimate") or "SMB",
                    description=item.get("description") or "",
                    international_presence=int(item.get("international_presence") or 0),
                    value_signals=item.get("value_signals") or "",
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
                    contact_email=item.get("contact_email") or "",
                    contact_phone=item.get("contact_phone") or "",
                    contact_page=item.get("contact_page") or "",
                    score=int(item.get("score") or 0),
                    classification=item.get("classification") or "LOW",
                )
                db.add(lead)
                saved += 1
            else:
                lead.score = int(item.get("score") or 0)
                lead.classification = item.get("classification") or lead.classification
                lead.contact_email = item.get("contact_email") or lead.contact_email
                lead.contact_phone = item.get("contact_phone") or lead.contact_phone
                lead.contact_page = item.get("contact_page") or lead.contact_page
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("search_global persist failed: %s", str(exc)[:300])
        raise HTTPException(status_code=500, detail="Errore durante il salvataggio dei lead.") from exc

    out = {"saved": saved, "results": results, "meta": meta}
    cache.set(cache_key, out)
    return out


@router.post("/analyze-company")
async def analyze_company_endpoint(
    payload: AnalyzeCompanyIn, user: User = Depends(get_current_user)
) -> dict:
    _ = user
    data = await safe_analyze_company(payload.website)
    if not data:
        raise HTTPException(status_code=422, detail="Impossibile analizzare il sito indicato (timeout o URL non valido).")
    return data


@router.post("/score-lead")
async def score_lead_endpoint(payload: ScoreLeadIn, user: User = Depends(get_current_user)) -> dict:
    _ = user
    try:
        score, classification = score_lead(payload.model_dump())
        return {"score": score, "classification": classification}
    except Exception as exc:
        logger.warning("score_lead failed: %s", str(exc)[:200])
        raise HTTPException(status_code=422, detail="Input non valido per lo scoring") from exc


@router.get("/leads", response_model=list[LeadItemOut])
async def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    temperature: str = Query(default="", max_length=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LeadItemOut]:
    offset = (page - 1) * page_size
    stmt = (
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.user_id == user.id)
    )
    if q.strip():
        q_clean = f"%{q.strip().lower()}%"
        stmt = stmt.where((Company.name.ilike(q_clean)) | (Company.sector.ilike(q_clean)) | (Company.country.ilike(q_clean)))
    stmt = stmt.order_by(Lead.score.desc(), Lead.id.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()
    out = [
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
    if temperature.strip().upper() in {"HOT", "WARM", "COLD"}:
        t = temperature.strip().upper()
        out = [item for item in out if item.temperature == t]
    return out


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
    payload: LeadTemperatureIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    value = payload.temperature
    result = await db.execute(select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.notes = f"TEMP:{value}"
    await db.commit()
    return {"ok": True, "temperature": value}


@router.get("/high-value-leads", response_model=list[LeadItemOut])
async def high_value_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LeadItemOut]:
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.user_id == user.id, Lead.score >= 70)
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
