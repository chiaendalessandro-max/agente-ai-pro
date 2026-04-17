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
    subject, body = make_email(company.name, company.sector, company.description, lead.score)
    status, error = send_or_draft(lead.contact_email, subject, body)
    item = EmailQueue(lead_id=lead.id, subject=subject, body=body, status=status, error=error)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return EmailDraftOut(id=item.id, status=item.status, subject=item.subject, body=item.body, error=item.error)


@router.get("")
async def list_emails(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(EmailQueue).join(Lead, EmailQueue.lead_id == Lead.id).where(Lead.user_id == user.id)
    )
    items = result.scalars().all()
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
