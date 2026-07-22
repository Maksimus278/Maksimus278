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
ALLOWED_USER_IDS: set[int] = set()
AUTO_CLAIM_OWNER = False
if _allowed == "*":
    AUTO_CLAIM_OWNER = True
elif _allowed:
    ALLOWED_USER_IDS = {int(x.strip()) for x in _allowed.split(",") if x.strip()}
else:
    # Default: claim the first Telegram user who messages the bot
    AUTO_CLAIM_OWNER = True

OWNER_FILE = Path(os.getenv("OWNER_FILE", str(ROOT / "data" / "allowed_owner.txt")))
if not OWNER_FILE.is_absolute():
    OWNER_FILE = ROOT / OWNER_FILE

# Persist claimed owner across restarts
if OWNER_FILE.exists():
    for line in OWNER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.isdigit():
            ALLOWED_USER_IDS.add(int(line))

LEADS_CSV_PATH = Path(os.getenv("LEADS_CSV_PATH", str(ROOT / "data" / "fleetguard-leads.csv")))
if not LEADS_CSV_PATH.is_absolute():
    LEADS_CSV_PATH = ROOT / LEADS_CSV_PATH

LEADS_DB_PATH = Path(os.getenv("LEADS_DB_PATH", str(ROOT / "data" / "leads_state.db")))
if not LEADS_DB_PATH.is_absolute():
    LEADS_DB_PATH = ROOT / LEADS_DB_PATH

FOLLOWUP_DAYS = int(os.getenv("FOLLOWUP_DAYS", "3"))
HIGH_SCORE_LIMIT = int(os.getenv("HIGH_SCORE_LIMIT", "10"))
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "8"))


def claim_owner(user_id: int) -> bool:
    """Claim bot ownership for the first user when auto-claim is enabled."""
    if user_id in ALLOWED_USER_IDS:
        return True
    if not AUTO_CLAIM_OWNER:
        return False
    if ALLOWED_USER_IDS:
        # Already claimed by someone else
        return False
    ALLOWED_USER_IDS.add(user_id)
    OWNER_FILE.parent.mkdir(parents=True, exist_ok=True)
    OWNER_FILE.write_text(f"{user_id}\n", encoding="utf-8")
    return True


def is_allowed(user_id: int) -> bool:
    if user_id in ALLOWED_USER_IDS:
        return True
    return claim_owner(user_id)
