from pydantic import BaseModel


class KpiOut(BaseModel):
    total_leads: int
    high_value: int
    medium_value: int
    low_value: int
    queued_emails: int
    scheduled_followups: int
    suggestions: list[dict]
    recent_activity: list[dict]
