from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from bot.models import Load, SearchQuery, WatchFilter

_CITY_ALIASES: dict[str, set[str]] = {
    "los angeles, ca": {"la", "los angeles", "los angeles ca", "los angeles, ca", "lax"},
    "new york, ny": {"nyc", "new york", "new york ny", "new york, ny", "ny"},
    "chicago, il": {"chi", "chicago", "chicago il", "chicago, il"},
    "dallas, tx": {"dallas", "dallas tx", "dallas, tx", "dfw"},
    "houston, tx": {"houston", "houston tx", "houston, tx", "hou"},
    "atlanta, ga": {"atlanta", "atlanta ga", "atlanta, ga", "atl"},
    "phoenix, az": {"phoenix", "phoenix az", "phoenix, az", "phx"},
    "miami, fl": {"miami", "miami fl", "miami, fl", "mia"},
    "seattle, wa": {"seattle", "seattle wa", "seattle, wa", "sea"},
    "denver, co": {"denver", "denver co", "denver, co", "den"},
    "las vegas, nv": {"las vegas", "vegas", "las vegas nv", "las vegas, nv", "las"},
    "san francisco, ca": {"sf", "san francisco", "san francisco ca", "san francisco, ca"},
    "san diego, ca": {"san diego", "san diego ca", "san diego, ca", "san"},
    "portland, or": {"portland", "portland or", "portland, or", "pdx"},
    "detroit, mi": {"detroit", "detroit mi", "detroit, mi", "dtw"},
    "columbus, oh": {"columbus", "columbus oh", "columbus, oh"},
    "indianapolis, in": {"indianapolis", "indy", "indianapolis in", "indianapolis, in"},
    "charlotte, nc": {"charlotte", "charlotte nc", "charlotte, nc", "clt"},
    "nashville, tn": {"nashville", "nashville tn", "nashville, tn", "bna"},
    "memphis, tn": {"memphis", "memphis tn", "memphis, tn", "mem"},
    "kansas city, mo": {"kansas city", "kc", "kansas city mo", "kansas city, mo"},
    "st louis, mo": {"st louis", "saint louis", "st louis mo", "st louis, mo", "stl"},
    "minneapolis, mn": {"minneapolis", "minneapolis mn", "minneapolis, mn", "msp"},
    "philadelphia, pa": {"philadelphia", "philly", "philadelphia pa", "philadelphia, pa"},
    "boston, ma": {"boston", "boston ma", "boston, ma", "bos"},
    "salt lake city, ut": {"salt lake", "salt lake city", "slc", "salt lake city, ut"},
    "jacksonville, fl": {"jacksonville", "jacksonville fl", "jacksonville, fl", "jax"},
    "orlando, fl": {"orlando", "orlando fl", "orlando, fl", "mco"},
    "tampa, fl": {"tampa", "tampa fl", "tampa, fl"},
    "el paso, tx": {"el paso", "el paso tx", "el paso, tx"},
    "san antonio, tx": {"san antonio", "san antonio tx", "san antonio, tx", "sat"},
    "austin, tx": {"austin", "austin tx", "austin, tx", "aus"},
    "oklahoma city, ok": {"oklahoma city", "okc", "oklahoma city ok", "oklahoma city, ok"},
    "laredo, tx": {"laredo", "laredo tx", "laredo, tx"},
    "ontario, ca": {"ontario", "ontario ca", "ontario, ca"},
}


def normalize_city(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    cleaned = cleaned.replace(".", "")
    for canonical, aliases in _CITY_ALIASES.items():
        if cleaned in aliases or cleaned == canonical:
            return canonical
    return cleaned


def cities_match(needle: str | None, haystack: Iterable[str]) -> bool:
    if not needle:
        return True
    n = normalize_city(needle)
    assert n is not None
    normalized_hay = {normalize_city(item) for item in haystack}
    if n in normalized_hay:
        return True
    # Match city name without state: "chicago" vs "chicago, il"
    n_city = n.split(",")[0].strip()
    for h in normalized_hay:
        if not h:
            continue
        h_city = h.split(",")[0].strip()
        if n_city == h_city or n_city in h or h_city in n:
            return True
    return False


ROUTE_RE = re.compile(
    r"^(?P<origin>.+?)\s*(?:->|→|-|—|–|\bto\b)\s*(?P<destination>.+)$",
    re.IGNORECASE,
)


def parse_route_text(text: str) -> SearchQuery:
    text = text.strip()
    match = ROUTE_RE.match(text)
    if match:
        return SearchQuery(
            origin=normalize_city(match.group("origin")),
            destination=normalize_city(match.group("destination")),
        )
    return SearchQuery(origin=normalize_city(text))


class LoadRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._loads: list[Load] = []
        self._watches: list[WatchFilter] = []
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            self._loads = []
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._loads = [Load.model_validate(item) for item in raw]

    def all(self) -> list[Load]:
        return list(self._loads)

    def search(self, query: SearchQuery, limit: int = 25) -> list[Load]:
        results: list[Load] = []
        # One city only → match origin OR destination so users always see loads.
        either_city = query.origin if query.origin and not query.destination else None

        for load in self._loads:
            if either_city:
                if not (
                    cities_match(either_city, load.cities_origin())
                    or cities_match(either_city, load.cities_destination())
                ):
                    continue
            else:
                if not cities_match(query.origin, load.cities_origin()):
                    continue
                if not cities_match(query.destination, load.cities_destination()):
                    continue
            if query.truck_type and query.truck_type.lower() not in load.truck_type.lower():
                continue
            if query.min_weight is not None and load.weight_lbs < query.min_weight:
                continue
            if query.max_weight is not None and load.weight_lbs > query.max_weight:
                continue
            if query.min_rate is not None and (load.rate or 0) < query.min_rate:
                continue
            results.append(load)

        results.sort(key=lambda item: (item.rate is None, -(item.rate or 0), item.weight_lbs))
        return results[:limit]

    def add_watch(self, watch: WatchFilter) -> None:
        self._watches = [
            w
            for w in self._watches
            if not (
                w.user_id == watch.user_id
                and w.origin == watch.origin
                and w.destination == watch.destination
            )
        ]
        self._watches.append(watch)

    def remove_watches(self, user_id: int) -> int:
        before = len(self._watches)
        self._watches = [w for w in self._watches if w.user_id != user_id]
        return before - len(self._watches)

    def watches_for(self, user_id: int) -> list[WatchFilter]:
        return [w for w in self._watches if w.user_id == user_id]

    def matching_watches(self, load: Load) -> list[WatchFilter]:
        matched: list[WatchFilter] = []
        for watch in self._watches:
            if not cities_match(watch.origin, load.cities_origin()):
                continue
            if not cities_match(watch.destination, load.cities_destination()):
                continue
            if watch.truck_type and watch.truck_type.lower() not in load.truck_type.lower():
                continue
            matched.append(watch)
        return matched
