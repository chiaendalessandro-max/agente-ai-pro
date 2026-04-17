from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import apply_rate_limit, get_current_user
from app.core.database import get_db
from app.models.email_queue import EmailQueue
from app.models.followup import Followup
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
    return KpiOut(
        total_leads=total or 0,
        high_value=high or 0,
        medium_value=med or 0,
        low_value=low or 0,
        queued_emails=emails or 0,
        scheduled_followups=followups or 0,
    )
