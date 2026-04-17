import asyncio
import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


async def get_with_retry(url: str) -> str:
    last_error: Exception | None = None
    headers = {"User-Agent": "AgenteAIPro/1.0", "Accept-Language": "en-US,en;q=0.9,it;q=0.8"}
    for attempt in range(1, settings.request_retries + 1):
        try:
            async with httpx.AsyncClient(
                timeout=settings.request_timeout_seconds, follow_redirects=True, headers=headers
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.text
        except Exception as exc:
            last_error = exc
            logger.warning("HTTP retry %s for %s failed", attempt, url)
            await asyncio.sleep(0.4 * attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")
