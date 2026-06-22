FROM python:3.13-slim

WORKDIR /app

# System deps: psycopg2 needs libpq, Pillow needs libjpeg + zlib
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY admin_panel/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY admin_panel/ .

EXPOSE 8000

CMD python manage.py migrate --no-input \
 && python manage.py collectstatic --no-input --clear \
 && exec gunicorn \
      --bind 0.0.0.0:8000 \
      --workers 2 \
      --timeout 120 \
      --access-logfile - \
      --error-logfile - \
      admin_panel.wsgi:application
