"""Compat: discovery lead delegata all'orchestrator (unico punto di verità)."""

from app.services.orchestrator_service import run_global_search


async def search_global(seed: str, country: str, sector: str, limit: int, min_confidence: float = 0.32) -> list[dict]:
    packed = await run_global_search(seed, country, sector, limit, min_confidence=min_confidence)
    return list(packed.get("results") or [])
