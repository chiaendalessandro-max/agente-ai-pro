import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


class InMemoryRateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.store: dict[str, deque[float]] = defaultdict(deque)

    async def check(self, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = time.time()
        q = self.store[client]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        q.append(now)


rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)
