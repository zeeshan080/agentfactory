# Multi-Stage Build Patterns Reference

Source: https://docs.docker.com/build/building/multi-stage/

## Core Syntax

```dockerfile
# Stage 1: Build
FROM node:22-slim AS build
RUN npm run build

# Stage 2: Runtime (minimal)
FROM dhi.io/node:22
COPY --from=build /app/dist ./dist
CMD ["node", "dist/main.js"]
```

## Named Stages

Use `AS <name>` for readable references:

```dockerfile
FROM python:3.13-slim AS builder
# Build dependencies

FROM dhi.io/python:3.13 AS production
COPY --from=builder /app /app
```

## COPY --from Patterns

```dockerfile
# From named stage
COPY --from=builder /path/source /path/dest

# From external image
COPY --from=nginx:latest /etc/nginx/nginx.conf /nginx.conf

# From stage index (fragile - avoid)
COPY --from=0 /binary /binary
```

## Stage Inheritance

```dockerfile
FROM node:22-slim AS base
RUN corepack enable

FROM base AS development
RUN pnpm install

FROM base AS production
# Inherits base, not dev dependencies
```

## Target-Specific Builds

```bash
# Build only to specific stage
docker build --target builder -t myapp:builder .
docker build --target production -t myapp:prod .
```

## Layer Caching Optimization

Order matters for cache efficiency:

```dockerfile
# 1. System dependencies (changes rarely)
RUN apt-get update && apt-get install -y ...

# 2. Package dependencies (changes sometimes)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 3. Application code (changes frequently)
COPY ./app ./app
```

## BuildKit Cache Mounts

```dockerfile
# syntax=docker/dockerfile:1

# Python (uv/pip)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/root/.cache/pip \
    uv pip install -r requirements.txt

# Node.js (pnpm)
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# Node.js (npm)
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

## Secrets in Multi-Stage

Never bake secrets - use BuildKit secrets:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS builder

# Mount secret at build time only
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install -r requirements.txt

FROM dhi.io/python:3.13 AS production
COPY --from=builder /opt/venv /opt/venv
# Secret is NOT in final image
```

Build with:
```bash
docker build --secret id=pip_conf,src=./pip.conf .
```

## BuildKit Features

Enable BuildKit:
```bash
export DOCKER_BUILDKIT=1
# or
docker buildx build ...
```

Benefits:
- Parallel stage execution
- Better caching
- Secret mounting
- SSH agent forwarding
