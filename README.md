# 🚛 ProxyBot — Live US Load Search Bot

Telegram bot [@Proxy007Bot](https://t.me/Proxy007Bot) that searches **real American freight loads**.

## Data source

By default the bot queries the **public Trulos load board APIs** (live):

- geo lookup for cities
- radius load search around origin/destination
- broker company + phone when available

If the live API is down, it falls back to local `data/loads.json`.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put BOT_TOKEN from @BotFather into .env
python -m bot.main
```

Examples in Telegram:

```text
Chicago
LA to Phoenix
Atlanta - Miami
/loads
```

## Env

| Variable | Meaning |
|---------|---------|
| `BOT_TOKEN` | Telegram bot token |
| `LIVE_LOADS` | `true` = live Trulos (default) |
| `SEARCH_RADIUS_MI` | search radius in miles (default 200) |
| `LOADS_PATH` | local fallback JSON |

## Notes

DAT / Truckstop / CHR Carrier APIs need paid accounts + keys. This bot uses Trulos’ public no-login board endpoints for live results without credentials.
