from __future__ import annotations

import logging
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from . import config
from .keyboards import lead_keyboard, search_keyboard
from .leads import LeadStore
from .pitches import format_lead_card, personalized_pitch

log = logging.getLogger(__name__)


def allowed_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not config.is_allowed(user.id):
            if update.message:
                await update.message.reply_text(
                    "Unauthorized. This bot is locked to its owner. "
                    "Ask the owner to add your Telegram id to TELEGRAM_ALLOWED_USER_IDS."
                )
            elif update.callback_query:
                await update.callback_query.answer("Unauthorized", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def store(context: ContextTypes.DEFAULT_TYPE) -> LeadStore:
    return context.application.bot_data["store"]


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

    card = format_lead_card(lead, status=status, follow_up_at=follow_up_at)
    pitch = personalized_pitch(lead)
    text = f"{card}\n\n{pitch}"
    # Telegram message limit ~4096
    if len(text) > 4000:
        text = text[:3990] + "…"

    keyboard = lead_keyboard(lead.usdot, lead.phone, lead.email)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True
        )


@allowed_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lead_store = store(context)
    stats = lead_store.stats()
    await update.effective_message.reply_text(
        "FleetGuard lead bot ready.\n\n"
        f"Loaded <b>{stats['total_leads']:,}</b> leads from CSV.\n\n"
        "Commands:\n"
        "/next — next best lead + pitch\n"
        "/highscore — top potential leads\n"
        "/search &lt;query&gt; — find a company / DOT / city\n"
        "/followups — who needs follow-up\n"
        "/stats — your progress\n\n"
        "Use the buttons under each lead to call, email, and track status.",
        parse_mode="HTML",
    )


@allowed_only
async def next_lead(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    leads = store(context).next_best(1)
    if not leads:
        await update.effective_message.reply_text("No new leads left. Check /followups or /stats.")
        return
    await send_lead(update, context, leads[0].usdot)


@allowed_only
async def highscore(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = store(context).high_score(config.HIGH_SCORE_LIMIT)
    if not rows:
        await update.effective_message.reply_text("No leads loaded.")
        return
    lines = ["🔥 <b>Highest-potential leads</b>\n"]
    usdots = []
    for i, (lead, status) in enumerate(rows, 1):
        usdots.append(lead.usdot)
        lines.append(
            f"{i}. <b>{lead.company}</b> · score {lead.effective_score} · "
            f"{lead.power_units} trucks · {lead.city}, {lead.state} · {status}\n"
            f"   DOT <code>{lead.usdot}</code> · {lead.suggested_plan}"
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
            f"{lead.power_units} trucks · score {lead.effective_score}\n"
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
        f"Touched overall: {s['touched']}"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")


@allowed_only
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    lead_store = store(context)

    if data == "cmd:next":
        leads = lead_store.next_best(1)
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
            f"📞 Call <b>{lead.company}</b>\n"
            f"Ask for: <b>{lead.officer or 'owner / safety / compliance'}</b>\n"
            f"Number: <code>{phone}</code>\n\n"
            f"{personalized_pitch(lead).split('✉️')[0].strip()}",
            parse_mode="HTML",
        )
        return

    if data.startswith("email:"):
        usdot = data.split(":", 1)[1]
        lead = lead_store.get_lead(usdot)
        if not lead:
            await query.message.reply_text("Lead not found.")
            return
        email = lead.email or "No email on file"
        pitch = personalized_pitch(lead)
        # Extract email parts after the email subject marker
        await query.message.reply_text(
            f"✉️ Email <b>{lead.company}</b>\nTo: <code>{email}</code>\n\n{pitch}",
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
            nxt = lead_store.next_best(1)
            if nxt:
                await query.message.reply_text("Next best lead:")
                lead_store.mark_viewed(nxt[0].usdot)
                state = lead_store.get_status(nxt[0].usdot)
                card = format_lead_card(
                    nxt[0],
                    status=state["status"] if state else "new",
                    follow_up_at=state["follow_up_at"] if state else None,
                )
                text = f"{card}\n\n{personalized_pitch(nxt[0])}"
                if len(text) > 4000:
                    text = text[:3990] + "…"
                await query.message.reply_text(
                    text,
                    reply_markup=lead_keyboard(nxt[0].usdot),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
        return

    await query.message.reply_text(f"Unhandled action: {data}")
