# =============================================================================
# Study Mode API - Production Dockerfile (Hardened)
# Multi-stage build | Non-root | Minimal attack surface | OCI compliant
# =============================================================================

# Pin versions for reproducibility
ARG PYTHON_VERSION=3.12

# -----------------------------------------------------------------------------
# Stage 1: Builder - Compile dependencies with build tools
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

# Install build dependencies for native packages
# - gcc: C compiler for native extensions
# - libpq-dev: PostgreSQL client library headers (asyncpg, psycopg)
# - libffi-dev: Foreign function interface (cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv from official image (only in builder - not copied to production)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /build

# Copy dependency files first (layer caching)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies into isolated venv
# uv pip install . reads pyproject.toml and installs all dependencies
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv pip install . --compile-bytecode

# Aggressive cleanup to minimize venv size
# Remove: pip, setuptools (not needed at runtime), tests, docs, type stubs, C headers
RUN rm -rf /app/.venv/lib/python*/site-packages/pip* \
           /app/.venv/lib/python*/site-packages/setuptools* \
           /app/.venv/lib/python*/site-packages/_distutils_hack \
           /app/.venv/lib/python*/site-packages/pkg_resources && \
    find /app/.venv -type f -name "*.pyo" -delete 2>/dev/null || true && \
    find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type d -name "__pycache__" -name "*.cpython-*.pyc" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pyi" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.md" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.rst" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.txt" ! -name "entry_points.txt" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.c" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.h" -delete 2>/dev/null || true && \
    find /app/.venv -type f -name "*.pxd" -delete 2>/dev/null || true

# -----------------------------------------------------------------------------
# Stage 2: Production Runtime (NO uv, NO build tools)
# This is the final stage - no --target flag needed
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim

# OCI standard labels
LABEL org.opencontainers.image.title="Study Mode API" \
      org.opencontainers.image.description="AI-powered tutoring with ChatKit integration" \
      org.opencontainers.image.version="5.1.0" \
      org.opencontainers.image.vendor="Panaversity" \
      org.opencontainers.image.source="https://github.com/panaversity/agentfactory" \
      org.opencontainers.image.licenses="MIT"

# Install ONLY runtime dependencies (minimal)
# - libpq5: PostgreSQL client library (required by psycopg at runtime)
# NO curl - we use Python's built-in urllib for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user (k8s runAsNonRoot compatible)
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --shell /sbin/nologin --no-create-home --no-log-init app

WORKDIR /app

# Copy ONLY the venv from builder (uv stays in builder, not copied here)
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy application source
COPY --chown=app:app src/ ./src/

# Environment configuration
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# Switch to non-root user
USER app

EXPOSE 8000

# Health check using Python stdlib (no curl needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

STOPSIGNAL SIGTERM

# Production uvicorn (single worker - scale with k8s replicas)
CMD ["sh", "-c", "exec uvicorn study_mode_api.main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --no-access-log"]
