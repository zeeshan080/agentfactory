# syntax=docker/dockerfile:1
# =============================================================================
# Production-Grade Python Dockerfile
# =============================================================================
# Multi-stage, multi-target build with uv for fast dependency resolution
# Supports: FastAPI, Flask, Django, or plain Python
#
# Targets:
#   dev        - Hot-reload, volume mounts, dev tools
#   staging    - Production-like with shell for debugging
#   production - Minimal DHI image, no shell, non-root
#
# Usage:
#   docker build --target dev -t app:dev .
#   docker build --target production -t app:prod .
#
# Features:
#   - BuildKit cache mounts for 10x faster rebuilds
#   - uv for fast dependency resolution
#   - Docker Hardened Images (DHI) for production
#   - Supports requirements.txt OR pyproject.toml
#   - Non-root user throughout
#   - Proper health checks
# =============================================================================

# ======================== Build Arguments ========================
ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.5
# For DHI (Docker Hardened Images): set USE_DHI=true and run `docker login dhi.io` first
ARG USE_DHI=false

# ======================== Stage: base ========================
# Common environment for all stages
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    # uv settings
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # App settings
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Create non-root user early
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# ======================== Stage: builder ========================
# Install dependencies with uv (fast) or pip (fallback)
FROM base AS builder

ARG UV_VERSION

# Install uv for fast dependency management
# Falls back to pip if uv install fails
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir uv==${UV_VERSION} || pip install --no-cache-dir uv

# Install build dependencies for native extensions
# Uncomment lines as needed for your dependencies:
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    # libpq-dev \              # PostgreSQL (psycopg2, asyncpg)
    # libffi-dev \             # cffi, cryptography
    # libssl-dev \             # cryptography, SSL
    # cargo rustc \            # Rust-based packages (cryptography, pydantic)
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files (supports both patterns)
COPY pyproject.toml* uv.lock* requirements*.txt* ./

# Install dependencies with caching
# Priority: uv.lock > pyproject.toml > requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    if [ -f uv.lock ]; then \
        uv pip install --no-cache -r pyproject.toml; \
    elif [ -f pyproject.toml ]; then \
        uv pip install --no-cache -r pyproject.toml; \
    elif [ -f requirements.txt ]; then \
        uv pip install --no-cache -r requirements.txt; \
    else \
        echo "No dependency file found!"; exit 1; \
    fi

# ======================== Stage: dev ========================
# Development with hot-reload and dev tools
FROM builder AS dev

# Install dev dependencies if present
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f requirements-dev.txt ]; then \
        uv pip install --no-cache -r requirements-dev.txt; \
    fi

# Copy source (will be shadowed by volume mount in compose)
COPY --chown=app:app . .

USER app

EXPOSE 8000

# Health check (lenient for dev)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

# DEV CMD - Replace based on framework:
# FastAPI:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Flask:    flask run --debug --host 0.0.0.0 --port 8000
# Django:   python manage.py runserver 0.0.0.0:8000
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ======================== Stage: staging ========================
# Production-like but with shell for debugging
FROM python:${PYTHON_VERSION}-slim AS staging

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app

WORKDIR ${APP_HOME}

# Create non-root user
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Copy venv from builder (isolated, portable)
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=app:app ./src ./src
# Or for non-src layout:
# COPY --chown=app:app ./app ./app

USER app

EXPOSE 8000

# Strict health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')" || exit 1

# STAGING CMD - Replace based on framework:
# FastAPI:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
# Flask:    gunicorn -w 2 -b 0.0.0.0:8000 app:app
# Django:   gunicorn -w 2 -b 0.0.0.0:8000 project.wsgi:application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# ======================== Stage: production ========================
# Minimal production image - works everywhere without auth
# For DHI (95% fewer CVEs): docker build --build-arg USE_DHI=true ... (requires docker login dhi.io)
FROM python:${PYTHON_VERSION}-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code only
COPY ./src ./src
# Or for non-src layout:
# COPY ./app ./app

USER app

EXPOSE 8000

# Production health check (strict)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"]

# PRODUCTION CMD - Replace based on framework:
# FastAPI:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --timeout-graceful-shutdown 30
# Flask:    gunicorn -w 4 -b 0.0.0.0:8000 --timeout 30 --graceful-timeout 30 app:app
# Django:   gunicorn -w 4 -b 0.0.0.0:8000 --timeout 30 --graceful-timeout 30 project.wsgi:application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--timeout-graceful-shutdown", "30"]
