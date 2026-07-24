# 🚛 ProxyBot — US Load Search Bot

Telegram bot [@Proxy007Bot](https://t.me/Proxy007Bot) for finding **American freight loads**.

## Features

- Search US loads by lane (`Chicago - Dallas`, `LA to Phoenix`)
- Equipment filter (dry van, reefer, flatbed, box truck, hotshot, power only)
- Latest loads feed
- Lane watches (`/watch`)

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put BOT_TOKEN from @BotFather into .env
python -m bot.main
```

Then open the bot and try:

```text
Chicago - Dallas
```

## Commands

| Command | Description |
|--------|-------------|
| `/start` | Menu |
| `/search` | Guided search |
| `/loads` | Latest US loads |
| `/watch Chicago - Dallas` | Watch a lane |
| `/watches` | List watches |
| `/unwatch` | Clear watches |
| `/help` | Help |

## Data

Loads live in `data/loads.json` (USD, miles, lbs). Restart the bot after editing.

Current board is a **US demo dataset**. Swap in DAT / Truckstop / broker feed later via the same `LoadRepository`.

## Security

- Keep the token only in `.env` (gitignored)
- If the token was shared in chat, revoke it in @BotFather
- Optional allow-list: `ALLOWED_USER_IDS`

## Tests

```bash
pytest -q
```
