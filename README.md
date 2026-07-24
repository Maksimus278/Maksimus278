# ProxyBot — Live US Leads & Loads

Telegram bot [@Proxy007Bot](https://t.me/Proxy007Bot) that generates **real broker leads** from live US freight loads (Trulos public board).

## What you get

Each lead includes:
- Broker company
- Contact / dispatch name
- Phone number
- Lane (origin → destination)
- Rate / equipment when available

## Commands

- `/leads` or button **Get leads**
- `/leads Chicago`
- `/leads Dallas - Atlanta`
- `/loads` — raw live loads
- `/search` — guided load search

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

`LIVE_LOADS=true` uses live Trulos APIs. Local JSON is fallback only.
