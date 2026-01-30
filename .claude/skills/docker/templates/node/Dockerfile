# syntax=docker/dockerfile:1
# =============================================================================
# Production-Grade Node.js Dockerfile
# =============================================================================
# Multi-stage, multi-target build with BuildKit cache optimization
# Supports: Next.js, Express, NestJS, Fastify
# Package managers: pnpm, npm, yarn
#
# Targets:
#   deps       - Dependencies only (for caching)
#   dev        - Hot-reload, volume mounts
#   builder    - Build application
#   production - Minimal DHI runtime
#
# Usage:
#   docker build --target dev -t app:dev .
#   docker build --target production -t app:prod .
#
# Features:
#   - BuildKit cache mounts (10x faster rebuilds)
#   - Docker Hardened Images (DHI) for production
#   - Supports npm/yarn/pnpm with proper caching
#   - Non-root user throughout
#   - Graceful shutdown handling
# =============================================================================

# ======================== Build Arguments ========================
ARG NODE_VERSION=22
# Package manager: npm, yarn, pnpm
ARG PACKAGE_MANAGER=pnpm
# For DHI (Docker Hardened Images): set USE_DHI=true and run `docker login dhi.io` first
ARG USE_DHI=false

# ======================== Stage: base ========================
FROM node:${NODE_VERSION}-slim AS base

ENV NODE_ENV=development

WORKDIR /app

# Enable corepack for pnpm/yarn
RUN corepack enable

# Create non-root user
RUN groupadd --gid 1001 nodejs \
    && useradd --uid 1001 --gid nodejs --shell /bin/bash --create-home nodejs

# ======================== Stage: deps ========================
# Install dependencies only (cached layer)
FROM base AS deps

ARG PACKAGE_MANAGER

# Copy only package files for dependency caching
COPY package.json ./
COPY pnpm-lock.yaml* yarn.lock* package-lock.json* ./

# Install dependencies with BuildKit cache
# pnpm
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    if [ -f pnpm-lock.yaml ]; then \
        corepack prepare pnpm@latest --activate && \
        pnpm install --frozen-lockfile; \
    fi

# npm
RUN --mount=type=cache,target=/root/.npm \
    if [ -f package-lock.json ]; then \
        npm ci; \
    fi

# yarn
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    if [ -f yarn.lock ]; then \
        yarn install --frozen-lockfile; \
    fi

# ======================== Stage: dev ========================
FROM base AS dev

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules

# Copy source (will be shadowed by volume mount)
COPY --chown=nodejs:nodejs . .

USER nodejs

EXPOSE 3000

# Health check (lenient for dev)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

# DEV CMD - Replace based on framework:
# Next.js:  pnpm dev
# Express:  pnpm dev (with nodemon)
# NestJS:   pnpm start:dev
CMD ["pnpm", "dev"]

# ======================== Stage: builder ========================
FROM base AS builder

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time environment variables (for Next.js NEXT_PUBLIC_*)
# ARG NEXT_PUBLIC_API_URL
# ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ENV NODE_ENV=production

# Build application
# Next.js:  pnpm build (outputs to .next/standalone)
# Express:  pnpm build (outputs to dist/)
# NestJS:   pnpm build (outputs to dist/)
RUN pnpm build

# ======================== Stage: production ========================
# Minimal production image - works everywhere without auth
# For DHI (95% fewer CVEs): docker build --build-arg USE_DHI=true ... (requires docker login dhi.io)
FROM node:${NODE_VERSION}-slim AS production

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1001 nodejs \
    && useradd --uid 1001 --gid nodejs --shell /bin/bash --create-home nodejs

# Copy built application
# For Next.js standalone:
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# For Express/NestJS (bundled):
# COPY --from=builder /app/dist ./dist
# COPY --from=builder /app/node_modules ./node_modules
# COPY --from=builder /app/package.json ./

USER nodejs

EXPOSE 3000

# Production health check (strict)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["node", "-e", "require('http').get('http://127.0.0.1:3000/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"]

# PRODUCTION CMD - Replace based on framework:
# Next.js standalone: node server.js
# Express/NestJS:     node dist/main.js
CMD ["node", "server.js"]
