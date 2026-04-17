from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import apply_rate_limit, get_current_user
from app.core.database import get_db
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.user import User
from app.services.followup_service import next_followup_iso


router = APIRouter(dependencies=[Depends(apply_rate_limit)])


@router.post("/{lead_id}")
async def create_followup(lead_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    lead_q = await db.execute(select(Lead).where(Lead.id == lead_id, Lead.user_id == user.id))
    lead = lead_q.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    f = Followup(lead_id=lead.id, due_at_iso=next_followup_iso(2), status="scheduled", note="Auto follow-up")
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return {"id": f.id, "status": f.status, "due_at": f.due_at_iso}


@router.get("")
async def list_followups(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(Followup).join(Lead, Followup.lead_id == Lead.id).where(Lead.user_id == user.id)
    )
    items = result.scalars().all()
    return {
        "items": [
            {"id": f.id, "lead_id": f.lead_id, "channel": f.channel, "due_at": f.due_at_iso, "status": f.status}
            for f in items
        ]
    }
