# Repo-root Dockerfile so Railway builds even when Root Directory is empty.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY telegram-lead-bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram-lead-bot/bot ./bot
COPY telegram-lead-bot/data/fleetguard-leads.csv ./data/fleetguard-leads.csv
COPY telegram-lead-bot/data/fleetguard-leads.sample.csv ./data/fleetguard-leads.sample.csv

RUN mkdir -p /app/data /app/logs

CMD ["python", "-m", "bot"]
