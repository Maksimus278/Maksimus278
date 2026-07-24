from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Load(BaseModel):
    id: str
    origin: str
    destination: str
    origin_aliases: list[str] = Field(default_factory=list)
    destination_aliases: list[str] = Field(default_factory=list)
    cargo: str
    weight_lbs: float
    truck_type: str = "dry van"
    rate: Optional[int] = None
    currency: str = "USD"
    payment: str = "quick pay"
    distance_miles: Optional[int] = None
    rate_per_mile: Optional[float] = None
    loading_date: Optional[date] = None
    contact: str = ""
    source: str = "us-board"
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)

    def cities_origin(self) -> set[str]:
        return {self.origin.lower(), *(a.lower() for a in self.origin_aliases)}

    def cities_destination(self) -> set[str]:
        return {self.destination.lower(), *(a.lower() for a in self.destination_aliases)}

    def format_card(self) -> str:
        if self.rate is not None:
            rpm = f" (${self.rate_per_mile:.2f}/mi)" if self.rate_per_mile else ""
            rate_line = f"💰 <b>${self.rate:,}</b>{rpm} · {self.payment}"
        else:
            rate_line = f"💰 rate TBD · {self.payment}"

        date_line = (
            f"📅 pickup: {self.loading_date.isoformat()}"
            if self.loading_date
            else "📅 pickup: ASAP / flexible"
        )
        distance = f" · {self.distance_miles} mi" if self.distance_miles else ""
        notes = f"\n📝 {self.notes}" if self.notes else ""
        contact = f"\n📞 {self.contact}" if self.contact else ""
        weight = f"{self.weight_lbs:,.0f} lbs".replace(",", " ")

        return (
            f"🚚 <b>{self.origin} → {self.destination}</b>{distance}\n"
            f"📦 {self.cargo} · {weight}\n"
            f"🚛 {self.truck_type}\n"
            f"{rate_line}\n"
            f"{date_line}"
            f"{contact}"
            f"{notes}\n"
            f"<i>source: {self.source} · #{self.id}</i>"
        )


class SearchQuery(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    truck_type: Optional[str] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    min_rate: Optional[int] = None


class WatchFilter(BaseModel):
    user_id: int
    origin: Optional[str] = None
    destination: Optional[str] = None
    truck_type: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
