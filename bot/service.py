from __future__ import annotations

import logging

from bot.models import Load, SearchQuery
from bot.providers.trulos import TrulosClient
from bot.search import LoadRepository

logger = logging.getLogger(__name__)


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
