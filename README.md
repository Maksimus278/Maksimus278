# 🚛 ProxyBot — US Load Search Bot

Telegram bot [@Proxy007Bot](https://t.me/Proxy007Bot) for finding **American freight loads**.

## Features

- Large US board (`data/loads.json`, 600+ demo loads)
- Search by lane (`Chicago - Dallas`, `LA to Phoenix`) or city (`Atlanta`)
- Equipment filter (dry van, reefer, flatbed, box truck, hotshot, power only…)
- Lane watches (`/watch`)

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

Regenerate a bigger demo board:

```bash
python scripts/generate_us_loads.py
```

## Commands

| Command | Description |
|--------|-------------|
| `/start` | Menu + board size |
| `/search` | Guided search |
| `/loads` | Latest US loads |
| `/watch Chicago - Dallas` | Watch a lane |
| `/reload` | Reload `data/loads.json` |
| `/help` | Help |

## Notes

Current board is a **generated US demo dataset** (USD / miles / lbs). Replace with DAT / Truckstop / broker API via the same `LoadRepository` when ready.
