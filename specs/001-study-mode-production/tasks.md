# Tasks: Study Mode API Production Hardening

**Input**: Design documents from `/specs/001-study-mode-production/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Tests are NOT explicitly requested - implementation-focused tasks only.

**Organization**: Tasks are grouped by user story priority (P1 first) to enable independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Base path**: `apps/study-mode-api/`
- **Source**: `apps/study-mode-api/src/study_mode_api/`
- **Reference TaskFlow**: `/Users/mjs/Documents/code/mjunaidca/taskforce_agent1/apps/api/src/taskflow_api/`
- **Reference Staging-Merge**: `/Users/mjs/Documents/code/panaversity-official/project-coding/staging-merge/microservices/enrollment/app/core/`

---

## Phase 1: Setup (Project Structure)

**Purpose**: Convert to uv-managed package with proper structure

- [ ] T001 Create `apps/study-mode-api/pyproject.toml` with all dependencies. **Ref**: TaskFlow pyproject.toml. Add: redis>=5.0.0, remove Dapr-related deps.
- [ ] T002 Create `apps/study-mode-api/src/study_mode_api/__init__.py` with version string.
- [ ] T003 [P] Create `apps/study-mode-api/.dockerignore` with standard Python exclusions.
- [ ] T004 [P] Update `apps/study-mode-api/.env.example` with new env vars: REDIS_URL, REDIS_PASSWORD, GITHUB_TOKEN, GITHUB_REPO, ALLOWED_ORIGINS, SSO_URL, DEV_MODE.
- [ ] T005 Use `cd apps/study-mode-api && uv sync` to install dependencies. Verify with `uv pip list`.

**Checkpoint**: Project structure ready, dependencies installable

---

## Phase 2: Foundational (Core Infrastructure)

**Purpose**: Core infrastructure that MUST complete before user stories

**⚠️ CRITICAL**: All user stories depend on this phase

### Configuration

- [ ] T006 Create `apps/study-mode-api/src/study_mode_api/config.py` with Settings class. **Ref**: TaskFlow config.py. Add: redis*url, redis_password, github_token, github_repo, content_cache_ttl. Remove: mcp_server_url, dapr*_, notification\__.
- [ ] T007 [P] Create `apps/study-mode-api/src/study_mode_api/core/__init__.py` with exports.

### Redis Infrastructure

- [ ] T008 Create `apps/study-mode-api/src/study_mode_api/core/redis_cache.py`. **Ref**: Staging-Merge redis_cache.py. Include: start_redis(), stop_redis(), get_redis(), safe_redis_get(), safe_redis_set(), @cache_response decorator with retry and exponential backoff.
- [ ] T009 Create `apps/study-mode-api/src/study_mode_api/core/rate_limit.py`. **Ref**: Staging-Merge rate_limit.py. Include: RATE_LIMIT_SCRIPT (Lua), RateLimitConfig, RateLimiter class, @rate_limit decorator. Configure default 20 req/min.

### Database Infrastructure

- [ ] T010 Create `apps/study-mode-api/src/study_mode_api/chatkit_store/__init__.py` with exports: PostgresStore, StoreConfig, RequestContext.
- [ ] T011 Create `apps/study-mode-api/src/study_mode_api/chatkit_store/config.py`. **Ref**: TaskFlow chatkit_store/config.py. Include: pool_size=20, max_overflow=10, pool_pre_ping=True, connect_args with command_timeout and statement_timeout. Schema: study_mode_chat.
- [ ] T012 Create `apps/study-mode-api/src/study_mode_api/chatkit_store/context.py`. **Ref**: TaskFlow chatkit_store/context.py. Include: RequestContext with user_id (required), organization_id (optional), request_id, metadata.
- [ ] T013 Create `apps/study-mode-api/src/study_mode_api/chatkit_store/postgres_store.py`. **Ref**: TaskFlow chatkit_store/postgres_store.py. **Doc**: Fetch SQLAlchemy docs via Context7 for async session factory patterns. Include: async_sessionmaker, \_warm_connection_pool(), schema existence check, Pydantic wrappers (ThreadData, ItemData), proper error handling with rollback.

### Lifespan Management

- [ ] T014 Create `apps/study-mode-api/src/study_mode_api/core/lifespan.py`. **Ref**: Staging-Merge lifespan.py. Include: async lifespan context manager with start_redis(), stop_redis(), PostgresStore initialization, pool warming.

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Lesson Content Access with Caching (Priority: P1) 🎯 MVP

**Goal**: Fetch lesson content from GitHub with Redis caching for fast repeated access

**Independent Test**: Request same lesson twice - second request should be <50ms (cache hit)

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create `apps/study-mode-api/src/study_mode_api/services/__init__.py` with exports.
- [ ] T016 [US1] Create `apps/study-mode-api/src/study_mode_api/services/content_loader.py`. Include: load_lesson_content() with Redis cache check, fetch_from_github() with authenticated requests, extract_title(), handle .md/.mdx extensions. Cache TTL: 24hr (86400s).
- [ ] T017 [US1] Create `apps/study-mode-api/src/study_mode_api/routers/__init__.py` with exports.
- [ ] T018 [US1] Create `apps/study-mode-api/src/study_mode_api/routers/chatkit.py`. Include: /chatkit/suggestions endpoint that uses content_loader, apply rate limiting.

**Checkpoint**: Lesson content caching functional - can test with curl

---

## Phase 4: User Story 2 - Connection Pool Resilience (Priority: P1)

**Goal**: Handle 50K concurrent users with proper connection pooling

**Independent Test**: Load test with 100+ concurrent requests - no connection errors

### Implementation for User Story 2

- [ ] T019 [US2] Update `apps/study-mode-api/src/study_mode_api/chatkit_store/postgres_store.py` to add pool_pre_ping validation. Verify connections are tested before use.
- [ ] T020 [US2] Add connection timeout handling in postgres_store.py. Queue requests with 30s timeout, return 503 if exceeded.
- [ ] T021 [US2] Add logging for connection pool metrics in lifespan.py - log pool size, overflow, recycled connections on startup.

**Checkpoint**: Connection pool resilient - ready for load testing

---

## Phase 5: User Story 3 - Rate Limiting Protection (Priority: P1)

**Goal**: Protect API from abuse with per-user rate limiting via Redis

**Independent Test**: Send 25 requests rapidly - should get 429 after request 20

### Implementation for User Story 3

- [ ] T022 [US3] Apply @rate_limit decorator to ChatKit endpoints in routers/chatkit.py. Configure: 20 requests/minute per user.
- [ ] T023 [US3] Add rate limit headers to responses: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset.
- [ ] T024 [US3] Add fail-open behavior in rate_limit.py - if Redis unavailable, allow request but log error.

**Checkpoint**: Rate limiting active - API protected from abuse

---

## Phase 6: User Story 4 - Health Checks (Priority: P2)

**Goal**: Liveness and readiness endpoints for container orchestration

**Independent Test**: Call /health and /health/ready - both return 200 with status

### Implementation for User Story 4

- [ ] T025 [US4] Create `apps/study-mode-api/src/study_mode_api/routers/health.py`. **Ref**: TaskFlow routers/health.py. Include: /health (liveness), /health/ready (readiness with DB and Redis checks).
- [ ] T026 [US4] Add health router to main app.

**Checkpoint**: Health checks functional - container orchestration ready

---

## Phase 7: User Story 5 - JWT/JWKS Authentication (Priority: P2)

**Goal**: Validate JWT tokens using JWKS public keys with dev mode bypass

**Independent Test**: Send request with valid JWT - proceeds; invalid JWT - 401

### Implementation for User Story 5

- [ ] T027 [US5] Create `apps/study-mode-api/src/study_mode_api/auth.py`. **Ref**: TaskFlow auth.py. **Doc**: Fetch python-jose docs via Context7 for JWT verification. Include: get_jwks() with 1hr cache, verify_jwt(), verify_opaque_token() fallback, CurrentUser class, get_current_user() dependency, dev_mode bypass.
- [ ] T028 [US5] Update routers/chatkit.py to optionally require authentication (based on DEV_MODE setting).
- [ ] T029 [US5] Extract user_id from JWT claims instead of query params when auth enabled.

**Checkpoint**: Authentication functional - secure in production, bypassable in dev

---

## Phase 8: User Story 6 - CORS Security (Priority: P2)

**Goal**: Restrict CORS to allowed origins only (no wildcards in production)

**Independent Test**: Request from evil.com origin - should be rejected

### Implementation for User Story 6

- [ ] T030 [US6] Update config.py to add allowed_origins_list property that splits ALLOWED_ORIGINS env var.
- [ ] T031 [US6] Configure CORS middleware in main.py with settings.allowed_origins_list instead of "\*".

**Checkpoint**: CORS secured - only allowed origins can access API

---

## Phase 9: User Story 7 - Container Deployment (Priority: P3)

**Goal**: Multi-stage Dockerfile with uv for production deployment

**Independent Test**: Build and run container - API responds to health check

### Implementation for User Story 7

- [ ] T032 [US7] Create `apps/study-mode-api/Dockerfile`. **Ref**: TaskFlow Dockerfile. Use multi-stage build with python:3.12-slim, install uv, run as non-root user (appuser), expose port 8000, include HEALTHCHECK.
- [ ] T033 [US7] Update Dockerfile CMD to run uvicorn with study_mode_api.main:app.
- [ ] T034 [US7] Test container build: `docker build -t study-mode-api apps/study-mode-api/`. Verify image size <500MB.

**Checkpoint**: Container deployable - ready for production

---

## Phase 10: Main Application Assembly

**Purpose**: Assemble all components into FastAPI app

### Implementation

- [ ] T035 Create `apps/study-mode-api/src/study_mode_api/services/study_agent.py`. Migrate agent creation logic from current server.py - TEACH_PROMPT, ChatKitServer integration.
- [ ] T036 Create `apps/study-mode-api/src/study_mode_api/main.py`. **Ref**: TaskFlow main.py. Include: FastAPI app with lifespan, CORS middleware, exception handlers, include routers (health, chatkit).
- [ ] T037 Update routers/chatkit.py to integrate with study_agent.py for full ChatKit functionality.

**Checkpoint**: Main app functional - all components integrated

---

## Phase 11: Migration & Cleanup

**Purpose**: Clean migration from old structure

### Implementation

- [ ] T038 Verify all functionality from old server.py is preserved in new structure.
- [ ] T039 Delete old files after verification: `apps/study-mode-api/server.py`, `apps/study-mode-api/chatkit_store/` (old location), `apps/study-mode-api/requirements.txt`.
- [ ] T040 Update any CI/CD or deployment scripts to use new entry point: `study_mode_api.main:app`.

**Checkpoint**: Migration complete - old code removed

---

## Phase 12: Polish & Validation

**Purpose**: Final verification and documentation

- [ ] T041 [P] Run manual test: Lesson content caching (SC-002: <50ms cached)
- [ ] T042 [P] Run manual test: Rate limiting (SC-004: 429 after 20 requests)
- [ ] T043 [P] Run manual test: Health checks (SC-005: <100ms response)
- [ ] T044 Verify container image size (SC-006: <500MB)
- [ ] T045 Verify cold start time (SC-007: <10s)
- [ ] T046 Security audit: Verify no wildcard CORS, auth required in production (SC-008)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories
- **US1-US3 (Phases 3-5)**: All P1, depend on Phase 2, can run in sequence
- **US4-US6 (Phases 6-8)**: All P2, depend on Phase 2, can run in parallel with US1-3
- **US7 (Phase 9)**: P3, depends on Phase 2
- **Assembly (Phase 10)**: Depends on US1-US6 completion
- **Migration (Phase 11)**: Depends on Phase 10
- **Polish (Phase 12)**: Depends on Phase 11

### User Story Dependencies

| Story                 | Depends On | Can Parallel With       |
| --------------------- | ---------- | ----------------------- |
| US1 (Content Caching) | Phase 2    | US2, US3, US4, US5, US6 |
| US2 (Connection Pool) | Phase 2    | US1, US3, US4, US5, US6 |
| US3 (Rate Limiting)   | Phase 2    | US1, US2, US4, US5, US6 |
| US4 (Health Checks)   | Phase 2    | US1, US2, US3, US5, US6 |
| US5 (Authentication)  | Phase 2    | US1, US2, US3, US4, US6 |
| US6 (CORS)            | Phase 2    | US1, US2, US3, US4, US5 |
| US7 (Container)       | Phase 2    | All others              |

### Parallel Opportunities

**Within Phase 2 (Foundational)**:

```
T006 config.py        |  T007 core/__init__.py
                      |
T008 redis_cache.py   |  T009 rate_limit.py
                      |
T010 store/__init__.py | T011 store/config.py | T012 store/context.py
                      |
T013 postgres_store.py (depends on T010-T012)
                      |
T014 lifespan.py (depends on T008, T013)
```

**Across User Stories (after Phase 2)**:

```
US1 Content   |  US2 Pool    |  US3 Rate   |  US4 Health  |  US5 Auth   |  US6 CORS
T015-T018     |  T019-T021   |  T022-T024  |  T025-T026   |  T027-T029  |  T030-T031
```

---

## Implementation Strategy

### MVP First (Recommended)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T014) - **CRITICAL PATH**
3. Complete Phase 3: US1 Content Caching (T015-T018)
4. **VALIDATE**: Test content caching works
5. Complete Phase 4: US2 Connection Pool (T019-T021)
6. Complete Phase 5: US3 Rate Limiting (T022-T024)
7. **VALIDATE**: Core P1 functionality complete

### Incremental Delivery

After MVP validation:

1. Add US4 Health Checks → Deploy/Demo
2. Add US5 Authentication → Deploy/Demo
3. Add US6 CORS → Deploy/Demo
4. Add US7 Container → Production Ready
5. Assembly → Migration → Polish → **DONE**

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [USn] label maps task to specific user story for traceability
- All file paths are relative to repository root
- Reference files should be READ for patterns, not copied verbatim
- Adapt patterns to study-mode-api context (schema names, env vars, etc.)
- Verify each checkpoint before proceeding to next phase
