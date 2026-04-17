import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.router import router as api_router
from app.core.logger import setup_logging
from app.core.database import engine
from app.models import Base
from app.services.scheduler_service import scheduler_loop


setup_logging()
logger = logging.getLogger(__name__)
app = FastAPI(title="Agente AI Pro", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

_stop_event = asyncio.Event()
_scheduler_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup() -> None:
    global _scheduler_task
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _scheduler_task = asyncio.create_task(scheduler_loop(_stop_event))
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown() -> None:
    _stop_event.set()
    if _scheduler_task:
        await asyncio.wait({_scheduler_task}, timeout=2)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def home() -> FileResponse:
    html_path = Path(__file__).resolve().parent / "frontend" / "index.html"
    return FileResponse(html_path)


@app.exception_handler(Exception)
async def global_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", str(exc)[:300])
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=False)
