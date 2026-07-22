from __future__ import annotations

from .leads import Lead

SITE_URL = "https://www.fleetguardlogistics.com"
TRIAL_URL = "https://www.fleetguardlogistics.com"


def personalized_pitch(lead: Lead) -> str:
    """Call + email pitch that drives the prospect to the website trial."""
    name = lead.officer or "there"
    first = name.split()[0].title() if name and name.lower() != "there" else "there"
    company = lead.company or lead.legal_name or "your fleet"
    trucks = lead.power_units or "a few"
    city_state = ", ".join(p for p in [lead.city, lead.state] if p) or "your area"
    plan = lead.suggested_plan or "a FleetGuard plan"
    dot = lead.usdot or "your DOT number"
    add_on = (lead.add_on or "").strip()
    add_on_line = f" {add_on}." if add_on else ""

    call = (
        f"Hi {first}, this is [Your Name] with FleetGuardAI — "
        f"we help trucking fleets keep CDLs, medical cards, insurance, and permits "
        f"in one place so missing paperwork doesn’t stop the day.\n\n"
        f"I was looking at {company} out of {city_state} — about {trucks} trucks, "
        f"DOT {dot}. With a fleet that size, expirations and driver files add up fast.\n\n"
        f"Here’s the easy next step: go to FleetGuardLogistics.com, hit Start 14-Day Trial, "
        f"add DOT {dot}, upload a few documents, and the dashboard shows what’s missing "
        f"or coming due. Card’s required for the trial; cancel before day 14 if it’s not a fit.\n\n"
        f"Want me to text/email you the link right now? It’s {SITE_URL} — "
        f"for you I’d start on {plan}.{add_on_line}"
    )

    voicemail = (
        f"Hi {first}, [Your Name] with FleetGuardAI. "
        f"We organize fleet paperwork and expiration reminders for carriers like {company}. "
        f"Start a free 14-day trial at FleetGuardLogistics.com — add your DOT number, "
        f"upload files, see what needs attention. Link: {SITE_URL}. "
        f"Happy to walk you through it — [Your Number]."
    )

    sms = (
        f"Hi {first} — [Your Name] @ FleetGuardAI. "
        f"For {company} (~{trucks} trucks): keep driver files + expirations in one place. "
        f"14-day trial → {SITE_URL} → Start Trial → add DOT {dot}. "
        f"Cancel before day 14 if it’s not useful."
    )

    email_subject = f"{company}: see what’s due before it expires (14-day trial)"
    email_body = (
        f"Hi {first},\n\n"
        f"Quick note for {company} (~{trucks} trucks, DOT {dot}) in {city_state}.\n\n"
        f"FleetGuardAI keeps CDLs, medical cards, insurance, permits, and inspection files "
        f"in one place, sends reminders before dates expire, and lets you check your public "
        f"DOT/FMCSA record without hunting around.\n\n"
        f"Start here (takes a few minutes):\n"
        f"1) Open {TRIAL_URL}\n"
        f"2) Click Start 14-Day Trial\n"
        f"3) Add DOT {dot}\n"
        f"4) Upload a few driver/fleet files\n"
        f"5) Open the dashboard — it shows what’s missing or coming due\n\n"
        f"Suggested plan for your size: {plan}.{add_on_line}\n"
        f"Trial requires a card; cancel before day 14 to avoid a charge.\n\n"
        f"Website: {SITE_URL}\n"
        f"Your FMCSA snapshot: {lead.safer_url or 'n/a'}\n\n"
        f"If easier, reply and I’ll hop on a 10-minute screen share while you set it up.\n\n"
        f"Thanks,\n"
        f"[Your Name]\n"
        f"FleetGuardAI\n"
        f"{SITE_URL}\n"
    )

    how_to_send = (
        "How to direct them to the site\n"
        f"• Say the name out loud: “FleetGuardLogistics.com”\n"
        f"• Send the link: {SITE_URL}\n"
        f"• Tell them the 4 clicks: Start 14-Day Trial → add DOT {dot} → upload files → open dashboard\n"
        f"• Soft close: “If it’s not useful, cancel before day 14.”"
    )

    return (
        f"📞 Call pitch\n{call}\n\n"
        f"📱 Voicemail\n{voicemail}\n\n"
        f"💬 SMS / text\n{sms}\n\n"
        f"✉️ Email subject\n{email_subject}\n\n"
        f"✉️ Email body\n{email_body}\n"
        f"{how_to_send}"
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
        f"USDOT <code>{_esc(lead.usdot)}</code> · {_esc(lead.fit_tier)}\n"
        f"🚛 <b>{lead.power_units} trucks</b> · 👤 {lead.drivers} drivers\n"
        f"🎯 {_esc(lead.truck_match_label())}\n"
        f"📍 {_esc(location)}\n"
        f"🧑 {_esc(officer)}\n"
        f"📞 <code>{_esc(phone)}</code>\n"
        f"✉️ <code>{_esc(email)}</code>"
        f"{tg_line}\n"
        f"💼 {_esc(lead.suggested_plan)}\n"
        f"🌐 <a href=\"{_esc(SITE_URL)}\">FleetGuardLogistics.com</a> · 14-day trial\n"
        f"📝 {_esc(lead.outreach_angle)}\n"
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
