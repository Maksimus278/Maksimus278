from __future__ import annotations

import logging
from functools import wraps

from telegram import Update
from telegram.error import BadRequest, RetryAfter, TelegramError
from telegram.ext import ContextTypes

from . import config
from .keyboards import lead_keyboard, remove_keyboard, search_keyboard, share_contact_keyboard
from .leads import LeadStore
from .phones import contact_name_parts, normalize_phone, to_e164
from .pitches import copy_text_version, format_lead_card, personalized_pitch

log = logging.getLogger(__name__)


def _is_benign_telegram_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "message is not modified" in text
        or "query is too old" in text
        or "query id is invalid" in text
        or "message to edit not found" in text
    )


def allowed_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not config.is_allowed(user.id, user.username):
            if update.message:
                await update.message.reply_text(
                    "Unauthorized. This bot is locked to its owner.\n"
                    "Allowed: configured Telegram ids / usernames "
                    "(e.g. @mixerius)."
                )
            elif update.callback_query:
                try:
                    await update.callback_query.answer("Unauthorized", show_alert=True)
                except TelegramError:
                    pass
            return
        try:
            return await func(update, context, *args, **kwargs)
        except RetryAfter as exc:
            wait = int(getattr(exc, "retry_after", 30)) + 1
            msg = f"Telegram rate limit. Wait {wait} seconds, then try again."
            log.warning("RetryAfter: wait %ss", wait)
            if update.callback_query:
                try:
                    await update.callback_query.answer(msg, show_alert=True)
                except TelegramError:
                    pass
                try:
                    await update.callback_query.message.reply_text(msg)
                except TelegramError:
                    pass
            elif update.effective_message:
                try:
                    await update.effective_message.reply_text(msg)
                except TelegramError:
                    pass
        except BadRequest as exc:
            if _is_benign_telegram_error(exc):
                log.info("Ignoring benign Telegram error: %s", exc)
                return
            log.exception("Telegram BadRequest in handler")
            if update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "Could not update that message. Send /next again."
                    )
                except TelegramError:
                    pass
        except TelegramError as exc:
            if _is_benign_telegram_error(exc):
                log.info("Ignoring benign Telegram error: %s", exc)
                return
            log.exception("Telegram error in handler")
            if update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "Telegram glitch. Send /next again."
                    )
                except TelegramError:
                    pass

    return wrapper


def store(context: ContextTypes.DEFAULT_TYPE) -> LeadStore:
    return context.application.bot_data["store"]


def _tg_bits(lead_store: LeadStore, usdot: str) -> tuple[str, int | None]:
    row = lead_store.get_telegram_for_lead(usdot)
    if not row:
        return "", None
    return (row["telegram_username"] or ""), row["telegram_user_id"]


def _sender_bits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, str]:
    user = update.effective_user
    fallback = ""
    if user:
        fallback = " ".join(p for p in [user.first_name, user.last_name] if p).strip()
    return store(context).resolve_sender(user.id if user else 0, fallback)


async def send_lead_contact(message, lead) -> bool:
    """Send one tappable Telegram contact card (save / call / message)."""
    phone = to_e164(lead.phone)
    if not phone:
        await message.reply_text("No phone number on file for this lead.")
        return False
    first, last = contact_name_parts(lead.officer, lead.company)
    try:
        await message.reply_contact(
            phone_number=phone,
            first_name=first,
            last_name=last or None,
        )
    except RetryAfter as exc:
        wait = int(getattr(exc, "retry_after", 30)) + 1
        await message.reply_text(
            f"Telegram rate limit on contacts. Wait {wait}s.\n"
            f"Phone to dial/message manually:\n{phone}"
        )
        return False
    except BadRequest as exc:
        await message.reply_text(
            f"Could not send contact card ({exc}).\nPhone:\n{phone}"
        )
        return False
    return True


async def send_lead(update: Update, context: ContextTypes.DEFAULT_TYPE, usdot: str) -> None:
    lead_store = store(context)
    lead = lead_store.get_lead(usdot)
    if not lead:
        target = update.effective_message
        if target:
            await target.reply_text(f"Lead {usdot} not found.")
        return

    state = lead_store.get_status(usdot)
    status = state["status"] if state else "new"
    follow_up_at = state["follow_up_at"] if state else None
    lead_store.mark_viewed(usdot)
    tg_user, tg_id = _tg_bits(lead_store, usdot)
    sender_name, _sender_phone = _sender_bits(update, context)

    card = format_lead_card(
        lead,
        status=status,
        follow_up_at=follow_up_at,
        telegram_username=tg_user,
        telegram_user_id=tg_id,
    )
    keyboard = lead_keyboard(lead.usdot, lead.phone, lead.email, telegram_username=tg_user)
    phone = to_e164(lead.phone) or lead.phone or "no phone"

    tip = (
        f"Name on SMS: {sender_name} (/setname to change)\n"
        f"Phone: {phone}\n"
        f"Tap Save / Message to open contact (call/message/save)\n"
        f"Tap Copy SMS for the text to paste"
    )

    # Always send a NEW message (never edit). Editing causes freezes when content is unchanged.
    msg = update.effective_message
    if update.callback_query and update.callback_query.message:
        msg = update.callback_query.message
    if not msg:
        return
    await msg.reply_text(card, reply_markup=keyboard, disable_web_page_preview=True)
    await msg.reply_text(tip)


def _truck_kwargs() -> dict:
    return {
        "target_trucks": config.TARGET_TRUCKS,
        "truck_min": config.TARGET_TRUCK_MIN,
        "truck_max": config.TARGET_TRUCK_MAX,
    }


@allowed_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lead_store = store(context)
    stats = lead_store.stats()
    await update.effective_message.reply_text(
        "FleetGuard lead bot ready.\n\n"
        f"Loaded {stats['total_leads']:,} leads from CSV.\n"
        f"Priority target: fleets with ~{config.TARGET_TRUCKS} trucks "
        f"({config.TARGET_TRUCK_MIN}–{config.TARGET_TRUCK_MAX}).\n\n"
        "Commands:\n"
        "/next — next best ~300-truck lead + pitch\n"
        "/highscore — fleets closest to ~300 trucks\n"
        "/search <query> — find a company / DOT / city\n"
        "/followups — who needs follow-up\n"
        "/stats — your progress\n"
        "/linkphone — share contact to save your phone → Telegram id\n"
        "/settg <phone|DOT> <@user|id> — link Telegram to a lead phone\n"
        "/findtg <phone> — look up a saved Telegram id by phone\n"
        "/tglist — recent phone → Telegram links\n"
        "/setname Your Name — put your name into copy-text pitches\n"
        "/setmyphone 5551234567 — put your number into voicemail/email\n"
        "/myname — show saved name/number\n\n"
        "Tap Copy SMS under each lead for a text ready to paste.\n"
        "Note: Telegram cannot auto-discover strangers’ ids from CSV phones. "
        "Share a contact or set them with /settg.",
    )


@allowed_only
async def next_lead(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    leads = store(context).next_best(1, **_truck_kwargs())
    if not leads:
        await update.effective_message.reply_text("No new leads left. Check /followups or /stats.")
        return
    await send_lead(update, context, leads[0].usdot)


@allowed_only
async def highscore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = store(context).high_score(config.HIGH_SCORE_LIMIT, **_truck_kwargs())
    if not rows:
        await update.effective_message.reply_text("No leads loaded.")
        return
    target = config.TARGET_TRUCKS
    lines = [
        f"🚛 Fleets closest to ~{target} trucks\n"
        f"Band {config.TARGET_TRUCK_MIN}–{config.TARGET_TRUCK_MAX} · nearest to {target} first\n",
    ]
    usdots = []
    for i, (lead, status) in enumerate(rows, 1):
        usdots.append(lead.usdot)
        dist = lead.truck_distance(target)
        lines.append(
            f"{i}. {lead.company} · {lead.power_units} trucks "
            f"(Δ{dist} from {target})\n"
            f"   {lead.city}, {lead.state} · {status} · DOT {lead.usdot}\n"
            f"   {lead.suggested_plan} · {lead.phone or 'no phone'}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=search_keyboard(usdots),
        disable_web_page_preview=True
    )


@allowed_only
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.effective_message.reply_text("Usage: /search trucking company")
        return
    hits = store(context).search(query, config.SEARCH_LIMIT)
    if not hits:
        await update.effective_message.reply_text(f"No matches for “{query}”.")
        return
    lines = [f"🔎 Results for {query}\n"]
    usdots = []
    for lead in hits:
        usdots.append(lead.usdot)
        lines.append(
            f"• {lead.company} · {lead.city}, {lead.state} · "
            f"{lead.power_units} trucks\n"
            f"  DOT {lead.usdot} · {lead.officer or '—'}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=search_keyboard(usdots)
    )


@allowed_only
async def followups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = store(context).followups_due(15)
    if not rows:
        await update.effective_message.reply_text("No follow-ups queued. Mark leads with 📅 Follow Up.")
        return
    lines = ["📅 Follow-ups\n"]
    usdots = []
    for lead, state in rows:
        usdots.append(lead.usdot)
        when = state["follow_up_at"] or state["updated_at"] or "—"
        lines.append(
            f"• {lead.company} · {lead.phone or 'no phone'}\n"
            f"  DOT {lead.usdot} · due {when}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=search_keyboard(usdots)
    )


@allowed_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = store(context).stats()
    text = (
        "📊 Progress\n\n"
        f"Total leads: {s['total_leads']:,}\n"
        f"Still new / available: {s['new_remaining']:,}\n"
        f"Viewed: {s['viewed']}\n"
        f"Contacted: {s['contacted']}\n"
        f"Interested: {s['interested']}\n"
        f"Follow-up: {s['follow_up']} (due now: {s['follow_up_due']})\n"
        f"Skipped: {s['skipped']}\n"
        f"Phone→Telegram links: {s.get('telegram_links', 0)}\n"
        f"Touched overall: {s['touched']}"
    )
    await update.effective_message.reply_text(text)


@allowed_only
async def linkphone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Tap the button below to share your phone number.\n"
        "I’ll save phone → your Telegram id (and unlock matching leads if the number is in the CSV).",
        reply_markup=share_contact_keyboard()
    )


@allowed_only
async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.effective_message.contact if update.effective_message else None
    user = update.effective_user
    if not contact or not user:
        return
    # Only accept the user's own contact share
    if contact.user_id and contact.user_id != user.id:
        await update.effective_message.reply_text(
            "Please share your own contact (not someone else’s).",
            reply_markup=remove_keyboard()
        )
        return
    phone = contact.phone_number or ""
    tg_id = contact.user_id or user.id
    username = user.username or ""
    lead_store = store(context)
    try:
        phone_norm = lead_store.set_telegram_for_phone(
            phone,
            telegram_user_id=tg_id,
            telegram_username=username,
            source="contact_share"
        )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc), reply_markup=remove_keyboard())
        return

    matches = lead_store.find_leads_by_phone(phone)
    extra = ""
    if matches:
        names = ", ".join(f"{m.company} (DOT {m.usdot})" for m in matches[:5])
        extra = f"\nMatched lead(s): {names}"
    await update.effective_message.reply_text(
        f"✅ Linked phone {phone_norm} → Telegram id {tg_id}"
        + (f" (@{username})" if username else "")
        + extra,
        reply_markup=remove_keyboard()
    )


def _parse_tg_target(raw: str) -> tuple[int | None, str]:
    value = raw.strip()
    if value.startswith("@"):
        return None, value.lstrip("@")
    if value.isdigit():
        return int(value), ""
    if value.startswith("https://t.me/") or value.startswith("t.me/"):
        handle = value.split("/")[-1].split("?")[0].lstrip("@")
        if handle.isdigit():
            return int(handle), ""
        return None, handle
    return None, value.lstrip("@")


@allowed_only
async def settg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if len(args) < 2:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/settg <phone|USDOT> <@username|telegram_id>\n\n"
            "Examples:\n"
            "/settg 6023978970 @fleetowner\n"
            "/settg 1301572 123456789\n"
            "/settg +1-602-397-8970 123456789",
            
        )
        return

    key = args[0]
    tg_raw = args[1]
    tg_id, tg_user = _parse_tg_target(tg_raw)
    lead_store = store(context)

    usdot = ""
    phone = key
    lead = lead_store.get_lead(key)
    if lead:
        usdot = lead.usdot
        phone = lead.phone or key
    else:
        # maybe phone matches a lead
        matches = lead_store.find_leads_by_phone(key)
        if matches:
            usdot = matches[0].usdot
            phone = matches[0].phone or key

    if not normalize_phone(phone) and not usdot:
        await update.effective_message.reply_text("Could not resolve phone or USDOT.")
        return
    if not normalize_phone(phone):
        await update.effective_message.reply_text(
            f"Lead DOT {usdot} has no phone on file. Provide a phone: /settg <phone> <@user|id>",
            
        )
        return

    try:
        phone_norm = lead_store.set_telegram_for_phone(
            phone,
            telegram_user_id=tg_id,
            telegram_username=tg_user,
            usdot=usdot,
            source="manual"
        )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    label = f"@{tg_user}" if tg_user else f"id {tg_id}"
    await update.effective_message.reply_text(
        f"✅ Saved Telegram {label} for phone {phone_norm}"
        + (f" · DOT {usdot}" if usdot else ""),
        
    )
    if usdot:
        await send_lead(update, context, usdot)


@allowed_only
async def findtg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /findtg <phone>")
        return
    phone = " ".join(args)
    lead_store = store(context)
    row = lead_store.get_telegram_by_phone(phone)
    matches = lead_store.find_leads_by_phone(phone)
    if not row and not matches:
        await update.effective_message.reply_text(
            f"No Telegram link and no CSV lead for {normalize_phone(phone) or phone}.\n"
            "Add one with /settg <phone> <@user|id>",
            
        )
        return
    lines = [f"🔎 Phone {normalize_phone(phone) or phone}"]
    if row:
        uname = f"@{row['telegram_username']}" if row["telegram_username"] else "—"
        lines.append(
            f"Telegram: {uname} · id {row['telegram_user_id'] or '—'} · "
            f"DOT {row['usdot'] or '—'} · source {row['source']}"
        )
    else:
        lines.append("Telegram: not linked yet")
    for lead in matches[:5]:
        lines.append(f"Lead: {lead.company} · DOT {lead.usdot} · {lead.city}, {lead.state}")
    await update.effective_message.reply_text("\n".join(lines))


@allowed_only
async def tglist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = store(context).list_telegram_links(20)
    if not rows:
        await update.effective_message.reply_text(
            "No phone→Telegram links yet.\nUse /linkphone or /settg <phone> <@user|id>.",
            
        )
        return
    lines = ["💬 Recent Telegram links\n"]
    for row in rows:
        uname = f"@{row['telegram_username']}" if row["telegram_username"] else "—"
        lines.append(
            f"• {row['phone_norm']} → {uname} / id {row['telegram_user_id'] or '—'}"
            + (f" · DOT {row['usdot']}" if row["usdot"] else "")
        )
    await update.effective_message.reply_text("\n".join(lines))


@allowed_only
async def setname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /setname Your Name")
        return
    name = " ".join(args).strip()
    user = update.effective_user
    try:
        store(context).set_sender_name(user.id, name)
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    await update.effective_message.reply_text(
        f"Saved. Copy-text pitches will use: {name}"
    )


@allowed_only
async def setmyphone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /setmyphone 5551234567")
        return
    phone = " ".join(args).strip()
    user = update.effective_user
    store(context).set_sender_phone(user.id, phone)
    await update.effective_message.reply_text(
        f"Saved. Voicemail/email scripts will use: {phone}"
    )


@allowed_only
async def myname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sender_name, sender_phone = _sender_bits(update, context)
    await update.effective_message.reply_text(
        f"Name: {sender_name}\nPhone: {sender_phone}\n\n"
        f"Change with /setname and /setmyphone"
    )


@allowed_only
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except TelegramError as exc:
        # Stale button presses should not freeze the bot
        if not _is_benign_telegram_error(exc):
            log.warning("callback answer failed: %s", exc)

    data = query.data or ""
    lead_store = store(context)

    if data == "cmd:next":
        leads = lead_store.next_best(1, **_truck_kwargs())
        if not leads:
            await query.message.reply_text("No new leads left. Try /followups or /stats.")
            return
        await send_lead(update, context, leads[0].usdot)
        return

    if data.startswith("open:"):
        await send_lead(update, context, data.split(":", 1)[1])
        return

    if data.startswith("contact:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        phone = to_e164(lead.phone) or lead.phone or "no phone"
        await query.message.reply_text(
            f"Contact for {lead.company}\n"
            f"Tap the card to Call, Message, or Save.\n"
            f"{phone}"
        )
        await send_lead_contact(query.message, lead)
        return

    if data.startswith("pitch:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        sn, sp = _sender_bits(update, context)
        await query.message.reply_text(
            personalized_pitch(lead, sender_name=sn, sender_phone=sp),
            disable_web_page_preview=True,
        )
        return

    if data.startswith("copy:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        sender_name, sender_phone = _sender_bits(update, context)
        text_block = copy_text_version(
            lead, sender_name=sender_name, sender_phone=sender_phone
        )
        phone = to_e164(lead.phone) or lead.phone or "no phone"
        await query.message.reply_text(
            f"SMS ready (name: {sender_name}).\n"
            f"1) Tap Save / Message (or the contact card) to open/message {phone}\n"
            f"2) Long-press next message -> Copy -> paste into SMS\n"
            f"Change name: /setname Your Name"
        )
        await query.message.reply_text(text_block, disable_web_page_preview=True)
        return

    if data.startswith("call:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        phone = to_e164(lead.phone) or lead.phone or "No phone on file"
        await query.message.reply_text(
            f"Call {lead.company}\n"
            f"Ask for: {lead.officer or 'owner / safety / compliance'}\n"
            f"Number:\n{phone}\n\n"
            f"Tap the contact card to Call or Message."
        )
        await send_lead_contact(query.message, lead)
        return

    if data.startswith("email:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        email = lead.email or "No email on file"
        await query.message.reply_text(
            f"✉️ Email {lead.company}\nTo: {email}",
            
        )
        sn, sp = _sender_bits(update, context)
        await query.message.reply_text(
            personalized_pitch(lead, sender_name=sn, sender_phone=sp),
            disable_web_page_preview=True,
        )
        return

    if data.startswith("addtg:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        phone = lead.phone or "unknown"
        await query.message.reply_text(
            f"💬 Link Telegram for {lead.company}\n"
            f"Phone on file: {phone}\n\n"
            f"Send:\n/settg {phone} @username\n"
            f"or\n/settg {usdot} 123456789\n\n"
            "Telegram bots cannot look up random numbers automatically.",
            
        )
        return

    if data.startswith("status:"):
        _, status, usdot = data.split(":", 2)
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        if status == "follow_up":
            lead_store.set_status(usdot, "follow_up", follow_up_days=config.FOLLOWUP_DAYS)
            msg = f"📅 Follow-up set for {lead.company} in {config.FOLLOWUP_DAYS} days."
        elif status == "skipped":
            lead_store.set_status(usdot, "skipped", clear_follow_up=True)
            msg = f"❌ Skipped {lead.company}."
        elif status == "contacted":
            lead_store.set_status(usdot, "contacted", clear_follow_up=True)
            msg = f"✅ Marked contacted: {lead.company}."
        elif status == "interested":
            lead_store.set_status(usdot, "interested", clear_follow_up=True)
            msg = f"🔥 Interested: {lead.company}."
        else:
            await query.message.reply_text("Unknown status.")
            return
        await query.message.reply_text(msg)
        # Auto-advance after skip / contacted / follow-up (always new messages, never edit)
        if status in {"skipped", "contacted", "follow_up"}:
            nxt = lead_store.next_best(1, **_truck_kwargs())
            if nxt:
                await query.message.reply_text("Next best ~300-truck lead:")
                await send_lead(update, context, nxt[0].usdot)
        return

    await query.message.reply_text(f"Unhandled action: {data}")
