from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from bot.models import Load, SearchQuery, WatchFilter

_CITY_ALIASES: dict[str, set[str]] = {
    "москва": {"мск", "moscow", "москва"},
    "санкт-петербург": {"спб", "питер", "петербург", "санкт-петербург", "st petersburg"},
    "нижний новгород": {"нн", "нижний", "нижний новгород"},
    "екатеринбург": {"екб", "ебург", "екатеринбург"},
    "новосибирск": {"нск", "новосиб", "новосибирск"},
    "казань": {"казань", "kzn"},
    "краснодар": {"краснодар", "крд"},
    "ростов-на-дону": {"ростов", "ростов-на-дону", "rnd"},
    "самара": {"самара", "смр"},
    "челябинск": {"челябинск", "чел"},
    "уфа": {"уфа"},
    "воронеж": {"воронеж"},
    "пермь": {"пермь"},
    "волгоград": {"волгоград"},
    "красноярск": {"красноярск"},
    "тюмень": {"тюмень"},
    "иркутск": {"иркутск"},
    "хабаровск": {"хабаровск"},
    "владивосток": {"владивосток", "влд"},
    "сочи": {"сочи"},
    "тула": {"тула"},
    "тверь": {"тверь"},
    "ярославль": {"ярославль"},
    "рязань": {"рязань"},
    "калининград": {"калининград"},
    "минск": {"минск"},
    "алматы": {"алматы", "алма-ата"},
}


def normalize_city(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    cleaned = cleaned.replace("ё", "е")
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
    return any(n in (h or "") or (h or "") in n for h in normalized_hay if h)


ROUTE_RE = re.compile(
    r"^(?P<origin>.+?)\s*(?:->|→|-|—|–)\s*(?P<destination>.+)$",
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

    def search(self, query: SearchQuery, limit: int = 10) -> list[Load]:
        results: list[Load] = []
        for load in self._loads:
            if not cities_match(query.origin, load.cities_origin()):
                continue
            if not cities_match(query.destination, load.cities_destination()):
                continue
            if query.truck_type and query.truck_type.lower() not in load.truck_type.lower():
                continue
            if query.min_weight is not None and load.weight_tons < query.min_weight:
                continue
            if query.max_weight is not None and load.weight_tons > query.max_weight:
                continue
            if query.min_rate is not None and (load.rate or 0) < query.min_rate:
                continue
            results.append(load)

        results.sort(key=lambda item: (item.rate is None, -(item.rate or 0), item.weight_tons))
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
