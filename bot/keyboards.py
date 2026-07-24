from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔥 Get leads"), KeyboardButton(text="🔍 Find load")],
            [KeyboardButton(text="📋 All loads"), KeyboardButton(text="👀 My watches")],
            [KeyboardButton(text="ℹ️ Help")],
        ],
        resize_keyboard=True,
    )


def truck_type_keyboard() -> InlineKeyboardMarkup:
    types = [
        ("Dry Van", "dry van"),
        ("Reefer", "reefer"),
        ("Flatbed", "flatbed"),
        ("Box Truck", "box truck"),
        ("Hotshot", "hotshot"),
        ("Power Only", "power only"),
        ("Any", "any"),
    ]
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"truck:{value}")]
        for label, value in types
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_search_keyboard(origin: str | None, destination: str | None) -> InlineKeyboardMarkup:
    o = origin or "*"
    d = destination or "*"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔥 Leads for this lane",
                    callback_data=f"leads:{o}|{d}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👀 Watch this lane",
                    callback_data=f"watch:{o}|{d}",
                )
            ],
            [InlineKeyboardButton(text="🔁 New search", callback_data="search:new")],
        ]
    )
