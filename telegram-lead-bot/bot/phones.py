from __future__ import annotations

import re


def normalize_phone(raw: str | None) -> str:
    """Normalize to digits-only, keep leading country code when present.

    US 10-digit numbers are stored as 1XXXXXXXXXX for consistent matching.
    """
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if not digits:
        return ""
    if len(digits) == 10:
        return "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    return digits


def to_e164(raw: str | None) -> str:
    """Return +E164 style phone for contacts / dialers, or empty string."""
    digits = normalize_phone(raw)
    if not digits:
        return ""
    return f"+{digits}"


def contact_name_parts(officer: str = "", company: str = "") -> tuple[str, str]:
    """Build first/last name for a Telegram contact card."""
    officer = (officer or "").strip()
    company = (company or "").strip()
    if officer:
        parts = officer.split()
        first = parts[0][:64]
        last = " ".join(parts[1:])[:64] if len(parts) > 1 else (company[:64] if company else "")
        return first, last
    if company:
        return company[:64], "FleetGuard lead"
    return "Fleet lead", ""


def phone_match_keys(raw: str | None) -> set[str]:
    """Possible normalized forms for loose matching against CSV phones."""
    n = normalize_phone(raw)
    if not n:
        return set()
    keys = {n}
    if len(n) == 11 and n.startswith("1"):
        keys.add(n[1:])
    elif len(n) == 10:
        keys.add("1" + n)
    return keys


def phones_equal(a: str | None, b: str | None) -> bool:
    ka, kb = phone_match_keys(a), phone_match_keys(b)
    return bool(ka & kb)
