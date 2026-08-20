"""Telegram-бот для продажи электробайков Sur-Ron в Кыргызстане.

Работает в двух режимах:
  * webhook (production, Render) — если задан WEBHOOK_BASE_URL
  * long polling (локальная разработка) — если WEBHOOK_BASE_URL не задан
"""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiohttp import web

from catalog import (
    CONTACT_URL,
    CONTACT_USERNAME,
    MODEL_ORDER,
    MODELS,
    format_model_card,
    format_models_list,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("surron-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "surron-webhook-secret").strip()
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    logger.error("Переменная окружения BOT_TOKEN не задана")
    sys.exit(1)

router = Router()


# ---------------------------------------------------------------- клавиатуры

def models_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура со списком всех моделей."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{MODELS[key]['emoji']} {MODELS[key]['name']} — {MODELS[key]['price']}",
                callback_data=f"model:{key}",
            )
        ]
        for key in MODEL_ORDER
    ]
    rows.append(
        [InlineKeyboardButton(text="💬 Связаться с менеджером", url=CONTACT_URL)]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def model_detail_keyboard(key: str) -> InlineKeyboardMarkup:
    """Клавиатура карточки модели: заказ, соседние модели, возврат в каталог."""
    others = [k for k in MODEL_ORDER if k != key]
    rows = [
        [
            InlineKeyboardButton(
                text=f"🛒 Заказать {MODELS[key]['name']}", url=CONTACT_URL
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{MODELS[k]['emoji']} {MODELS[k]['name']}",
                callback_data=f"model:{k}",
            )
            for k in others
        ],
        [InlineKeyboardButton(text="⬅️ Назад в каталог", callback_data="catalog")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ------------------------------------------------------------------ хендлеры

WELCOME_TEXT = (
    "👋 <b>Добро пожаловать в Sur-Ron Кыргызстан!</b>\n\n"
    "Мы продаём оригинальные электробайки <b>Sur-Ron</b> — тихие, мощные и "
    "не требующие бензина. Идеальны для гор, бездорожья и города.\n\n"
    "🏍 <b>Наши модели:</b>\n"
    "⚡ Light Bee X — <b>150 000 сом</b>\n"
    "🔥 Ultra Bee — <b>300 000 сом</b>\n"
    "🌪 Storm Bee — <b>600 000 сом</b>\n\n"
    "Выберите модель ниже, чтобы узнать характеристики и оформить заказ 👇\n\n"
    "Команды: /models — каталог, /help — помощь"
)

HELP_TEXT = (
    "ℹ️ <b>Помощь по боту Sur-Ron Кыргызстан</b>\n\n"
    "<b>Доступные команды:</b>\n"
    "/start — приветствие и каталог моделей\n"
    "/models — показать все модели с ценами\n"
    "/help — это сообщение\n\n"
    "<b>Как оформить заказ:</b>\n"
    "1. Нажмите /models или кнопку с моделью\n"
    "2. Изучите характеристики и цену\n"
    "3. Нажмите кнопку «🛒 Заказать»\n"
    f"4. Напишите менеджеру @{CONTACT_USERNAME} — он ответит на вопросы, "
    "расскажет про наличие, доставку по Кыргызстану и условия оплаты\n\n"
    "<b>Часто спрашивают:</b>\n"
    "• <b>Есть ли гарантия?</b> Да, гарантия и сервисная поддержка — уточните у менеджера.\n"
    "• <b>Нужны ли права?</b> Light Bee относится к электровелосипедам-эндуро и "
    "используется преимущественно вне дорог общего пользования.\n"
    "• <b>Есть ли доставка в регионы?</b> Да, доставка по всему Кыргызстану.\n"
    "• <b>Можно ли в рассрочку?</b> Условия обсуждаются индивидуально с менеджером.\n\n"
    f"💬 Связаться напрямую: @{CONTACT_USERNAME}"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    logger.info("Пользователь %s запустил бота", message.from_user.id)
    await message.answer(WELCOME_TEXT, reply_markup=models_keyboard())


@router.message(Command("models"))
async def cmd_models(message: Message) -> None:
    await message.answer(format_models_list(), reply_markup=models_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        HELP_TEXT,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏍 Каталог моделей", callback_data="catalog")],
                [InlineKeyboardButton(text="💬 Написать менеджеру", url=CONTACT_URL)],
            ]
        ),
    )


@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        format_models_list(), reply_markup=models_keyboard()
    )


@router.callback_query(F.data.startswith("model:"))
async def cb_model(callback: CallbackQuery) -> None:
    key = callback.data.split(":", 1)[1]
    if key not in MODELS:
        await callback.answer("Модель не найдена", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        format_model_card(key), reply_markup=model_detail_keyboard(key)
    )


@router.message()
async def fallback(message: Message) -> None:
    """Любое другое сообщение — показываем каталог."""
    await message.answer(
        "Я бот-консультант Sur-Ron Кыргызстан 🏍\n\n"
        "Выберите модель из каталога ниже или напишите менеджеру "
        f"@{CONTACT_USERNAME} напрямую.\n\n"
        "Команды: /start, /models, /help",
        reply_markup=models_keyboard(),
    )


# --------------------------------------------------------------------- запуск

async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать / каталог"),
            BotCommand(command="models", description="Все модели и цены"),
            BotCommand(command="help", description="Помощь и контакты"),
        ]
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def run_polling() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    logger.info("Запуск в режиме long polling")
    await dp.start_polling(bot)


async def run_webhook() -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot": "surron-sales-bot"})

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    async def on_startup(_app: web.Application) -> None:
        url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(
            url=url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        await set_commands(bot)
        logger.info("Webhook установлен: %s", url)

    app.on_startup.append(on_startup)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logger.info("HTTP-сервер запущен на порту %s", PORT)
    await asyncio.Event().wait()


def main() -> None:
    if WEBHOOK_BASE_URL:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
