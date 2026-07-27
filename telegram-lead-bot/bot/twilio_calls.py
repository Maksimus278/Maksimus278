from __future__ import annotations

import logging
import xml.sax.saxutils as xml

from . import config
from .phones import to_e164

log = logging.getLogger(__name__)


class TwilioCallError(Exception):
    pass


def twilio_configured() -> bool:
    return bool(
        config.TWILIO_ACCOUNT_SID
        and config.TWILIO_AUTH_TOKEN
        and config.TWILIO_FROM_NUMBER
    )


def start_click_to_call(
    *,
    agent_phone: str,
    lead_phone: str,
    company: str = "",
    officer: str = "",
) -> str:
    """Call the agent first; when they answer, bridge to the lead.

    Human-initiated click-to-call only — not an autodialer.
    Returns Twilio Call SID.
    """
    if not twilio_configured():
        raise TwilioCallError(
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in .env / Railway Variables."
        )

    agent = to_e164(agent_phone)
    lead = to_e164(lead_phone)
    from_num = to_e164(config.TWILIO_FROM_NUMBER) or config.TWILIO_FROM_NUMBER
    if not agent:
        raise TwilioCallError("Your phone is missing. Send /setmyphone 5551234567 first.")
    if not lead:
        raise TwilioCallError("This lead has no usable phone number.")
    if agent == lead:
        raise TwilioCallError("Your phone and the lead phone are the same number.")

    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException
    except ImportError as exc:
        raise TwilioCallError("Twilio package not installed. pip install twilio") from exc

    ask = officer or "owner / safety / compliance"
    label = company or "the lead"
    # Brief whisper to agent before dial — then Dial the lead.
    twiml = (
        "<Response>"
        f"<Say voice='Polly.Joanna'>Connecting you to {xml.escape(label)}. "
        f"Ask for {xml.escape(ask)}.</Say>"
        f"<Dial callerId='{xml.escape(from_num)}'>"
        f"<Number>{xml.escape(lead)}</Number>"
        "</Dial>"
        "</Response>"
    )

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    try:
        call = client.calls.create(
            to=agent,
            from_=from_num,
            twiml=twiml,
            timeout=30,
        )
    except TwilioRestException as exc:
        log.exception("Twilio call failed")
        raise TwilioCallError(f"Twilio error {exc.code}: {exc.msg}") from exc

    log.info("Click-to-call started sid=%s agent=%s lead=%s", call.sid, agent, lead)
    return call.sid


def _client():
    if not twilio_configured():
        raise TwilioCallError(
            "Twilio is not configured. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in .env / Railway Variables."
        )
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise TwilioCallError("Twilio package not installed. pip install twilio") from exc
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def leave_voicemail(
    *,
    lead_phone: str,
    spoken_script: str,
) -> str:
    """Call the lead and play a TTS voicemail-style message (human-initiated).

    On Twilio Trial this only works for verified numbers — upgrade required for real leads.
    Returns Call SID.
    """
    lead = to_e164(lead_phone)
    from_num = to_e164(config.TWILIO_FROM_NUMBER) or config.TWILIO_FROM_NUMBER
    if not lead:
        raise TwilioCallError("This lead has no usable phone number.")

    from twilio.base.exceptions import TwilioRestException

    # Pause briefly so many voicemail greetings finish, then leave the message.
    twiml = (
        "<Response>"
        "<Pause length='2'/>"
        f"<Say voice='Polly.Joanna'>{xml.escape(spoken_script)}</Say>"
        "<Pause length='1'/>"
        "</Response>"
    )
    client = _client()
    try:
        call = client.calls.create(
            to=lead,
            from_=from_num,
            twiml=twiml,
            timeout=45,
            machine_detection="DetectMessageEnd",
        )
    except TwilioRestException as exc:
        log.exception("Twilio voicemail failed")
        raise TwilioCallError(f"Twilio error {exc.code}: {exc.msg}") from exc

    log.info("Voicemail call started sid=%s lead=%s", call.sid, lead)
    return call.sid


def send_link_sms(
    *,
    lead_phone: str,
    body: str,
) -> str:
    """Send one SMS with a clickable https link (human tapped the button)."""
    lead = to_e164(lead_phone)
    from_num = to_e164(config.TWILIO_FROM_NUMBER) or config.TWILIO_FROM_NUMBER
    if not lead:
        raise TwilioCallError("This lead has no usable phone number.")
    if not body.strip():
        raise TwilioCallError("SMS body is empty.")

    from twilio.base.exceptions import TwilioRestException

    client = _client()
    try:
        msg = client.messages.create(
            to=lead,
            from_=from_num,
            body=body.strip()[:1500],
        )
    except TwilioRestException as exc:
        log.exception("Twilio SMS failed")
        raise TwilioCallError(f"Twilio SMS error {exc.code}: {exc.msg}") from exc

    log.info("Link SMS sent sid=%s lead=%s", msg.sid, lead)
    return msg.sid
