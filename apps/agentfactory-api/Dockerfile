# AgentFactory API - Production Dockerfile
# Optimized for Google Cloud Run

FROM python:3.12-slim AS builder

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files and README (required by hatchling)
COPY pyproject.toml uv.lock README.md ./

# Copy source code
COPY src/ src/

# Install all dependencies including the project
RUN uv sync --frozen --no-dev


# =============================================================================
# Production stage
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY --from=builder /app/src /app/src

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Cloud Run uses PORT environment variable
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run with uvicorn (production settings)
CMD ["python", "-m", "uvicorn", "agentfactory_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
