import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine
from app.models.email_queue import EmailQueue


logger = logging.getLogger(__name__)


async def process_email_retries() -> None:
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        result = await db.execute(
            select(EmailQueue).where(EmailQueue.status == "draft", EmailQueue.retries < 3).limit(20)
        )
        drafts = result.scalars().all()
        for item in drafts:
            item.retries += 1
        await db.commit()
        if drafts:
            logger.info("Scheduler updated %s draft retries", len(drafts))


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await process_email_retries()
        except Exception as exc:
            logger.warning("Scheduler iteration failed: %s", str(exc)[:250])
        await asyncio.sleep(60)
