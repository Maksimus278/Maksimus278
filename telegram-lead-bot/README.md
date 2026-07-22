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

Configured for **@Moneymakeybot**. With `TELEGRAM_ALLOWED_USER_IDS` empty, the **first person who sends `/start` becomes the owner**.

```bash
cd telegram-lead-bot
cp .env.example .env   # add TELEGRAM_BOT_TOKEN
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m bot
```

Then open Telegram → `@Moneymakeybot` → `/start` → `/next`.

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
