# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl nodejs npm gettext && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

WORKDIR /app

COPY pyproject.toml README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root

# Build CSS
COPY package.json tailwind.config.js postcss.config.js ./
RUN npm install --no-audit --no-fund

COPY checktick_app ./checktick_app
COPY manage.py ./
COPY locale ./locale
# Include documentation and contributing guide so docs pages work in production
COPY docs ./docs
COPY CONTRIBUTING.md ./
# Install the current project now that sources are present
RUN poetry install --only main --no-interaction --no-ansi
RUN npm run build:css

RUN adduser --disabled-login --gecos "" appuser
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R appuser:appuser /app/staticfiles /app/media
USER appuser

ENV DJANGO_SETTINGS_MODULE=checktick_app.settings
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-lc", "python manage.py migrate --noinput && python manage.py collectstatic --noinput --clear && CSS_HASH=$(md5sum /app/staticfiles/build/styles.css | cut -d' ' -f1) && cp /app/staticfiles/build/styles.css /app/staticfiles/build/styles.$CSS_HASH.css && echo $CSS_HASH > /tmp/css_hash.txt && gunicorn checktick_app.wsgi:application --bind 0.0.0.0:${PORT} --workers 4"]
