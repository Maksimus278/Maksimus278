from __future__ import annotations

import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from . import config
from .keyboards import lead_keyboard, remove_keyboard, search_keyboard, share_contact_keyboard
from .leads import LeadStore
from .phones import normalize_phone
from .pitches import format_lead_card, personalized_pitch

log = logging.getLogger(__name__)


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
                await update.callback_query.answer("Unauthorized", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def store(context: ContextTypes.DEFAULT_TYPE) -> LeadStore:
    return context.application.bot_data["store"]


def _tg_bits(lead_store: LeadStore, usdot: str) -> tuple[str, int | None]:
    row = lead_store.get_telegram_for_lead(usdot)
    if not row:
        return "", None
    return (row["telegram_username"] or ""), row["telegram_user_id"]


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

    card = format_lead_card(
        lead,
        status=status,
        follow_up_at=follow_up_at,
        telegram_username=tg_user,
        telegram_user_id=tg_id,
    )
    pitch = personalized_pitch(lead)
    keyboard = lead_keyboard(lead.usdot, lead.phone, lead.email, telegram_username=tg_user)

    # Card uses HTML; pitch is plain text (avoids Telegram HTML parse failures on & / quotes)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            card, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
        )
        await update.callback_query.message.reply_text(pitch, disable_web_page_preview=True)
    elif update.effective_message:
        await update.effective_message.reply_text(
            card, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
        )
        await update.effective_message.reply_text(pitch, disable_web_page_preview=True)


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
        f"Loaded <b>{stats['total_leads']:,}</b> leads from CSV.\n"
        f"Priority target: fleets with <b>~{config.TARGET_TRUCKS} trucks</b> "
        f"({config.TARGET_TRUCK_MIN}–{config.TARGET_TRUCK_MAX}).\n\n"
        "Commands:\n"
        "/next — next best ~300-truck lead + pitch\n"
        "/highscore — fleets closest to ~300 trucks\n"
        "/search &lt;query&gt; — find a company / DOT / city\n"
        "/followups — who needs follow-up\n"
        "/stats — your progress\n"
        "/linkphone — share contact to save your phone → Telegram id\n"
        "/settg &lt;phone|DOT&gt; &lt;@user|id&gt; — link Telegram to a lead phone\n"
        "/findtg &lt;phone&gt; — look up a saved Telegram id by phone\n"
        "/tglist — recent phone → Telegram links\n\n"
        "Use the buttons under each lead to call, email, and track status.\n"
        "<i>Note: Telegram cannot auto-discover strangers’ ids from CSV phones. "
        "Share a contact or set them with /settg.</i>",
        parse_mode="HTML",
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
        f"🚛 <b>Fleets closest to ~{target} trucks</b>\n"
        f"<i>Band {config.TARGET_TRUCK_MIN}–{config.TARGET_TRUCK_MAX} · nearest to {target} first</i>\n",
    ]
    usdots = []
    for i, (lead, status) in enumerate(rows, 1):
        usdots.append(lead.usdot)
        dist = lead.truck_distance(target)
        lines.append(
            f"{i}. <b>{lead.company}</b> · <b>{lead.power_units} trucks</b> "
            f"(Δ{dist} from {target})\n"
            f"   {lead.city}, {lead.state} · {status} · DOT <code>{lead.usdot}</code>\n"
            f"   {lead.suggested_plan} · {lead.phone or 'no phone'}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=search_keyboard(usdots),
        disable_web_page_preview=True,
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
    lines = [f"🔎 Results for <b>{query}</b>\n"]
    usdots = []
    for lead in hits:
        usdots.append(lead.usdot)
        lines.append(
            f"• <b>{lead.company}</b> · {lead.city}, {lead.state} · "
            f"<b>{lead.power_units} trucks</b>\n"
            f"  DOT <code>{lead.usdot}</code> · {lead.officer or '—'}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=search_keyboard(usdots),
    )


@allowed_only
async def followups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = store(context).followups_due(15)
    if not rows:
        await update.effective_message.reply_text("No follow-ups queued. Mark leads with 📅 Follow Up.")
        return
    lines = ["📅 <b>Follow-ups</b>\n"]
    usdots = []
    for lead, state in rows:
        usdots.append(lead.usdot)
        when = state["follow_up_at"] or state["updated_at"] or "—"
        lines.append(
            f"• <b>{lead.company}</b> · {lead.phone or 'no phone'}\n"
            f"  DOT <code>{lead.usdot}</code> · due {when}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=search_keyboard(usdots),
    )


@allowed_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = store(context).stats()
    text = (
        "📊 <b>Progress</b>\n\n"
        f"Total leads: <b>{s['total_leads']:,}</b>\n"
        f"Still new / available: <b>{s['new_remaining']:,}</b>\n"
        f"Viewed: {s['viewed']}\n"
        f"Contacted: {s['contacted']}\n"
        f"Interested: {s['interested']}\n"
        f"Follow-up: {s['follow_up']} (due now: {s['follow_up_due']})\n"
        f"Skipped: {s['skipped']}\n"
        f"Phone→Telegram links: {s.get('telegram_links', 0)}\n"
        f"Touched overall: {s['touched']}"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")


@allowed_only
async def linkphone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Tap the button below to share your phone number.\n"
        "I’ll save <b>phone → your Telegram id</b> (and unlock matching leads if the number is in the CSV).",
        parse_mode="HTML",
        reply_markup=share_contact_keyboard(),
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
            reply_markup=remove_keyboard(),
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
            source="contact_share",
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
        f"✅ Linked phone <code>{phone_norm}</code> → Telegram id <code>{tg_id}</code>"
        + (f" (@{username})" if username else "")
        + extra,
        parse_mode="HTML",
        reply_markup=remove_keyboard(),
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
            "/settg &lt;phone|USDOT&gt; &lt;@username|telegram_id&gt;\n\n"
            "Examples:\n"
            "/settg 6023978970 @fleetowner\n"
            "/settg 1301572 123456789\n"
            "/settg +1-602-397-8970 123456789",
            parse_mode="HTML",
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
            f"Lead DOT {usdot} has no phone on file. Provide a phone: /settg &lt;phone&gt; &lt;@user|id&gt;",
            parse_mode="HTML",
        )
        return

    try:
        phone_norm = lead_store.set_telegram_for_phone(
            phone,
            telegram_user_id=tg_id,
            telegram_username=tg_user,
            usdot=usdot,
            source="manual",
        )
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    label = f"@{tg_user}" if tg_user else f"id {tg_id}"
    await update.effective_message.reply_text(
        f"✅ Saved Telegram {label} for phone <code>{phone_norm}</code>"
        + (f" · DOT <code>{usdot}</code>" if usdot else ""),
        parse_mode="HTML",
    )
    if usdot:
        await send_lead(update, context, usdot)


@allowed_only
async def findtg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /findtg &lt;phone&gt;", parse_mode="HTML")
        return
    phone = " ".join(args)
    lead_store = store(context)
    row = lead_store.get_telegram_by_phone(phone)
    matches = lead_store.find_leads_by_phone(phone)
    if not row and not matches:
        await update.effective_message.reply_text(
            f"No Telegram link and no CSV lead for <code>{normalize_phone(phone) or phone}</code>.\n"
            "Add one with /settg &lt;phone&gt; &lt;@user|id&gt;",
            parse_mode="HTML",
        )
        return
    lines = [f"🔎 Phone <code>{normalize_phone(phone) or phone}</code>"]
    if row:
        uname = f"@{row['telegram_username']}" if row["telegram_username"] else "—"
        lines.append(
            f"Telegram: {uname} · id <code>{row['telegram_user_id'] or '—'}</code> · "
            f"DOT {row['usdot'] or '—'} · source {row['source']}"
        )
    else:
        lines.append("Telegram: not linked yet")
    for lead in matches[:5]:
        lines.append(f"Lead: <b>{lead.company}</b> · DOT <code>{lead.usdot}</code> · {lead.city}, {lead.state}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


@allowed_only
async def tglist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = store(context).list_telegram_links(20)
    if not rows:
        await update.effective_message.reply_text(
            "No phone→Telegram links yet.\nUse /linkphone or /settg &lt;phone&gt; &lt;@user|id&gt;.",
            parse_mode="HTML",
        )
        return
    lines = ["💬 <b>Recent Telegram links</b>\n"]
    for row in rows:
        uname = f"@{row['telegram_username']}" if row["telegram_username"] else "—"
        lines.append(
            f"• <code>{row['phone_norm']}</code> → {uname} / id <code>{row['telegram_user_id'] or '—'}</code>"
            + (f" · DOT {row['usdot']}" if row["usdot"] else "")
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


@allowed_only
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    lead_store = store(context)

    if data == "cmd:next":
        leads = lead_store.next_best(1, **_truck_kwargs())
        if not leads:
            await query.edit_message_text("No new leads left. Try /followups or /stats.")
            return
        await send_lead(update, context, leads[0].usdot)
        return

    if data.startswith("open:"):
        await send_lead(update, context, data.split(":", 1)[1])
        return

    if data.startswith("pitch:"):
        await send_lead(update, context, data.split(":", 1)[1])
        return

    if data.startswith("call:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        phone = lead.phone or "No phone on file"
        await query.message.reply_text(
            f"📞 Call <b>{_html(lead.company)}</b>\n"
            f"Ask for: <b>{_html(lead.officer or 'owner / safety / compliance')}</b>\n"
            f"Number: <code>{_html(phone)}</code>",
            parse_mode="HTML",
        )
        # Plain text pitch (no HTML) so & / quotes never break Telegram parsing
        call_pitch = personalized_pitch(lead).split("✉️")[0].strip()
        await query.message.reply_text(call_pitch, disable_web_page_preview=True)
        return

    if data.startswith("email:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        email = lead.email or "No email on file"
        await query.message.reply_text(
            f"✉️ Email <b>{_html(lead.company)}</b>\nTo: <code>{_html(email)}</code>",
            parse_mode="HTML",
        )
        await query.message.reply_text(personalized_pitch(lead), disable_web_page_preview=True)
        return

    if data.startswith("addtg:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        phone = lead.phone or "unknown"
        await query.message.reply_text(
            f"💬 Link Telegram for <b>{_html(lead.company)}</b>\n"
            f"Phone on file: <code>{_html(phone)}</code>\n\n"
            f"Send:\n<code>/settg {_html(phone)} @username</code>\n"
            f"or\n<code>/settg {_html(usdot)} 123456789</code>\n\n"
            "Telegram bots cannot look up random numbers automatically.",
            parse_mode="HTML",
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
        # Auto-advance after skip / contacted / follow-up
        if status in {"skipped", "contacted", "follow_up"}:
            nxt = lead_store.next_best(1, **_truck_kwargs())
            if nxt:
                await query.message.reply_text("Next best ~300-truck lead:")
                # Reuse the safe two-message sender via a synthetic path
                lead = nxt[0]
                lead_store.mark_viewed(lead.usdot)
                state = lead_store.get_status(lead.usdot)
                tg_user, tg_id = _tg_bits(lead_store, lead.usdot)
                card = format_lead_card(
                    lead,
                    status=state["status"] if state else "new",
                    follow_up_at=state["follow_up_at"] if state else None,
                    telegram_username=tg_user,
                    telegram_user_id=tg_id,
                )
                pitch = personalized_pitch(lead)
                await query.message.reply_text(
                    card,
                    reply_markup=lead_keyboard(
                        lead.usdot, lead.phone, lead.email, telegram_username=tg_user
                    ),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                await query.message.reply_text(pitch, disable_web_page_preview=True)
        return

    await query.message.reply_text(f"Unhandled action: {data}")


def _html(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
