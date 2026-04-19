import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import apply_rate_limit, get_current_user
from app.core.database import get_db
from app.models.company import Company
from app.models.email_queue import EmailQueue
from app.models.lead import Lead
from app.models.user import User
from app.schemas.email import EmailDraftOut
from app.services.email_service import make_email, send_or_draft


logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(apply_rate_limit)])


@router.post("/{lead_id}", response_model=EmailDraftOut)
async def create_email(lead_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> EmailDraftOut:
    result = await db.execute(
        select(Lead, Company)
        .join(Company, Lead.company_id == Company.id)
        .where(Lead.id == lead_id, Lead.user_id == user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead, company = row
    last_email_q = await db.execute(
        select(EmailQueue)
        .where(EmailQueue.lead_id == lead.id)
        .order_by(EmailQueue.id.desc())
        .limit(1)
    )
    last_email = last_email_q.scalar_one_or_none()
    if last_email and (last_email.status in {"sent", "draft"}):
        return EmailDraftOut(
            id=last_email.id,
            status=last_email.status,
            subject=last_email.subject,
            body=last_email.body,
            error=last_email.error,
        )
    subject, body = make_email(company.name, company.sector, company.description, lead.score)
    status, error = send_or_draft(lead.contact_email, subject, body)
    item = EmailQueue(lead_id=lead.id, subject=subject, body=body, status=status, error=error)
    db.add(item)
    try:
        await db.commit()
        await db.refresh(item)
    except Exception as exc:
        await db.rollback()
        logger.exception("create_email persist failed: %s", str(exc)[:250])
        raise HTTPException(status_code=500, detail="Impossibile salvare l'email in coda.") from exc
    return EmailDraftOut(id=item.id, status=item.status, subject=item.subject, body=item.body, error=item.error)


@router.get("")
async def list_emails(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    try:
        result = await db.execute(
            select(EmailQueue).join(Lead, EmailQueue.lead_id == Lead.id).where(Lead.user_id == user.id)
        )
        items = result.scalars().all()
    except Exception as exc:
        logger.exception("list_emails failed: %s", str(exc)[:250])
        return {"items": []}
    return {
        "items": [
            {
                "id": e.id,
                "lead_id": e.lead_id,
                "status": e.status,
                "subject": e.subject,
                "retries": e.retries,
                "error": e.error,
            }
            for e in items
        ]
    }
