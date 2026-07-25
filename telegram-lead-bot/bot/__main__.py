from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from . import config
from . import handlers
from .leads import LeadStore

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "bot.log"

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3),
    ],
)
# Avoid logging full bot token in request URLs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("fleetguard-bot")


def build_app() -> Application:
    store = LeadStore(config.LEADS_CSV_PATH, config.LEADS_DB_PATH)
    log.info("Loaded %s leads from %s", f"{len(store.leads):,}", config.LEADS_CSV_PATH)

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(False)  # serialize handlers — prevents duplicate /next races
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .get_updates_read_timeout(40)
        .build()
    )
    app.bot_data["store"] = store

    async def on_error(update: object, context) -> None:
        err = context.error
        log.exception("Unhandled bot error: %s", err)
        from telegram.error import RetryAfter, TimedOut, NetworkError
        from telegram import Update as TgUpdate

        if isinstance(update, TgUpdate) and update.effective_message:
            try:
                if isinstance(err, RetryAfter):
                    wait = int(getattr(err, "retry_after", 30)) + 1
                    await update.effective_message.reply_text(
                        f"Telegram rate limit. Wait about {wait} seconds, then try /next."
                    )
                elif isinstance(err, (TimedOut, NetworkError)):
                    await update.effective_message.reply_text(
                        "Network blip. Send /ping then /next."
                    )
            except Exception:
                pass

    async def heartbeat(context) -> None:
        log.info("heartbeat — bot alive, leads=%s", f"{len(store.leads):,}")

    app.add_error_handler(on_error)
    app.job_queue.run_repeating(heartbeat, interval=60, first=15)

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.start))
    app.add_handler(CommandHandler("ping", handlers.ping))
    app.add_handler(CommandHandler("next", handlers.next_lead))
    app.add_handler(CommandHandler("highscore", handlers.highscore))
    app.add_handler(CommandHandler("search", handlers.search))
    app.add_handler(CommandHandler("followups", handlers.followups))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CommandHandler("linkphone", handlers.linkphone))
    app.add_handler(CommandHandler("settg", handlers.settg))
    app.add_handler(CommandHandler("findtg", handlers.findtg))
    app.add_handler(CommandHandler("tglist", handlers.tglist))
    app.add_handler(CommandHandler("setname", handlers.setname))
    app.add_handler(CommandHandler("setmyphone", handlers.setmyphone))
    app.add_handler(CommandHandler("myname", handlers.myname))
    app.add_handler(MessageHandler(filters.CONTACT, handlers.on_contact))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    return app


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN or "ABC-DEF" in config.TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is missing or still a placeholder. "
            "Set it in Railway → Variables, then Redeploy."
        )
    app = build_app()
    log.info("Starting FleetGuard lead bot (allowed users: %s)", sorted(config.ALLOWED_USER_IDS))
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
        close_loop=False,
    )


if __name__ == "__main__":
    main()
