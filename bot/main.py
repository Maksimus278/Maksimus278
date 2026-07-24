import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.handlers import router
from bot.middlewares import AccessMiddleware
from bot.providers.trulos import TrulosClient
from bot.search import LoadRepository
from bot.service import LoadService

logger = logging.getLogger(__name__)


def build_dispatcher(settings, repo: LoadRepository, service: LoadService) -> Dispatcher:
    router._parent_router = None  # noqa: SLF001

    dp = Dispatcher(storage=MemoryStorage())
    dp["repo"] = repo
    dp["service"] = service
    dp.message.middleware(AccessMiddleware(settings))
    dp.callback_query.middleware(AccessMiddleware(settings))
    dp.include_router(router)
    return dp


async def run_bot() -> None:
    settings = get_settings()
    repo = LoadRepository(settings.loads_path)
    service = LoadService(
        repo,
        live=TrulosClient(),
        use_live=settings.live_loads,
        radius_mi=settings.search_radius_mi,
    )

    session = AiohttpSession(timeout=60)
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(settings, repo, service)

    logger.info(
        "Bot ready · live=%s · local_fallback=%s · radius=%smi",
        settings.live_loads,
        len(repo.all()),
        settings.search_radius_mi,
    )
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(
            bot,
            repo=repo,
            service=service,
            allowed_updates=["message", "callback_query"],
            polling_timeout=25,
        )
    finally:
        await bot.session.close()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    backoff = 3
    while True:
        try:
            await run_bot()
            break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Bot polling crashed; restarting in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    asyncio.run(main())
