#!/usr/bin/env bash
# Keep the bot alive: auto-restart on crash / Telegram disconnect.
set -u
cd "$(dirname "$0")"
mkdir -p logs
export PYTHONUNBUFFERED=1

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv — create it and install requirements first." >&2
  exit 1
fi

while true; do
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) starting FleetGuard bot" | tee -a logs/supervisor.log
  .venv/bin/python -m bot
  code=$?
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) bot exited code=${code}; restarting in 3s" | tee -a logs/supervisor.log
  sleep 3
done
