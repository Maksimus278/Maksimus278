import pytest

from bot.models import SearchQuery
from bot.providers.trulos import TrulosClient


@pytest.mark.asyncio
async def test_live_trulos_chicago_search():
    client = TrulosClient(timeout=30)
    loads = await client.search(SearchQuery(origin="Chicago"), limit=10, radius=150)
    assert len(loads) >= 3
    assert all(load.source == "Trulos (live)" for load in loads)
    assert any("IL" in load.origin or "Chicago" in load.origin for load in loads)
