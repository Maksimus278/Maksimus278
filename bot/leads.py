from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from bot.models import Load, utc_now


PHONE_RE = re.compile(r"(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}")


@dataclass
class Lead:
    company: str
    contact_name: str
    phone: str
    origin: str
    destination: str
    rate: Optional[int]
    equipment: str
    load_id: str
    source: str
    pickup: str = ""
    created_at: datetime = field(default_factory=utc_now)

    @property
    def key(self) -> str:
        phone = re.sub(r"\D", "", self.phone)[-10:]
        company = self.company.lower().strip()
        return f"{phone}|{company}"

    def format_card(self, index: int | None = None) -> str:
        prefix = f"<b>LEAD #{index}</b>\n" if index is not None else "<b>LEAD</b>\n"
        rate = f"${self.rate:,}" if self.rate else "rate TBD"
        contact = self.contact_name or "Dispatch"
        pickup = f"\n📅 pickup: {self.pickup}" if self.pickup else ""
        return (
            f"{prefix}"
            f"🏢 <b>{self.company or 'Broker'}</b>\n"
            f"👤 {contact}\n"
            f"📞 <code>{self.phone}</code>\n"
            f"🚚 {self.origin} → {self.destination}\n"
            f"🚛 {self.equipment} · 💰 {rate}"
            f"{pickup}\n"
            f"<i>{self.source} · #{self.load_id}</i>"
        )


def parse_contact_parts(contact: str) -> tuple[str, str, str]:
    """Split 'Company · Name · Phone' into parts."""
    parts = [p.strip() for p in (contact or "").split("·") if p.strip()]
    company = parts[0] if parts else ""
    contact_name = ""
    phone = ""
    phones = PHONE_RE.findall(contact or "")
    if phones:
        digits = re.sub(r"\D", "", phones[-1])
        if len(digits) == 10:
            phone = f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            phone = f"+{digits}"
        else:
            phone = digits
    for part in parts[1:]:
        if PHONE_RE.search(part):
            continue
        contact_name = part
        break
    return company, contact_name, phone


def lead_from_load(load: Load) -> Lead | None:
    company, contact_name, phone = parse_contact_parts(load.contact)
    if not phone:
        return None
    return Lead(
        company=company or "Broker",
        contact_name=contact_name or "Dispatch",
        phone=phone,
        origin=load.origin,
        destination=load.destination,
        rate=load.rate,
        equipment=load.truck_type,
        load_id=load.id,
        source=load.source,
        pickup=load.loading_date.isoformat() if load.loading_date else "",
    )


def unique_leads(loads: Iterable[Load], limit: int = 20) -> list[Lead]:
    seen: set[str] = set()
    leads: list[Lead] = []
    ordered = sorted(loads, key=lambda item: (item.rate is None, -(item.rate or 0)))
    for load in ordered:
        lead = lead_from_load(load)
        if lead is None or lead.key in seen:
            continue
        seen.add(lead.key)
        leads.append(lead)
        if len(leads) >= limit:
            break
    return leads
