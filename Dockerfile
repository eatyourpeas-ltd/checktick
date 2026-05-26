# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl nodejs npm gettext && rm -rf /var/lib/apt/lists/*

# Upgrade pip to fix CVE-2026-1703 (path traversal vulnerability)
RUN pip install --no-cache-dir --upgrade pip>=26.0
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

# Install sct binary (SNOMED CT toolchain) — pre-built release, no Rust needed
ARG SCT_VERSION=v3.11-ctfix1
ARG SCT_REPO=eatyourpeas/sct
RUN set -eux; \
    ARCH=$(uname -m); \
    case "$ARCH" in \
    x86_64)  SCT_ARCH="x86_64" ;; \
    aarch64) SCT_ARCH="aarch64" ;; \
    *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/${SCT_REPO}/releases/download/${SCT_VERSION}/sct-linux-${SCT_ARCH}.tar.gz" \
    -o /tmp/sct.tar.gz; \
    tar -xzf /tmp/sct.tar.gz -C /usr/local/bin sct; \
    chmod +x /usr/local/bin/sct; \
    rm /tmp/sct.tar.gz; \
    sct --version

WORKDIR /app

COPY pyproject.toml README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root

# Build CSS
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY checktick_app ./checktick_app
COPY manage.py ./
COPY locale ./locale
# Include documentation and contributing guide so docs pages work in production
COPY docs ./docs
COPY CONTRIBUTING.md ./
# Install the current project now that sources are present
RUN poetry install --only main --no-interaction --no-ansi
RUN NODE_OPTIONS=--max-old-space-size=384 npm run build:css

RUN adduser --disabled-login --gecos "" appuser
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R appuser:appuser /app/staticfiles /app/media
USER appuser

ENV DJANGO_SETTINGS_MODULE=checktick_app.settings
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-lc", "python manage.py migrate --noinput && python manage.py sync_branding && python manage.py sync_nhs_dd_datasets && python manage.py sync_global_question_group_templates && python manage.py collectstatic --noinput --clear && CSS_HASH=$(md5sum /app/staticfiles/build/styles.css | cut -d' ' -f1) && cp /app/staticfiles/build/styles.css /app/staticfiles/build/styles.$CSS_HASH.css && echo $CSS_HASH > /tmp/css_hash.txt && gunicorn checktick_app.wsgi:application --bind 0.0.0.0:${PORT} --workers 4"]
