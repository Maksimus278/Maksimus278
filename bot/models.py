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
    weight_tons: float
    volume_m3: Optional[float] = None
    truck_type: str = "тент"
    rate: Optional[int] = None
    currency: str = "RUB"
    payment: str = "на карту"
    distance_km: Optional[int] = None
    loading_date: Optional[date] = None
    contact: str = ""
    source: str = "board"
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)

    def cities_origin(self) -> set[str]:
        return {self.origin.lower(), *(a.lower() for a in self.origin_aliases)}

    def cities_destination(self) -> set[str]:
        return {self.destination.lower(), *(a.lower() for a in self.destination_aliases)}

    def format_card(self) -> str:
        rate_line = (
            f"💰 <b>{self.rate:,} {self.currency}</b> · {self.payment}".replace(",", " ")
            if self.rate
            else f"💰 ставка договорная · {self.payment}"
        )
        date_line = (
            f"📅 погрузка: {self.loading_date.isoformat()}"
            if self.loading_date
            else "📅 погрузка: сегодня / по договорённости"
        )
        distance = f" · {self.distance_km} км" if self.distance_km else ""
        volume = f" / {self.volume_m3:g} м³" if self.volume_m3 else ""
        notes = f"\n📝 {self.notes}" if self.notes else ""
        contact = f"\n📞 {self.contact}" if self.contact else ""

        return (
            f"🚚 <b>{self.origin} → {self.destination}</b>{distance}\n"
            f"📦 {self.cargo} · {self.weight_tons:g} т{volume}\n"
            f"🚛 {self.truck_type}\n"
            f"{rate_line}\n"
            f"{date_line}"
            f"{contact}"
            f"{notes}\n"
            f"<i>источник: {self.source} · #{self.id}</i>"
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
