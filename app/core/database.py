from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _normalize_database_url(url: str) -> str:
    """Render fornisce postgresql://; il driver async richiede postgresql+asyncpg://."""
    u = (url or "").strip()
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    if u.startswith("postgresql://") and "+asyncpg" not in u:
        u = "postgresql+asyncpg://" + u[len("postgresql://"):]
    return u


def _connect_args_for_url(url: str) -> dict:
    """Evita hang infiniti in startup (Render port scan) se il DB non risponde."""
    u = (url or "").lower()
    if "postgresql+asyncpg" in u or "postgres+asyncpg" in u:
        # asyncpg: timeout di connessione TCP/handshake (secondi)
        return {"timeout": 15}
    return {}


_database_url = _normalize_database_url(settings.database_url)

engine = create_async_engine(
    _database_url,
    pool_pre_ping=True,
    pool_timeout=30,
    connect_args=_connect_args_for_url(_database_url),
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
