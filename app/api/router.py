from fastapi import APIRouter

from app.api.routes import auth, emails, followups, kpi, leads


router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(leads.router, tags=["leads"])
router.include_router(emails.router, prefix="/emails", tags=["emails"])
router.include_router(kpi.router, prefix="/kpi", tags=["kpi"])
router.include_router(followups.router, prefix="/followups", tags=["followups"])
