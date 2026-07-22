from __future__ import annotations

from .leads import Lead


def personalized_pitch(lead: Lead) -> str:
    """Short call/email pitch tailored to the lead."""
    name = lead.officer or "there"
    first = name.split()[0].title() if name and name.lower() != "there" else "there"
    company = lead.company or lead.legal_name or "your fleet"
    trucks = lead.power_units or "a few"
    city_state = ", ".join(p for p in [lead.city, lead.state] if p) or "your area"
    plan = lead.suggested_plan or "a FleetGuard plan"
    angle = lead.outreach_angle or "keeping CDLs, medical cards, and permits organized with reminders before they expire"

    call = (
        f"Hi {first}, this is [Your Name] with FleetGuardAI. "
        f"You look like about {trucks} trucks out of {city_state}. "
        f"We help fleets like {company} with {angle.lower() if angle[:1].isupper() else angle}. "
        f"Most owners start a 14-day trial — add your DOT number, upload a few files, "
        f"and see what’s missing or coming due. Open to a quick look? "
        f"I’d point you at {plan}."
    )

    email_subject = f"DOT #{lead.usdot} — expiration reminders for {company}"
    email_body = (
        f"Hi {first},\n\n"
        f"I work with fleets around {city_state} on DOT paperwork — "
        f"CDLs, medical cards, insurance, permits — in one place with reminders before dates expire, "
        f"plus a clear view of the public FMCSA record.\n\n"
        f"For {company} (~{trucks} trucks), {plan} is usually the fit. "
        f"{lead.add_on}.\n\n"
        f"Here’s a 14-day trial if you want to see what’s due: https://www.fleetguardlogistics.com\n"
        f"SAFER profile: {lead.safer_url or 'n/a'}\n\n"
        f"Happy to walk through it in 10 minutes.\n"
    )

    return (
        f"📞 Call pitch\n{call}\n\n"
        f"✉️ Email subject\n{email_subject}\n\n"
        f"✉️ Email body\n{email_body}"
    )


def format_lead_card(
    lead: Lead,
    status: str = "new",
    follow_up_at: str | None = None,
    telegram_username: str = "",
    telegram_user_id: int | None = None,
) -> str:
    officer = lead.officer or "—"
    phone = lead.phone or "—"
    email = lead.email or "—"
    location = ", ".join(p for p in [lead.city, lead.state, lead.zip] if p) or "—"
    follow = f"\n📅 Follow-up: {follow_up_at}" if follow_up_at else ""
    if telegram_username:
        tg_line = f"\n💬 Telegram: @{_esc(telegram_username.lstrip('@'))}"
    elif telegram_user_id:
        tg_line = f"\n💬 Telegram id: <code>{telegram_user_id}</code>"
    else:
        tg_line = "\n💬 Telegram: not linked — /settg &lt;phone&gt; &lt;@user|id&gt;"

    return (
        f"<b>{_esc(lead.company)}</b>\n"
        f"USDOT <code>{_esc(lead.usdot)}</code> · {_esc(lead.fit_tier)} · score <b>{lead.effective_score}</b>\n"
        f"🚛 {lead.power_units} trucks · 👤 {lead.drivers} drivers · priority {_esc(lead.priority)}\n"
        f"📍 {_esc(location)}\n"
        f"🧑 {_esc(officer)}\n"
        f"📞 <code>{_esc(phone)}</code>\n"
        f"✉️ <code>{_esc(email)}</code>"
        f"{tg_line}\n"
        f"💼 {_esc(lead.suggested_plan)}\n"
        f"🎯 {_esc(lead.outreach_angle)}\n"
        f"🔗 <a href=\"{_esc(lead.safer_url)}\">SAFER profile</a>\n"
        f"Status: <b>{_esc(status)}</b>{follow}"
    )


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
