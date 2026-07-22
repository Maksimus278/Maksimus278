from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def lead_keyboard(
    usdot: str,
    phone: str = "",
    email: str = "",
    telegram_username: str = "",
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Copy SMS", callback_data=f"copy:{usdot}"),
            InlineKeyboardButton("Call", callback_data=f"call:{usdot}"),
        ],
        [
            InlineKeyboardButton("Email", callback_data=f"email:{usdot}"),
            InlineKeyboardButton("Add Telegram", callback_data=f"addtg:{usdot}")
            if not telegram_username
            else InlineKeyboardButton("Telegram", url=f"https://t.me/{telegram_username.lstrip('@')}"),
        ],
        [
            InlineKeyboardButton("Contacted", callback_data=f"status:contacted:{usdot}"),
            InlineKeyboardButton("Interested", callback_data=f"status:interested:{usdot}"),
        ],
        [
            InlineKeyboardButton("Follow Up", callback_data=f"status:follow_up:{usdot}"),
            InlineKeyboardButton("Skip", callback_data=f"status:skipped:{usdot}"),
        ],
        [
            InlineKeyboardButton("Next lead", callback_data="cmd:next"),
            InlineKeyboardButton("Pitch again", callback_data=f"pitch:{usdot}"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def search_keyboard(usdots: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f"Open #{usdot}", callback_data=f"open:{usdot}")]
        for usdot in usdots[:8]
    ]
    return InlineKeyboardMarkup(buttons)


def share_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share my phone (link Telegram id)", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
