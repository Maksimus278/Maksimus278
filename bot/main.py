import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.handlers import router
from bot.middlewares import AccessMiddleware
from bot.search import LoadRepository


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    settings = get_settings()
    repo = LoadRepository(settings.loads_path)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["repo"] = repo
    dp.message.middleware(AccessMiddleware(settings))
    dp.callback_query.middleware(AccessMiddleware(settings))
    dp.include_router(router)

    logging.info("Loaded %s loads from %s", len(repo.all()), settings.loads_path)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, repo=repo)


if __name__ == "__main__":
    asyncio.run(main())
