from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти груз"), KeyboardButton(text="👀 Мои подписки")],
            [KeyboardButton(text="📋 Все грузы"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def truck_type_keyboard() -> InlineKeyboardMarkup:
    types = ["тент", "рефрижератор", "открытая", "газель", "самосвал", "любой"]
    rows = [
        [InlineKeyboardButton(text=label.capitalize(), callback_data=f"truck:{label}")]
        for label in types
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def watch_confirm_keyboard(origin: str, destination: str) -> InlineKeyboardMarkup:
    o = origin or "*"
    d = destination or "*"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👀 Следить за направлением",
                    callback_data=f"watch:{o}|{d}",
                )
            ]
        ]
    )


def after_search_keyboard(origin: str | None, destination: str | None) -> InlineKeyboardMarkup:
    o = origin or "*"
    d = destination or "*"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👀 Подписаться на направление",
                    callback_data=f"watch:{o}|{d}",
                )
            ],
            [InlineKeyboardButton(text="🔁 Новый поиск", callback_data="search:new")],
        ]
    )
