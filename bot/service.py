from __future__ import annotations

import logging

from bot.leads import Lead, unique_leads
from bot.models import Load, SearchQuery
from bot.providers.trulos import TrulosClient
from bot.search import LoadRepository

logger = logging.getLogger(__name__)

LEAD_HUBS = [
    "Chicago",
    "Dallas",
    "Los Angeles",
    "Atlanta",
    "Houston",
    "Phoenix",
    "New York",
    "Memphis",
    "Indianapolis",
    "Columbus",
]


class LoadService:
    """Prefer live Trulos loads; fall back to local demo board."""

    def __init__(
        self,
        repo: LoadRepository,
        live: TrulosClient | None = None,
        *,
        use_live: bool = True,
        radius_mi: int = 200,
    ) -> None:
        self.repo = repo
        self.live = live or TrulosClient()
        self.use_live = use_live
        self.radius_mi = radius_mi

    async def search(self, query: SearchQuery, limit: int = 20) -> tuple[list[Load], str]:
        if self.use_live:
            try:
                loads = await self.live.search(query, limit=limit, radius=self.radius_mi)
                if loads:
                    return loads, "live:Trulos"
            except Exception:
                logger.exception("Live Trulos search failed; using local fallback")
        return self.repo.search(query, limit=limit), "local-demo"

    async def latest(self, limit: int = 15) -> tuple[list[Load], str]:
        if self.use_live:
            try:
                loads = await self.live.search(SearchQuery(), limit=limit, radius=120)
                if loads:
                    return loads, "live:Trulos"
            except Exception:
                logger.exception("Live latest fetch failed; using local fallback")
        return self.repo.all()[:limit], "local-demo"

    async def generate_leads(
        self,
        query: SearchQuery | None = None,
        *,
        limit: int = 15,
    ) -> tuple[list[Lead], str]:
        """Build real broker leads from live loads (company + phone)."""
        query = query or SearchQuery()
        collected: list[Load] = []
        source = "live:Trulos"

        if self.use_live:
            try:
                if query.origin or query.destination:
                    loads, source = await self.search(query, limit=max(limit * 4, 40))
                    collected.extend(loads)
                else:
                    # Multi-hub sweep for fresh leads across the US
                    for city in LEAD_HUBS:
                        chunk, source = await self.search(
                            SearchQuery(origin=city, truck_type=query.truck_type),
                            limit=20,
                        )
                        collected.extend(chunk)
                        if len(unique_leads(collected, limit=limit * 2)) >= limit:
                            break
            except Exception:
                logger.exception("Live lead generation failed")

        if not collected:
            collected = self.repo.search(query, limit=max(limit * 3, 40)) if (query.origin or query.destination) else self.repo.all()[:80]
            source = "local-demo"

        return unique_leads(collected, limit=limit), source
