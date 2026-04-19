"""Compat: discovery lead delegata all'orchestrator (unico punto di verità)."""

from app.services.orchestrator_service import run_global_search


async def search_global(seed: str, country: str, sector: str, limit: int) -> list[dict]:
    packed = await run_global_search(seed, country, sector, limit)
    return list(packed.get("results") or [])
