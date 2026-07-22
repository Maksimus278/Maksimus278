from __future__ import annotations

import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from . import config
from . import handlers
from .leads import LeadStore

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
# Avoid logging full bot token in request URLs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("fleetguard-bot")


def build_app() -> Application:
    store = LeadStore(config.LEADS_CSV_PATH, config.LEADS_DB_PATH)
    log.info("Loaded %s leads from %s", f"{len(store.leads):,}", config.LEADS_CSV_PATH)

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.bot_data["store"] = store

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.start))
    app.add_handler(CommandHandler("next", handlers.next_lead))
    app.add_handler(CommandHandler("highscore", handlers.highscore))
    app.add_handler(CommandHandler("search", handlers.search))
    app.add_handler(CommandHandler("followups", handlers.followups))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    return app


def main() -> None:
    app = build_app()
    log.info("Starting FleetGuard lead bot (allowed users: %s)", sorted(config.ALLOWED_USER_IDS))
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
