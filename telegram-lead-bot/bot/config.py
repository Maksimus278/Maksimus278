from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}. Copy .env.example to .env and fill it in.")
    return value


TELEGRAM_BOT_TOKEN = _required("TELEGRAM_BOT_TOKEN")

_allowed = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS = {int(x.strip()) for x in _allowed.split(",") if x.strip()}
if not ALLOWED_USER_IDS:
    raise SystemExit("Set TELEGRAM_ALLOWED_USER_IDS to your Telegram user id (from @userinfobot).")

LEADS_CSV_PATH = Path(os.getenv("LEADS_CSV_PATH", str(ROOT / "data" / "fleetguard-leads.csv")))
if not LEADS_CSV_PATH.is_absolute():
    LEADS_CSV_PATH = ROOT / LEADS_CSV_PATH

LEADS_DB_PATH = Path(os.getenv("LEADS_DB_PATH", str(ROOT / "data" / "leads_state.db")))
if not LEADS_DB_PATH.is_absolute():
    LEADS_DB_PATH = ROOT / LEADS_DB_PATH

FOLLOWUP_DAYS = int(os.getenv("FOLLOWUP_DAYS", "3"))
HIGH_SCORE_LIMIT = int(os.getenv("HIGH_SCORE_LIMIT", "10"))
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "8"))