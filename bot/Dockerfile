FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot package; media is a named volume mounted at /app/media
COPY bot/ ./bot/

CMD ["python", "-m", "bot.main"]
