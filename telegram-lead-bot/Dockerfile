FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY data/fleetguard-leads.csv ./data/fleetguard-leads.csv
COPY data/fleetguard-leads.sample.csv ./data/fleetguard-leads.sample.csv
COPY run_bot.sh .

# Runtime state lives here; mount a volume in production if you want persistence.
RUN mkdir -p /app/data /app/logs \
    && chmod +x run_bot.sh

# Railway restarts the container on crash (see railway.toml).
# Prefer direct python entry so deploy logs show the real error.
CMD ["python", "-m", "bot"]
