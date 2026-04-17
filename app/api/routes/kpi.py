from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import apply_rate_limit, get_current_user
from app.core.database import get_db
from app.models.email_queue import EmailQueue
from app.models.followup import Followup
from app.models.company import Company
from app.models.lead import Lead
from app.models.user import User
from app.schemas.kpi import KpiOut


router = APIRouter(dependencies=[Depends(apply_rate_limit)])


@router.get("", response_model=KpiOut)
async def get_kpi(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> KpiOut:
    total = await db.scalar(select(func.count(Lead.id)).where(Lead.user_id == user.id))
    high = await db.scalar(select(func.count(Lead.id)).where(Lead.user_id == user.id, Lead.classification == "HIGH VALUE"))
    med = await db.scalar(select(func.count(Lead.id)).where(Lead.user_id == user.id, Lead.classification == "MEDIUM"))
    low = await db.scalar(select(func.count(Lead.id)).where(Lead.user_id == user.id, Lead.classification == "LOW"))
    emails = await db.scalar(select(func.count(EmailQueue.id)).join(Lead, EmailQueue.lead_id == Lead.id).where(Lead.user_id == user.id))
    followups = await db.scalar(
        select(func.count(Followup.id)).join(Lead, Followup.lead_id == Lead.id).where(Lead.user_id == user.id, Followup.status == "scheduled")
    )
    top_result = await db.execute(
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.user_id == user.id)
        .order_by(Lead.score.desc(), Lead.id.desc())
        .limit(5)
    )
    top_leads = top_result.all()
    suggestions = [
        {
            "lead_id": l.id,
            "company_name": c.name,
            "score": l.score,
            "classification": l.classification,
            "hint": "Contattare entro 24h" if l.score >= 70 else ("Warm nurturing" if l.score >= 40 else "Monitorare"),
        }
        for l, c in top_leads
    ]
    recent_activity = [
        {"type": "lead_saved", "value": int(total or 0)},
        {"type": "email_queue", "value": int(emails or 0)},
        {"type": "followups", "value": int(followups or 0)},
    ]
    next_actions: list[str] = []
    if (total or 0) == 0:
        next_actions.append("Avvia una prima ricerca globale dalla sezione Ricerca")
    if (high or 0) > 0:
        next_actions.append("Contatta oggi i lead HIGH VALUE per massimizzare conversione")
    if (emails or 0) == 0 and (total or 0) > 0:
        next_actions.append("Genera email personalizzate dalla sezione Email/Outreach")
    if (followups or 0) == 0 and (total or 0) > 0:
        next_actions.append("Pianifica follow-up automatici sui lead più caldi")
    if not next_actions:
        next_actions.append("Pipeline in ordine: continua con nuove ricerche e nurturing")
    return KpiOut(
        total_leads=total or 0,
        high_value=high or 0,
        medium_value=med or 0,
        low_value=low or 0,
        queued_emails=emails or 0,
        scheduled_followups=followups or 0,
        suggestions=suggestions,
        recent_activity=recent_activity,
        next_actions=next_actions,
    )
