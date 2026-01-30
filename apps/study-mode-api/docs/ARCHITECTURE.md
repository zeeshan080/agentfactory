# Study Mode API - Complete Architecture

## Overview

The Study Mode API is a **production-ready ChatKit server** that provides AI-powered tutoring for the AgentFactory book. It was designed to handle **50,000+ concurrent users** with proper security, caching, and resilience patterns.

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              STUDY MODE API v5.0                                  │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│                              ┌──────────────┐                                     │
│                              │  SSO Server  │ (JWKS endpoint)                     │
│                              │  (Logto)     │                                     │
│                              └──────┬───────┘                                     │
│                                     │ JWKS keys (cached 1hr)                      │
│                                     ▼                                             │
│   ┌──────────────┐           ┌──────────────┐     ┌──────────────┐               │
│   │   Frontend   │ Bearer    │   FastAPI    │────▶│   ChatKit    │               │
│   │  (ChatKit    │──────────▶│   + Auth     │     │   Server     │               │
│   │   React UI)  │ id_token  │   + CORS     │     │   (Agent)    │               │
│   └──────────────┘           └──────────────┘     └──────────────┘               │
│          │                          │                    │                        │
│          │ localStorage:            ▼                    ▼                        │
│          │ ainative_id_token ┌──────────────┐     ┌──────────────┐               │
│          │                   │ Rate Limiter │     │  PostgreSQL  │               │
│          │                   │ (Redis/Lua)  │     │    Store     │               │
│          │                   └──────────────┘     └──────────────┘               │
│          │                          │                    │                        │
│          │                          ▼                    │                        │
│          │                   ┌──────────────┐            │                        │
│          │                   │    Redis     │◀───────────┘                        │
│          │                   │    Cache     │                                     │
│          │                   └──────────────┘                                     │
│          │                          │                                             │
│          │                          ▼                                             │
│          │                   ┌──────────────┐                                     │
│          │                   │   GitHub     │                                     │
│          │                   │   Content    │                                     │
│          │                   └──────────────┘                                     │
│          │                                                                        │
│          │  Headers sent:                                                         │
│          │  ├── Authorization: Bearer <id_token>                                  │
│          │  ├── X-User-ID: <user_id>                                              │
│          │  └── X-User-Name: <user_name>                                          │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. Configuration Layer (`config.py`)

```python
class Settings(BaseSettings):
    # Database & Redis
    database_url: str = ""
    redis_url: str = ""

    # Security
    allowed_origins: str = "http://localhost:3000"
    sso_url: str = ""
    dev_mode: bool = False

    # GitHub Content
    github_token: str = ""
    github_repo: str = "panaversity/agentfactory"
    content_cache_ttl: int = 86400  # 24 hours
```

**How it works:**
- Pydantic Settings loads from environment variables and `.env` file
- `allowed_origins_list` property splits comma-separated CORS origins
- `dev_mode` enables auth bypass for local development
- `chat_enabled` checks if ChatKit database is configured

---

### 2. Redis Caching Layer (`core/redis_cache.py`)

```python
# Connection with retry and exponential backoff
_aredis = redis.asyncio.Redis.from_url(
    redis_url,
    retry=redis.asyncio.retry.Retry(
        backoff=redis.backoff.ExponentialBackoff(),
        retries=5,
    ),
    retry_on_error=[ConnectionError, TimeoutError, ClusterError],
)
```

**What is cached:**
- **Lesson Content**: GitHub markdown files (24hr TTL)
- **Rate Limit Counters**: Per-user request counts (1 minute window)
- **JWKS Keys**: SSO public keys (1hr TTL in memory)

**Graceful Degradation:**
- If Redis unavailable, app continues without caching
- Rate limiting fails open (allows requests)

---

### 3. Rate Limiting Layer (`core/rate_limit.py`)

**Atomic Lua Script** (runs entirely in Redis, no race conditions):

```lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])      -- 20 requests
local window = tonumber(ARGV[2])     -- 60000 ms (1 minute)

local current = redis.call('incr', key)
if current == 1 then
    redis.call('pexpire', key, window)
end

if current > limit then
    return {current, window, redis.call('pttl', key)}
end
return {current, window, 0}
```

---

### 4. PostgreSQL Store (`chatkit_store/postgres_store.py`)

**Production-Ready Connection Pool:**

| Setting | Value | Purpose |
|---------|-------|---------|
| pool_size | 20 | Base persistent connections |
| max_overflow | 10 | Burst capacity (up to 30 total) |
| pool_timeout | 30s | Wait before 503 error |
| pool_recycle | 3600s | Refresh connections hourly |
| pool_pre_ping | True | Validate connection before use |
| statement_timeout | 30s | Query-level timeout |

**User Isolation:**
Every query includes `user_id` filter for multi-tenancy.

---

### 5. Content Loading (`services/content_loader.py`)

```
Request → Check Redis Cache → Hit? Return <50ms
                            → Miss? Fetch GitHub → Cache 24hr → Return
```

---

### 6. Authentication (`auth.py`)

**Token Requirements:**
- Backend requires **JWT format** (3 dot-separated parts starting with `eyJ`)
- Frontend MUST use `ainative_id_token` from localStorage (JWT format)
- `ainative_access_token` may be opaque and will fail validation

**Verification Flow:**
```
Frontend Request
    │
    ├── Authorization: Bearer <id_token>
    │
    ▼
┌─────────────────────┐
│ Check Token Format  │
│ (JWT = 3 parts)     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│ JWT Token?          │ YES │ Verify via JWKS     │
│ (starts with eyJ)   │────▶│ (cached 1hr)        │
└─────────────────────┘     └─────────────────────┘
          │ NO
          ▼
┌─────────────────────┐
│ Verify via SSO      │
│ userinfo endpoint   │
└─────────────────────┘
```

**Frontend Implementation (ChatKit):**
```typescript
// TeachMePanel uses custom fetch to inject auth
const authenticatedFetch = async (input, options) => {
  const token = localStorage.getItem("ainative_id_token"); // MUST be ID token
  return fetch(input, {
    ...options,
    headers: {
      ...options?.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      "X-User-ID": userId,
      "X-User-Name": userName,
    },
  });
};
```

**Dev Mode**: Set `DEV_MODE=true` to bypass auth for local development

---

### 7. Health Checks (`routers/health.py`)

| Endpoint | Type | Checks |
|----------|------|--------|
| `/health` | Liveness | App is running |
| `/health/ready` | Readiness | DB + Redis connectivity |

---

## Database Schema

```sql
-- Schema: study_mode_chat

CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    organization_id TEXT,
    lesson_path TEXT DEFAULT '',        -- For filtering by lesson
    title TEXT DEFAULT 'Study Session', -- Display name
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    data JSONB NOT NULL,                -- Full ThreadMetadata
    UNIQUE (id, user_id)
);

CREATE TABLE items (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    organization_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    data JSONB NOT NULL,
    UNIQUE (id, user_id)
);

CREATE TABLE attachments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    organization_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    data JSONB NOT NULL,
    UNIQUE (id, user_id)
);
```

---

## Security Layers

1. **CORS**: No wildcards in production
2. **Rate Limiting**: 20 req/min per user (atomic Lua)
3. **Authentication**: JWT/JWKS with 1hr cache
4. **User Isolation**: All queries filtered by user_id
5. **Container**: Non-root user, minimal image

---

## Performance Targets

| Metric | Target | Implementation |
|--------|--------|----------------|
| Cached Content | <50ms | Redis cache, 24hr TTL |
| Health Check | <100ms | Simple SELECT 1 |
| Cold Start | <10s | Pool warming |
| Rate Limit | 20/min | Atomic Lua script |
| Concurrent Users | 50K+ | Pool 20+10 overflow |
| Container Size | <500MB | Multi-stage build |

---

## User Context Flow

```
Frontend (React)
    │
    ├── Auth Token (JWT) ─────────────────────────────┐
    │   Contains: sub, email, name, role, org_ids     │
    │                                                  │
    └── API Request ──────────────────────────────────┤
        Headers:                                       │
        - Authorization: Bearer <token>                │
        - X-User-ID: <user_id>                        │
        - X-User-Name: <user_name>                    ▼
                                              ┌───────────────┐
                                              │   FastAPI     │
                                              │   Middleware  │
                                              └───────┬───────┘
                                                      │
                                                      ▼
                                              ┌───────────────┐
                                              │ RequestContext│
                                              ├───────────────┤
                                              │ user_id       │
                                              │ organization_id│
                                              │ request_id    │
                                              │ metadata:     │
                                              │  - user_name  │
                                              │  - lesson_path│
                                              │  - mode       │
                                              └───────┬───────┘
                                                      │
                                                      ▼
                                              ┌───────────────┐
                                              │  Study Agent  │
                                              ├───────────────┤
                                              │ STUDENT: name │
                                              │ (personalized)│
                                              └───────────────┘
```

**User Info Propagation:**
1. Frontend extracts user info from auth token
2. Passes via `X-User-ID` and `X-User-Name` headers
3. ChatKit router creates `RequestContext` with metadata
4. Agent receives user name for personalized responses

---

## Caching Strategy

| Data Type | Cached? | Location | TTL |
|-----------|---------|----------|-----|
| Lesson Content | ✅ Yes | Redis | 24hr |
| JWKS Keys | ✅ Yes | Memory | 1hr |
| Rate Limit Counters | ✅ Yes | Redis | 1min |
| Thread Metadata | ✅ Yes | Redis | 1hr |
| Thread Items | ✅ Yes | Redis | 30min |
| Thread Lists | ✅ Yes | Redis | 10min |

### CachedPostgresStore (Write-Through Pattern)

The `CachedPostgresStore` wraps `PostgresStore` with Redis caching:

```
Read Request
    │
    ▼
┌─────────────┐     HIT    ┌──────────────┐
│ Check Redis │ ──────────▶│ Return Data  │
│   Cache     │            └──────────────┘
└─────────────┘
    │ MISS
    ▼
┌─────────────┐            ┌──────────────┐
│  Query      │ ──────────▶│ Update Cache │
│ PostgreSQL  │            │  + Return    │
└─────────────┘            └──────────────┘
```

**Write-Through**: All writes go to PostgreSQL first, then update cache.

**Background Writer**: Async queue (max 1000) for non-blocking writes.

**Cache Invalidation**: Pattern-based deletion using `SCAN` command.

---

## File Structure

```
src/study_mode_api/
├── __init__.py            # Package version
├── config.py              # Pydantic Settings
├── auth.py                # JWT/JWKS authentication
├── main.py                # FastAPI app + /chatkit POST + /health endpoints
├── chatkit_server.py      # StudyModeChatKitServer (carfixer pattern)
├── fte/                   # FTE Agent System (multi-agent ready)
│   ├── __init__.py        # Exports: create_agent, AgentState
│   ├── triage.py          # Agent selection + prompts
│   └── state.py           # AgentState context management
├── core/
│   ├── redis_cache.py     # Redis + caching decorator
│   ├── rate_limit.py      # Lua-based rate limiting
│   └── lifespan.py        # App lifecycle (creates chatkit_server)
├── chatkit_store/
│   ├── config.py          # Pool settings
│   ├── context.py         # User isolation context (RequestContext)
│   ├── cached_postgres_store.py  # Redis-cached wrapper
│   └── postgres_store.py  # Full Store implementation
└── services/
    └── content_loader.py  # GitHub fetch + cache
```
