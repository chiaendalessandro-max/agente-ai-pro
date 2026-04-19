import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)

_DEFAULT_UA = "AgenteAIPro/1.0 (+https://example.invalid)"
_ACCEPT_LANG = "en-US,en;q=0.9,it;q=0.8"


def _client_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=float(settings.http_connect_timeout),
        read=float(settings.http_read_timeout),
        write=float(settings.http_read_timeout),
        pool=10.0,
    )


async def get_with_retry(url: str) -> str:
    """GET con timeout granulari, limiti connessione e retry exponential backoff."""
    last_error: Exception | None = None
    headers = {"User-Agent": _DEFAULT_UA, "Accept-Language": _ACCEPT_LANG}
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=30)
    timeout = _client_timeout()
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
        limits=limits,
    ) as client:
        for attempt in range(1, settings.request_retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("http_timeout url=%s attempt=%s err=%s", url[:200], attempt, str(exc)[:200])
            except httpx.HTTPStatusError as exc:
                last_error = exc
                code = exc.response.status_code if exc.response is not None else 0
                logger.warning("http_status url=%s attempt=%s status=%s", url[:200], attempt, code)
                if code in (404, 410):
                    raise RuntimeError(f"HTTP {code} for {url}") from exc
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning("http_request_error url=%s attempt=%s err=%s", url[:200], attempt, str(exc)[:200])
            except Exception as exc:
                last_error = exc
                logger.warning("http_unknown url=%s attempt=%s err=%s", url[:200], attempt, str(exc)[:200])
            await asyncio.sleep(min(2.0, 0.35 * (2 ** (attempt - 1))))
    raise RuntimeError(f"Failed to fetch {url}: {last_error!s}")


async def post_json_with_retry(url: str, json_body: dict[str, Any] | None = None) -> httpx.Response:
    """Utility per chiamate POST JSON future (provider AI esterni)."""
    headers = {"User-Agent": _DEFAULT_UA, "Accept-Language": _ACCEPT_LANG, "Content-Type": "application/json"}
    timeout = _client_timeout()
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, limits=httpx.Limits(max_connections=10)) as client:
        for attempt in range(1, settings.request_retries + 1):
            try:
                r = await client.post(url, json=json_body or {})
                return r
            except Exception as exc:
                last_error = exc
                logger.warning("post_retry %s %s", attempt, str(exc)[:200])
                await asyncio.sleep(0.4 * attempt)
    raise RuntimeError(f"POST failed {url}: {last_error!s}")
