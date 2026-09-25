#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
if [[ ! -f .env ]]; then
  echo "Copy .env.example to .env and add TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_USER_IDS"
  exit 1
fi
exec .venv/bin/python -m bot
