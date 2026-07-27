from __future__ import annotations

import random

from .leads import Lead

SITE_URL = "https://www.fleetguardlogistics.com"
TRIAL_URL = "https://www.fleetguardlogistics.com"
SITE_URL_SPOKEN = "w w w dot fleet guard logistics dot com"


def _first_name(lead: Lead) -> str:
    name = lead.officer or "there"
    if not name or name.lower() == "there":
        return "there"
    return name.split()[0].title()


def link_sms_text(
    lead: Lead,
    *,
    sender_name: str = "Your Name",
) -> str:
    """Short SMS with a real clickable trial link (tap to open website)."""
    first = _first_name(lead)
    company = lead.company or lead.legal_name or "your fleet"
    dot = lead.usdot or "your DOT"
    me = (sender_name or "Your Name").strip() or "Your Name"
    return (
        f"Hi {first}, {me} at FleetGuardAI for {company}. "
        f"Tap this link to open the website and start your 14-day trial "
        f"(then add DOT {dot}):\n"
        f"{SITE_URL}"
    )


def voicemail_spoken_text(
    lead: Lead,
    *,
    sender_name: str = "Your Name",
) -> str:
    """TTS script for a voicemail drop (points them to the SMS tap-link)."""
    first = _first_name(lead)
    company = lead.company or lead.legal_name or "your fleet"
    trucks = lead.power_units or "a few"
    dot = lead.usdot or "your D O T number"
    me = (sender_name or "Your Name").strip() or "Your Name"
    return (
        f"Hi {first}, this is {me} with Fleet Guard A I. "
        f"Quick message for {company}, about {trucks} trucks. "
        f"We keep C D L s, medical cards, insurance, and expirations in one dashboard "
        f"so missing paperwork does not park a truck. "
        f"I just texted you a link — tap that link in the text message to open our website "
        f"and start the 14 day trial. Add D O T {dot} when you sign up. "
        f"The site is also {SITE_URL_SPOKEN}, fleetguardlogistics.com. "
        f"Cancel before day 14 if it is not a fit. Thank you."
    )


def sms_text(
    lead: Lead,
    *,
    sender_name: str = "Your Name",
) -> str:
    """Confident SMS body ready to long-press and copy."""
    first = _first_name(lead)
    company = lead.company or lead.legal_name or "your fleet"
    trucks = lead.power_units or "a few"
    dot = lead.usdot or "your DOT number"
    me = (sender_name or "Your Name").strip() or "Your Name"

    options = [
        (
            f"Hi {first}, {me} with FleetGuardAI. "
            f"{company} (~{trucks} trucks) should not be chasing CDLs, med cards, and expirations by hand. "
            f"We put driver files + due dates in one dashboard and flag what is missing before it stops a truck. "
            f"Start the 14-day trial now: {SITE_URL} → Start Trial → add DOT {dot}."
        ),
        (
            f"{first}, {me} at FleetGuardAI. "
            f"Fleets your size (~{trucks} trucks) lose time and risk when paperwork is scattered. "
            f"FleetGuardAI keeps compliance docs current and shows what expires next — for {company}, DOT {dot}. "
            f"Open {SITE_URL}, hit Start Trial, add your DOT. 14 days. Card required. Cancel anytime before day 14."
        ),
        (
            f"Hi {first} — {me}, FleetGuardAI. "
            f"I looked at {company} (~{trucks} units). You need one system for driver files, insurance, permits, and expirations — not folders and reminders. "
            f"Trial is live: {SITE_URL} → Start 14-Day Trial → DOT {dot}. "
            f"Get the dashboard up today; cancel before day 14 if you do not keep it."
        ),
    ]
    return random.choice(options)


def personalized_pitch(
    lead: Lead,
    *,
    sender_name: str = "Your Name",
    sender_phone: str = "Your Number",
) -> str:
    """Plain-text call / SMS / email scripts with your name filled in."""
    first = _first_name(lead)
    company = lead.company or lead.legal_name or "your fleet"
    trucks = lead.power_units or "a few"
    city_state = ", ".join(p for p in [lead.city, lead.state] if p) or "your area"
    plan = lead.suggested_plan or "a FleetGuard plan"
    dot = lead.usdot or "your DOT number"
    add_on = (lead.add_on or "").strip()
    add_on_line = f" Add-on that fits you: {add_on}." if add_on else ""
    me = (sender_name or "Your Name").strip() or "Your Name"
    my_phone = (sender_phone or "Your Number").strip() or "Your Number"

    call = (
        f"Hi {first}, this is {me} with FleetGuardAI. "
        f"I am calling because fleets like {company} in {city_state} — about {trucks} trucks, DOT {dot} — "
        f"cannot afford missing CDLs, medical cards, insurance, or permits when a truck is ready to roll. "
        f"We put that paperwork in one place, remind you before dates expire, and show what is incomplete on a live dashboard. "
        f"Best next step: go to {SITE_URL}, start the 14-day trial, add DOT {dot}, upload a few files, and you will see gaps immediately. "
        f"For your size I put you on {plan}.{add_on_line} "
        f"Card is required for the trial. Cancel before day 14 if you decide not to continue. "
        f"I can text the link right now."
    )

    voicemail = (
        f"Hi {first}, {me} with FleetGuardAI. "
        f"Calling about {company} — we run DOT compliance docs and expiration tracking for fleets your size. "
        f"Start the 14-day trial at {SITE_URL}, add DOT {dot}, and see what is due before it bites you. "
        f"Call me back at {my_phone}."
    )

    sms = sms_text(lead, sender_name=me)

    email_subject = f"{company}: get expirations under control in 14 days"
    email_body = (
        f"Hi {first},\n\n"
        f"I am reaching out about {company} (~{trucks} trucks, DOT {dot}) in {city_state}.\n\n"
        f"FleetGuardAI is built for fleets that need CDLs, medical cards, insurance, permits, and inspections "
        f"in one system — with reminders before dates expire and a clear view of what is missing.\n\n"
        f"Do this today:\n"
        f"1) Open {TRIAL_URL}\n"
        f"2) Click Start 14-Day Trial\n"
        f"3) Add DOT {dot}\n"
        f"4) Upload a few driver/fleet files\n"
        f"5) Open the dashboard — you will see what needs attention\n\n"
        f"Recommended for your size: {plan}.{add_on_line}\n"
        f"Trial requires a card. Cancel before day 14 to avoid a charge.\n\n"
        f"Site: {SITE_URL}\n"
        f"FMCSA snapshot: {lead.safer_url or 'n/a'}\n\n"
        f"Reply if you want a 10-minute walkthrough while you set it up.\n\n"
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
    """Copy-text button content: SMS only."""
    return sms_text(lead, sender_name=sender_name)


def format_lead_card(
    lead: Lead,
    status: str = "new",
    follow_up_at: str | None = None,
    telegram_username: str = "",
    telegram_user_id: int | None = None,
) -> str:
    """Plain-text lead card (no HTML)."""
    from .phones import to_e164

    officer = lead.officer or "-"
    phone_raw = lead.phone or "-"
    phone_e164 = to_e164(lead.phone) or phone_raw
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
        f"Phone:\n{phone_e164}\n"
        f"Email: {email}"
        f"{tg_line}\n"
        f"Plan: {lead.suggested_plan}\n"
        f"Website: {SITE_URL}\n"
        f"SAFER: {lead.safer_url or '-'}\n"
        f"Status: {status}{follow}"
    )
