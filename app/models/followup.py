from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Followup(Base, TimestampMixin):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(40), default="email")
    due_at_iso: Mapped[str] = mapped_column(String(50), default="")
    status: Mapped[str] = mapped_column(String(40), default="scheduled")
    note: Mapped[str] = mapped_column(Text, default="")

    lead = relationship("Lead", back_populates="followups")
