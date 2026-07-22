from __future__ import annotations

from .leads import Lead

SITE_URL = "https://www.fleetguardlogistics.com"
TRIAL_URL = "https://www.fleetguardlogistics.com"


def personalized_pitch(
    lead: Lead,
    *,
    sender_name: str = "Your Name",
    sender_phone: str = "Your Number",
) -> str:
    """Plain-text call / SMS / email scripts with your name filled in."""
    name = lead.officer or "there"
    first = name.split()[0].title() if name and name.lower() != "there" else "there"
    company = lead.company or lead.legal_name or "your fleet"
    trucks = lead.power_units or "a few"
    city_state = ", ".join(p for p in [lead.city, lead.state] if p) or "your area"
    plan = lead.suggested_plan or "a FleetGuard plan"
    dot = lead.usdot or "your DOT number"
    add_on = (lead.add_on or "").strip()
    add_on_line = f" {add_on}." if add_on else ""
    me = (sender_name or "Your Name").strip() or "Your Name"
    my_phone = (sender_phone or "Your Number").strip() or "Your Number"

    call = (
        f"Hi {first}, this is {me} with FleetGuardAI. "
        f"We help trucking fleets keep CDLs, medical cards, insurance, and permits "
        f"in one place so missing paperwork does not stop the day. "
        f"I was looking at {company} out of {city_state}, about {trucks} trucks, DOT {dot}. "
        f"With a fleet that size, expirations and driver files add up fast. "
        f"Easy next step: go to {SITE_URL}, click Start 14-Day Trial, add DOT {dot}, "
        f"upload a few documents, and the dashboard shows what is missing or coming due. "
        f"Card is required for the trial. Cancel before day 14 if it is not a fit. "
        f"I can text you the link right now. For your size I would start on {plan}.{add_on_line}"
    )

    voicemail = (
        f"Hi {first}, {me} with FleetGuardAI. "
        f"We organize fleet paperwork and expiration reminders for carriers like {company}. "
        f"Start a 14-day trial at {SITE_URL}. Add your DOT number, upload files, "
        f"see what needs attention. Happy to walk you through it. {my_phone}."
    )

    sms = (
        f"Hi {first}, {me} at FleetGuardAI. "
        f"For {company} (~{trucks} trucks): keep driver files and expirations in one place. "
        f"14-day trial: {SITE_URL} -> Start Trial -> add DOT {dot}. "
        f"Cancel before day 14 if it is not useful."
    )

    email_subject = f"{company}: see what is due before it expires (14-day trial)"
    email_body = (
        f"Hi {first},\n\n"
        f"Quick note for {company} (~{trucks} trucks, DOT {dot}) in {city_state}.\n\n"
        f"FleetGuardAI keeps CDLs, medical cards, insurance, permits, and inspection files "
        f"in one place, sends reminders before dates expire, and lets you check your public "
        f"DOT/FMCSA record without hunting around.\n\n"
        f"Start here:\n"
        f"1) Open {TRIAL_URL}\n"
        f"2) Click Start 14-Day Trial\n"
        f"3) Add DOT {dot}\n"
        f"4) Upload a few driver/fleet files\n"
        f"5) Open the dashboard to see what is missing or coming due\n\n"
        f"Suggested plan for your size: {plan}.{add_on_line}\n"
        f"Trial requires a card. Cancel before day 14 to avoid a charge.\n\n"
        f"Website: {SITE_URL}\n"
        f"FMCSA snapshot: {lead.safer_url or 'n/a'}\n\n"
        f"If easier, reply and I can do a 10-minute screen share while you set it up.\n\n"
        f"Thanks,\n"
        f"{me}\n"
        f"FleetGuardAI\n"
        f"{SITE_URL}\n"
        f"{my_phone}\n"
    )

    return (
        f"CALL\n{call}\n\n"
        f"VOICEMAIL\n{voicemail}\n\n"
        f"SMS\n{sms}\n\n"
        f"EMAIL SUBJECT\n{email_subject}\n\n"
        f"EMAIL BODY\n{email_body}"
    )


def copy_text_version(
    lead: Lead,
    *,
    sender_name: str = "Your Name",
    sender_phone: str = "Your Number",
) -> str:
    """Single clean plain-text block meant for long-press copy in Telegram."""
    return personalized_pitch(
        lead,
        sender_name=sender_name,
        sender_phone=sender_phone,
    )


def format_lead_card(
    lead: Lead,
    status: str = "new",
    follow_up_at: str | None = None,
    telegram_username: str = "",
    telegram_user_id: int | None = None,
) -> str:
    """Plain-text lead card (no HTML)."""
    officer = lead.officer or "-"
    phone = lead.phone or "-"
    email = lead.email or "-"
    location = ", ".join(p for p in [lead.city, lead.state, lead.zip] if p) or "-"
    follow = f"\nFollow-up: {follow_up_at}" if follow_up_at else ""
    if telegram_username:
        tg_line = f"\nTelegram: @{telegram_username.lstrip('@')}"
    elif telegram_user_id:
        tg_line = f"\nTelegram id: {telegram_user_id}"
    else:
        tg_line = "\nTelegram: not linked (use /settg <phone> <@user|id>)"

    return (
        f"{lead.company}\n"
        f"USDOT {lead.usdot} | {lead.fit_tier}\n"
        f"Trucks: {lead.power_units} | Drivers: {lead.drivers}\n"
        f"{lead.truck_match_label()}\n"
        f"Location: {location}\n"
        f"Contact: {officer}\n"
        f"Phone: {phone}\n"
        f"Email: {email}"
        f"{tg_line}\n"
        f"Plan: {lead.suggested_plan}\n"
        f"Website: {SITE_URL}\n"
        f"SAFER: {lead.safer_url or '-'}\n"
        f"Status: {status}{follow}"
    )
