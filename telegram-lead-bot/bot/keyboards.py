from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def lead_keyboard(usdot: str, phone: str = "", email: str = "") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📞 Call", callback_data=f"call:{usdot}"),
            InlineKeyboardButton("✉️ Email", callback_data=f"email:{usdot}"),
        ],
        [
            InlineKeyboardButton("✅ Contacted", callback_data=f"status:contacted:{usdot}"),
            InlineKeyboardButton("🔥 Interested", callback_data=f"status:interested:{usdot}"),
        ],
        [
            InlineKeyboardButton("📅 Follow Up", callback_data=f"status:follow_up:{usdot}"),
            InlineKeyboardButton("❌ Skip", callback_data=f"status:skipped:{usdot}"),
        ],
        [
            InlineKeyboardButton("⏭ Next lead", callback_data="cmd:next"),
            InlineKeyboardButton("📋 Pitch again", callback_data=f"pitch:{usdot}"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def search_keyboard(usdots: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f"Open #{usdot}", callback_data=f"open:{usdot}")]
        for usdot in usdots[:8]
    ]
    return InlineKeyboardMarkup(buttons)
