from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Optional

import aiohttp

from bot.models import Load, SearchQuery

logger = logging.getLogger(__name__)

RADIUS_API_BASE = "https://zqk7up8crd.execute-api.us-east-2.amazonaws.com/default"
LOADBOARD_PAGE = "https://www.trulos.com/load-board/"
LOADBOARD_API = "https://www.trulos.com/loadboard.php"

EQUIP_TO_GROUP = {
    "dry van": "van",
    "van": "van",
    "тент": "van",
    "reefer": "reefer",
    "рефрижератор": "reefer",
    "flatbed": "flatbed",
    "открытая": "flatbed",
    "step deck": "stepdeck",
    "hotshot": "hotshot",
    "power only": "power",
    "box truck": "van",
}

HUBS = [
    ("Chicago", "IL"),
    ("Dallas", "TX"),
    ("Los Angeles", "CA"),
    ("Atlanta", "GA"),
    ("Houston", "TX"),
    ("Phoenix", "AZ"),
    ("New York", "NY"),
    ("Memphis", "TN"),
    ("Indianapolis", "IN"),
    ("Columbus", "OH"),
]


def _city_query(value: str | None) -> str:
    if not value:
        return ""
    # "los angeles, ca" / "chicago, il" → "Los Angeles" / "Chicago"
    cleaned = value.split(",")[0].strip()
    return cleaned.title()


def _parse_rate(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    text = str(raw).replace(",", "").replace("$", "").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return int(round(value))


def _parse_weight_lbs(raw: Any) -> float:
    if raw is None or raw == "":
        return 0.0
    try:
        value = float(str(raw).replace(",", "").strip())
    except ValueError:
        return 0.0
    # Some Trulos endpoints return weight in thousands (48.00 => 48000 lbs).
    if 0 < value < 1000:
        return value * 1000
    return value


def _parse_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _equip_group(truck_type: str | None) -> str:
    if not truck_type:
        return ""
    return EQUIP_TO_GROUP.get(truck_type.lower().strip(), "")


def map_trulos_row(row: dict[str, Any]) -> Load:
    origin_city = str(row.get("OriginCity") or row.get("originCity") or "").title()
    origin_state = str(row.get("OriginState") or row.get("originState") or "").upper()
    dest_city = str(row.get("DestinationCity") or row.get("destinationCity") or "").title()
    dest_state = str(row.get("DestinationState") or row.get("destinationState") or "").upper()
    origin = f"{origin_city}, {origin_state}".strip(", ")
    destination = f"{dest_city}, {dest_state}".strip(", ")
    rate = _parse_rate(row.get("Rate") if "Rate" in row else row.get("rate"))
    miles_raw = row.get("DistanceMiles") or row.get("distanceMiles") or row.get("Miles")
    miles = int(float(miles_raw)) if miles_raw not in (None, "") else None
    rpm = round(rate / miles, 2) if rate and miles and miles > 0 else None
    company = str(row.get("CompanyName") or row.get("companyName") or "").strip()
    contact_name = str(row.get("ContactName") or row.get("contactName") or "").strip()
    phone = str(row.get("ContactPhone") or row.get("contactPhone") or "").strip()
    contact = " · ".join(p for p in (company, contact_name, phone) if p)
    comment = str(row.get("Comment") or row.get("comment") or "").strip()
    load_id = str(row.get("LoadID") or row.get("loadId") or row.get("id") or "NA")
    equipment = str(row.get("Equipment") or row.get("equipment") or "dry van")
    weight = _parse_weight_lbs(row.get("Weight") if "Weight" in row else row.get("weight"))
    size = str(row.get("loadSize") or row.get("LoadSize") or "").strip()
    notes = " · ".join(p for p in (size, comment) if p)

    return Load(
        id=f"TR-{load_id}",
        origin=origin or "Unknown",
        destination=destination or "Unknown",
        origin_aliases=[origin_city] if origin_city else [],
        destination_aliases=[dest_city] if dest_city else [],
        cargo=notes or "Freight",
        weight_lbs=weight or 0,
        truck_type=equipment.lower(),
        rate=rate,
        currency="USD",
        payment="see broker",
        distance_miles=miles,
        rate_per_mile=rpm,
        loading_date=_parse_date(row.get("PickupDate") or row.get("pickupDate")),
        contact=contact,
        source="Trulos (live)",
        notes=notes,
    )


class TrulosClient:
    """Live US loads from Trulos public load board APIs."""

    def __init__(self, timeout: float = 25.0) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._token: str | None = None
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; ProxyBot/1.0; +https://t.me/Proxy007Bot)"
            ),
            "Accept": "application/json,text/html,*/*",
        }

    async def _session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(timeout=self.timeout, headers=self._headers)

    async def refresh_token(self) -> str | None:
        async with await self._session() as session:
            async with session.get(LOADBOARD_PAGE) as resp:
                text = await resp.text()
        match = re.search(r'TRULOS_PUBLIC_LOADBOARD_TOKEN="([^"]+)"', text)
        self._token = match.group(1) if match else None
        return self._token

    async def geo_search(self, query: str) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        url = f"{RADIUS_API_BASE}/geo/search"
        async with await self._session() as session:
            async with session.get(url, params={"q": query}) as resp:
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        suggestions = payload.get("suggestions") if isinstance(payload, dict) else payload
        return list(suggestions or [])

    async def resolve_city(self, query: str | None) -> Optional[dict[str, Any]]:
        city = _city_query(query)
        if not city:
            return None
        suggestions = await self.geo_search(city)
        if not suggestions:
            return None
        # Prefer exact city name match.
        lower = city.lower()
        for item in suggestions:
            if str(item.get("city", "")).lower() == lower:
                return item
        return suggestions[0]

    async def radius_loads(
        self,
        lat: float,
        lng: float,
        *,
        radius: int = 150,
        search_type: str = "origin",
        equip_group: str = "",
        limit: int = 100,
        rates_only: bool = False,
    ) -> list[Load]:
        params: dict[str, Any] = {
            "lat": lat,
            "lng": lng,
            "radius": radius,
            "searchType": search_type,
            "limit": limit,
        }
        if equip_group:
            params["equipGroup"] = equip_group
        if rates_only:
            params["filterRate"] = "true"
            params["ratesOnly"] = "true"
        url = f"{RADIUS_API_BASE}/loads/radius"
        async with await self._session() as session:
            async with session.get(url, params=params) as resp:
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        rows = []
        if isinstance(payload, dict):
            rows = payload.get("loads") or payload.get("Loads") or payload.get("data") or []
        elif isinstance(payload, list):
            rows = payload
        return [map_trulos_row(row) for row in rows if isinstance(row, dict)]

    async def state_loads(self, states: list[str], *, limit: int = 100, equip_group: str = "") -> list[Load]:
        if not self._token:
            await self.refresh_token()
        params: dict[str, Any] = {
            "path": "loads",
            "originStates": ",".join(states),
            "limit": limit,
        }
        if equip_group:
            params["equipGroup"] = equip_group
        headers = {
            **self._headers,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LOADBOARD_PAGE,
        }
        if self._token:
            headers["X-Trulos-Loadboard-Token"] = self._token
        async with await self._session() as session:
            async with session.get(LOADBOARD_API, params=params, headers=headers) as resp:
                if resp.status == 403:
                    await self.refresh_token()
                    if self._token:
                        headers["X-Trulos-Loadboard-Token"] = self._token
                    async with session.get(LOADBOARD_API, params=params, headers=headers) as retry:
                        retry.raise_for_status()
                        payload = await retry.json(content_type=None)
                else:
                    resp.raise_for_status()
                    payload = await resp.json(content_type=None)
        rows = payload.get("loads") if isinstance(payload, dict) else payload
        return [map_trulos_row(row) for row in (rows or []) if isinstance(row, dict)]

    async def search(self, query: SearchQuery, *, limit: int = 25, radius: int = 200) -> list[Load]:
        equip = _equip_group(query.truck_type)
        origin = await self.resolve_city(query.origin)
        destination = await self.resolve_city(query.destination) if query.destination else None

        loads: list[Load] = []
        if origin:
            loads = await self.radius_loads(
                float(origin["lat"]),
                float(origin["lng"]),
                radius=radius,
                search_type="origin",
                equip_group=equip,
                limit=max(limit * 3, 60),
            )
            if destination:
                dest_city = str(destination.get("city", "")).lower()
                dest_state = str(destination.get("state", "")).lower()
                filtered = []
                for load in loads:
                    hay = f"{load.destination}".lower()
                    if dest_city and dest_city in hay:
                        filtered.append(load)
                    elif dest_state and f", {dest_state}" in hay:
                        filtered.append(load)
                # If destination filter is too strict, keep nearby origin results
                # but prefer filtered matches when present.
                if filtered:
                    loads = filtered
        elif destination:
            loads = await self.radius_loads(
                float(destination["lat"]),
                float(destination["lng"]),
                radius=radius,
                search_type="destination",
                equip_group=equip,
                limit=max(limit * 3, 60),
            )
        else:
            # Browse mode: pull from major hubs.
            for city, state in HUBS[:5]:
                try:
                    geo = await self.resolve_city(f"{city}, {state}")
                    if not geo:
                        continue
                    chunk = await self.radius_loads(
                        float(geo["lat"]),
                        float(geo["lng"]),
                        radius=120,
                        equip_group=equip,
                        limit=30,
                    )
                    loads.extend(chunk)
                except Exception:
                    logger.exception("Hub fetch failed for %s, %s", city, state)

        # De-dupe by id, prefer rated loads first.
        uniq: dict[str, Load] = {}
        for load in loads:
            uniq.setdefault(load.id, load)
        result = list(uniq.values())
        result.sort(key=lambda item: (item.rate is None, -(item.rate or 0)))
        return result[:limit]
