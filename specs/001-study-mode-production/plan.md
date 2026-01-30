# Implementation Plan: Study Mode API Production Hardening

**Branch**: `001-study-mode-production` | **Date**: 2026-01-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-study-mode-production/spec.md`

## Summary

Transform the study-mode-api from a development prototype to a production-ready service by adopting proven patterns from TaskFlow API (ChatKit store, auth, config, database) and Staging-Merge Microservices (Redis caching, rate limiting). This includes converting to a proper uv-managed Python package, adding Redis caching for lesson content, implementing JWT/JWKS authentication, rate limiting, and containerization. Target: 50,000+ concurrent users.

---

## Technical Context

**Language/Version**: Python 3.12+ (targeting 3.13 for container)
**Primary Dependencies**: FastAPI 0.115+, SQLAlchemy 2.x async, redis-py 5.x, python-jose, httpx
**Storage**: PostgreSQL (asyncpg), Redis (Upstash)
**Testing**: pytest with pytest-asyncio
**Target Platform**: Linux container (Docker/Kubernetes)
**Project Type**: Single API service
**Performance Goals**: 50,000+ concurrent users, <50ms cached response (p95), <2s uncached
**Constraints**: Container image <500MB, cold start <10s, no wildcard CORS in production
**Scale/Scope**: Stateless API with external state in PostgreSQL + Redis

### Key Dependencies (pyproject.toml)

```toml
dependencies = [
    "fastapi>=0.115.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "redis>=5.0.0",
    "httpx>=0.28.0",
    "python-jose[cryptography]>=3.3.0",
    "uvicorn[standard]>=0.32.0",
    "python-dotenv>=1.0.0",
    "openai-agents>=0.0.9",
    "openai-chatkit>=1.4.0",
]
```

### Environment Variables

| Variable          | Required | Description                                          |
| ----------------- | -------- | ---------------------------------------------------- |
| `DATABASE_URL`    | Yes      | PostgreSQL connection string                         |
| `REDIS_URL`       | Yes      | Redis/Upstash URL                                    |
| `REDIS_PASSWORD`  | Yes      | Redis password                                       |
| `SSO_URL`         | Prod     | SSO endpoint for JWKS                                |
| `GITHUB_TOKEN`    | No       | GitHub PAT for higher rate limits                    |
| `GITHUB_REPO`     | Yes      | GitHub repo (e.g., `panaversity-official/tutorsgpt`) |
| `ALLOWED_ORIGINS` | Yes      | Comma-separated CORS origins                         |
| `DEV_MODE`        | No       | Bypass auth for local dev                            |
| `LOG_LEVEL`       | No       | INFO, DEBUG, etc.                                    |

---

## Constitution Check

_GATE: Passed - no complexity violations_

- Single API service (no monorepo overhead)
- Adopting proven patterns from reference implementations
- No new abstractions - direct adaptation of TaskFlow and Staging-Merge patterns

---

## Project Structure

### Documentation (this feature)

```text
specs/001-study-mode-production/
├── spec.md              # Feature specification
├── plan.md              # This file
├── checklists/          # Implementation checklists
└── tasks.md             # Phase 2 output (/sp.tasks command)
```

### Source Code (target structure)

```text
apps/study-mode-api/
├── pyproject.toml              # NEW: uv project definition
├── uv.lock                     # NEW: Lock file
├── Dockerfile                  # NEW: Multi-stage container build
├── .dockerignore               # NEW: Exclude unnecessary files
├── .env.example                # UPDATE: Add new env vars
├── src/
│   └── study_mode_api/
│       ├── __init__.py
│       ├── main.py             # NEW: FastAPI app with lifespan
│       ├── config.py           # NEW: Pydantic settings (from TaskFlow)
│       ├── auth.py             # NEW: JWT/JWKS auth (from TaskFlow)
│       │
│       ├── core/               # NEW: Core infrastructure
│       │   ├── __init__.py
│       │   ├── redis_cache.py  # NEW: Redis client + decorator (from Staging-Merge)
│       │   ├── rate_limit.py   # NEW: Lua-based rate limiter (from Staging-Merge)
│       │   └── lifespan.py     # NEW: App startup/shutdown (from Staging-Merge)
│       │
│       ├── chatkit_store/      # MIGRATE: From current flat structure
│       │   ├── __init__.py
│       │   ├── config.py       # UPDATE: Enhanced pool settings (from TaskFlow)
│       │   ├── context.py      # UPDATE: Add organization_id
│       │   └── postgres_store.py  # UPDATE: Connection pooling (from TaskFlow)
│       │
│       ├── services/           # NEW: Business logic
│       │   ├── __init__.py
│       │   ├── content_loader.py   # NEW: GitHub content fetching with cache
│       │   └── study_agent.py      # MIGRATE: Agent creation logic
│       │
│       └── routers/            # NEW: Route modules
│           ├── __init__.py
│           ├── health.py       # NEW: Liveness/readiness (from TaskFlow)
│           └── chatkit.py      # NEW: ChatKit routes
│
├── chatkit_store/              # DELETE: Replaced by src/study_mode_api/chatkit_store/
├── server.py                   # DELETE: Replaced by src/study_mode_api/main.py
└── requirements.txt            # DELETE: Replaced by pyproject.toml
```

**Structure Decision**: Single API service with `src/` layout for proper Python packaging. All existing code in flat `chatkit_store/` directory migrates to `src/study_mode_api/chatkit_store/` with enhancements from TaskFlow patterns.

---

## Implementation Phases

### Phase 1: Project Structure & Build (P1) - FR-001, FR-002, FR-034, FR-035, FR-036

**Goal**: Convert to proper uv-managed package structure with containerization.

#### Tasks

| Task | Source                  | Target                           | Action                                         |
| ---- | ----------------------- | -------------------------------- | ---------------------------------------------- |
| 1.1  | TaskFlow pyproject.toml | `pyproject.toml`                 | Create with dependencies from TaskFlow + redis |
| 1.2  | -                       | `src/study_mode_api/__init__.py` | Create package                                 |
| 1.3  | TaskFlow Dockerfile     | `Dockerfile`                     | Adapt multi-stage build                        |
| 1.4  | -                       | `.dockerignore`                  | Create exclusion list                          |
| 1.5  | Current `.env.example`  | `.env.example`                   | Add new env vars                               |

**File Mappings**:

- `pyproject.toml`: Base on TaskFlow, add redis dependency, remove Dapr
- `Dockerfile`: Copy from TaskFlow, update entry point to `study_mode_api.main:app`

---

### Phase 2: Configuration & Core Infrastructure (P1) - FR-003 to FR-013, FR-027, FR-028

**Goal**: Set up centralized configuration, Redis client, and enhanced database pooling.

#### Tasks

| Task | Source                                   | Target                                               | Action                     |
| ---- | ---------------------------------------- | ---------------------------------------------------- | -------------------------- |
| 2.1  | TaskFlow config.py                       | `src/study_mode_api/config.py`                       | Adapt settings class       |
| 2.2  | Staging-Merge redis_cache.py             | `src/study_mode_api/core/redis_cache.py`             | Copy with modifications    |
| 2.3  | Staging-Merge lifespan.py                | `src/study_mode_api/core/lifespan.py`                | Adapt for Redis + DB       |
| 2.4  | TaskFlow chatkit_store/config.py         | `src/study_mode_api/chatkit_store/config.py`         | Enhanced pool config       |
| 2.5  | TaskFlow chatkit_store/postgres_store.py | `src/study_mode_api/chatkit_store/postgres_store.py` | Add pool warming, timeouts |

**config.py Adaptations** (from TaskFlow):

- Keep: `database_url`, `sso_url`, `allowed_origins`, `debug`, `log_level`, `dev_mode`, `dev_user_*`
- Add: `redis_url`, `redis_password`, `redis_max_connections`, `github_token`, `github_repo`, `content_cache_ttl`
- Remove: `mcp_server_url`, `openai_api_key`, `dapr_*`, `notification_*`

**redis_cache.py Adaptations** (from Staging-Merge):

- Keep: `start_redis()`, `stop_redis()`, `get_redis()`, `safe_redis_get()`, `safe_redis_set()`, `cache_response()` decorator
- Update: Import settings from local config
- Add: `cache_lesson_content()` function for content-specific caching

**postgres_store.py Adaptations** (from TaskFlow):

- Copy: `_create_engine()` method with `pool_pre_ping=True`, `connect_args` with `command_timeout`, `server_settings`
- Copy: `_warm_connection_pool()` method
- Copy: `initialize_schema()` with schema existence check
- Update: Schema name to `study_mode_chat`

---

### Phase 3: Content Loading with Redis Cache (P1) - FR-014 to FR-017

**Goal**: Fetch lesson content from GitHub with Redis caching.

#### Tasks

| Task | Source            | Target                                          | Action              |
| ---- | ----------------- | ----------------------------------------------- | ------------------- |
| 3.1  | Current server.py | `src/study_mode_api/services/content_loader.py` | Extract and enhance |
| 3.2  | -                 | Add GitHub API fetching                         | New functionality   |
| 3.3  | -                 | Add Redis cache integration                     | New functionality   |

**content_loader.py Design**:

```python
# Key functions
async def load_lesson_content(lesson_path: str) -> tuple[str, str]:
    """Load lesson content from cache or GitHub."""
    cache_key = f"lesson:{lesson_path}"

    # Check Redis cache first (FR-016)
    cached = await safe_redis_get(cache_key)
    if cached:
        data = json.loads(cached)
        return data["content"], data["title"]

    # Fetch from GitHub (FR-014)
    content, title = await fetch_from_github(lesson_path)

    # Cache with 24hr TTL (FR-012)
    await safe_redis_set(cache_key, json.dumps({"content": content, "title": title}), 86400)

    return content, title

async def fetch_from_github(lesson_path: str) -> tuple[str, str]:
    """Fetch lesson from GitHub raw content API."""
    # Try both .md and .mdx extensions (FR-017)
    base_url = f"https://raw.githubusercontent.com/{settings.github_repo}/main/apps/learn-app/docs/{lesson_path}"

    headers = {}
    if settings.github_token:  # FR-015: authenticated requests
        headers["Authorization"] = f"token {settings.github_token}"

    async with httpx.AsyncClient() as client:
        for ext in [".md", ".mdx", "/index.md", "/README.md"]:
            try:
                response = await client.get(f"{base_url}{ext}", headers=headers)
                if response.status_code == 200:
                    content = response.text
                    title = extract_title(content, lesson_path)
                    return content, title
            except httpx.HTTPError:
                continue

    return "", f"Page: {lesson_path}"
```

---

### Phase 4: Rate Limiting (P1) - FR-018 to FR-021

**Goal**: Implement atomic rate limiting with Redis Lua scripts.

#### Tasks

| Task | Source                      | Target                                  | Action                      |
| ---- | --------------------------- | --------------------------------------- | --------------------------- |
| 4.1  | Staging-Merge rate_limit.py | `src/study_mode_api/core/rate_limit.py` | Copy with minor adaptations |
| 4.2  | -                           | Apply to ChatKit endpoint               | Integration                 |

**File Adaptations**:

- Keep: `RATE_LIMIT_SCRIPT` (Lua), `RateLimitConfig`, `RateLimiter` class, `rate_limit()` decorator
- Update: Import `get_redis` from local `redis_cache.py`
- Update: Configure default as 20 requests/minute (FR-020)
- Keep: Fail-open behavior when Redis unavailable (FR-021)

---

### Phase 5: Authentication (P2) - FR-022 to FR-026

**Goal**: Implement JWT/JWKS authentication with dev mode bypass.

#### Tasks

| Task | Source           | Target                        | Action                  |
| ---- | ---------------- | ----------------------------- | ----------------------- |
| 5.1  | TaskFlow auth.py | `src/study_mode_api/auth.py`  | Copy with modifications |
| 5.2  | -                | Integrate with ChatKit routes | Apply dependency        |

**File Adaptations**:

- Keep: `get_jwks()`, `verify_jwt()`, `verify_opaque_token()`, `CurrentUser` class, `get_current_user()` dependency
- Keep: JWKS caching with 1hr TTL (FR-023)
- Keep: Expired cache fallback (FR-024)
- Keep: Dev mode bypass (FR-026)
- Update: Import settings from local config

---

### Phase 6: Health Checks (P2) - FR-029, FR-030

**Goal**: Add liveness and readiness endpoints for container orchestration.

#### Tasks

| Task | Source                     | Target                                 | Action                |
| ---- | -------------------------- | -------------------------------------- | --------------------- |
| 6.1  | TaskFlow routers/health.py | `src/study_mode_api/routers/health.py` | Copy with Redis check |

**Readiness Check Design**:

```python
@router.get("/health/ready")
async def ready():
    """Readiness check - verifies database and Redis connections."""
    checks = {"database": "unknown", "redis": "unknown"}

    # Database check
    try:
        async with postgres_store.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis check
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    status = "ready" if all(v == "connected" for v in checks.values()) else "unhealthy"
    return {"status": status, **checks}
```

---

### Phase 7: Main Application Assembly (P2) - FR-031 to FR-033

**Goal**: Assemble all components into the main FastAPI application.

#### Tasks

| Task | Source            | Target                                       | Action                 |
| ---- | ----------------- | -------------------------------------------- | ---------------------- |
| 7.1  | TaskFlow main.py  | `src/study_mode_api/main.py`                 | Adapt structure        |
| 7.2  | Current server.py | `src/study_mode_api/services/study_agent.py` | Migrate agent logic    |
| 7.3  | -                 | `src/study_mode_api/routers/chatkit.py`      | Extract ChatKit routes |

**main.py Structure**:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .core.lifespan import lifespan
from .routers import health, chatkit

app = FastAPI(
    title="Study Mode API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS - no wildcards (FR-027, FR-028)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(chatkit.router, prefix="/chatkit")
```

---

### Phase 8: Testing & Validation (P3)

**Goal**: Verify all success criteria are met.

#### Tasks

| Task | Description                          | Success Criteria             |
| ---- | ------------------------------------ | ---------------------------- |
| 8.1  | Load test with 1000 concurrent users | SC-001: No connection errors |
| 8.2  | Measure cached response latency      | SC-002: <50ms p95            |
| 8.3  | Measure uncached response latency    | SC-003: <2s                  |
| 8.4  | Verify rate limiting enforces limits | SC-004: 429 after limit      |
| 8.5  | Verify health check response         | SC-005: <100ms               |
| 8.6  | Verify container image size          | SC-006: <500MB               |
| 8.7  | Verify cold start time               | SC-007: <10s                 |
| 8.8  | Security audit for CORS and auth     | SC-008: No wildcards in prod |

---

## File-by-File Mapping Summary

| New File                                             | Source Reference  | Key Adaptations                          |
| ---------------------------------------------------- | ----------------- | ---------------------------------------- |
| `pyproject.toml`                                     | TaskFlow          | Add redis, remove Dapr                   |
| `Dockerfile`                                         | TaskFlow          | Update entry point                       |
| `src/study_mode_api/config.py`                       | TaskFlow          | Add Redis, GitHub settings               |
| `src/study_mode_api/auth.py`                         | TaskFlow          | Direct copy, update imports              |
| `src/study_mode_api/core/redis_cache.py`             | Staging-Merge     | Update imports, add content caching      |
| `src/study_mode_api/core/rate_limit.py`              | Staging-Merge     | Update imports                           |
| `src/study_mode_api/core/lifespan.py`                | Staging-Merge     | Add DB init                              |
| `src/study_mode_api/chatkit_store/config.py`         | TaskFlow          | Update schema name                       |
| `src/study_mode_api/chatkit_store/postgres_store.py` | TaskFlow          | Add pool warming, keep study_mode schema |
| `src/study_mode_api/routers/health.py`               | TaskFlow          | Add Redis check                          |
| `src/study_mode_api/services/content_loader.py`      | Current server.py | Add GitHub API + cache                   |
| `src/study_mode_api/services/study_agent.py`         | Current server.py | Extract agent creation                   |
| `src/study_mode_api/routers/chatkit.py`              | Current server.py | Extract routes                           |
| `src/study_mode_api/main.py`                         | TaskFlow          | Combine patterns                         |

---

## Risk Mitigation

| Risk                              | Mitigation                                                |
| --------------------------------- | --------------------------------------------------------- |
| Redis unavailable                 | Graceful degradation - cache miss continues to GitHub     |
| GitHub rate limits                | Authenticated requests (5000/hr) + caching                |
| Connection pool exhaustion        | Proper pool sizing (20 + 10 overflow), queue with timeout |
| Auth service down                 | Cached JWKS fallback, dev mode bypass                     |
| Migration breaks existing clients | Maintain `/chatkit` endpoint structure                    |

---

## Success Verification

After implementation, verify with:

```bash
# Build container
docker build -t study-mode-api .
docker images study-mode-api  # Verify <500MB

# Run with env vars
docker run -p 8000:8000 --env-file .env study-mode-api

# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/ready

# Cache verification
curl "http://localhost:8000/chatkit/suggestions?lesson_path=01-agent-factory-paradigm/01-digital-fte-revolution"
# Second call should be <50ms

# Rate limit test
for i in {1..25}; do curl -w "%{http_code}\n" http://localhost:8000/chatkit/suggestions; done
# Should see 429 after 20 requests
```

---

## Appendix: Reference File Paths

### TaskFlow API Reference

| File                 | Path                                                                                                             |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Config               | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/config.py`                       |
| Auth                 | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/auth.py`                         |
| Database             | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/database.py`                     |
| Main                 | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/main.py`                         |
| ChatKit Store Config | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/chatkit_store/config.py`         |
| ChatKit Store        | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/chatkit_store/postgres_store.py` |
| Health Router        | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/routers/health.py`               |
| Dockerfile           | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/Dockerfile`                                       |
| pyproject.toml       | `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/pyproject.toml`                                   |

### Staging-Merge Microservices Reference

| File        | Path                                                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Redis Cache | `/Users/mjs/Documents/code/panaversity-official/project-coding/staging-merge/microservices/enrollment/app/core/redis_cache.py` |
| Rate Limit  | `/Users/mjs/Documents/code/panaversity-official/project-coding/staging-merge/microservices/enrollment/app/core/rate_limit.py`  |
| Lifespan    | `/Users/mjs/Documents/code/panaversity-official/project-coding/staging-merge/microservices/enrollment/app/core/lifespan.py`    |

### Current Study Mode API (to be migrated)

| File          | Path                                                                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| Server        | `/Users/mjs/Documents/code/panaversity-official/tutorsgpt/ask/apps/study-mode-api/server.py`                       |
| ChatKit Store | `/Users/mjs/Documents/code/panaversity-official/tutorsgpt/ask/apps/study-mode-api/chatkit_store/postgres_store.py` |
| Store Config  | `/Users/mjs/Documents/code/panaversity-official/tutorsgpt/ask/apps/study-mode-api/chatkit_store/config.py`         |
| Context       | `/Users/mjs/Documents/code/panaversity-official/tutorsgpt/ask/apps/study-mode-api/chatkit_store/context.py`        |
