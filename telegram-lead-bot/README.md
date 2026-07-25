# FleetGuardAI Telegram Lead Bot

CSV → Telegram → best lead → contact info + personalized pitch → track follow-up.

## What you get

| Command | Action |
| --- | --- |
| `/next` | Next best lead near **~300 trucks** |
| `/highscore` | Fleets closest to **~300 trucks** (200–450 band) |
| `/search trucking company` | Find by company, DOT, city, officer |
| `/followups` | Who needs follow-up |
| `/stats` | Progress |
| `/linkphone` | Share your contact → save phone → Telegram id |
| `/settg <phone\|DOT> <@user\|id>` | Manually link Telegram to a lead phone |
| `/findtg <phone>` | Look up a saved Telegram id by phone |
| `/tglist` | Recent phone → Telegram links |

Priority = fleet size near **300 trucks** (not a 300-point score).


**Buttons on every lead:** 📞 Call · ✉️ Email · 💬 Telegram/Add Telegram · ✅ Contacted · 🔥 Interested · 📅 Follow Up · ❌ Skip · ⏭ Next

> **Telegram limit:** bots cannot look up strangers’ Telegram ids from CSV phone numbers. Use `/settg` when you know `@username` / id, or `/linkphone` when someone shares their own contact.

## Live bot

Configured for **@Moneymakeybot**.

### Why it “dies every day” on Cursor

Cursor Cloud VMs **shut down when idle**. Anything started there (tmux, `run_bot.sh`) is **not 24/7 hosting**.  
For a bot that stays online, deploy it once on Railway / Render / a VPS (below).

### Run locally (temporary)

```bash
cd telegram-lead-bot
cp .env.example .env   # add TELEGRAM_BOT_TOKEN
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash ./run_bot.sh      # auto-restarts on crash
```

Then open Telegram → `@Moneymakeybot` → `/ping` → `/next`.

### Deploy 24/7 on Railway (recommended)

1. Push this repo to GitHub (already done if you’re on the PR branch).
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Set **Root Directory** to `telegram-lead-bot`.
4. Add variables:

```env
TELEGRAM_BOT_TOKEN=your_token_from_BotFather
TELEGRAM_ALLOWED_USER_IDS=7889069727,8724669761
TELEGRAM_ALLOWED_USERNAMES=mixerius
LEADS_CSV_PATH=data/fleetguard-leads.csv
LEADS_DB_PATH=data/leads_state.db
TARGET_TRUCKS=300
TARGET_TRUCK_MIN=200
TARGET_TRUCK_MAX=450
```

5. Deploy. No public domain needed — the bot only talks outbound to Telegram.
6. In Telegram send `/ping`. If you get `pong`, it’s online for good.

Optional: attach a Railway **Volume** on `/app/data` so `leads_state.db` survives redeploys.

`Dockerfile`, `Procfile`, `railway.toml`, and `render.yaml` are included in this folder.

## Setup (5 minutes)

1. Talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. Get your user id from [@userinfobot](https://t.me/userinfobot).
3. In this folder:

```bash
cd telegram-lead-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

4. Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_ALLOWED_USER_IDS=your_numeric_id
LEADS_CSV_PATH=data/fleetguard-leads.csv
```

5. Run:

```bash
python -m bot
```

6. Open Telegram, find your bot, send `/start`, then `/next`.

## Data

- Default CSV: `data/fleetguard-leads.csv` (same schema as your FleetGuard export).
- Sample file for quick tests: `data/fleetguard-leads.sample.csv`.
- Outreach state is stored in `data/leads_state.db` (SQLite).

## Notes

- Only users listed in `TELEGRAM_ALLOWED_USER_IDS` can use the bot.
- `/next` ranks fleets closest to **~300 trucks** (band 200–450), then by contact/fit quality.
- `/highscore` lists the closest ~300-truck fleets.
- 📅 Follow Up schedules a reminder date (`FOLLOWUP_DAYS`, default 3). Check with `/followups`.
- Use for legitimate B2B outreach. Honor opt-outs. Don’t spam SMS without consent.
