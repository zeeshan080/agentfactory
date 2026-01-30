# Study Mode API - Test Plan

## Overview

This document outlines the testing strategy for the Study Mode API, covering unit tests, integration tests, and production verification.

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures, env setup
├── test_config.py           # Configuration validation (6 tests)
├── test_redis_cache.py      # Redis caching layer (14 tests)
├── test_rate_limit.py       # Rate limiting (11 tests)
├── test_health.py           # Health endpoints (7 tests)
├── test_auth.py             # JWT/JWKS authentication (13 tests)
├── test_content_loader.py   # GitHub content fetching (10 tests)
├── test_postgres_store.py   # Database operations (24 tests)
└── test_chatkit.py          # ChatKit router (16 tests)
```

**Total: ~101 tests**

---

## Test Categories

### 1. Configuration Tests (`test_config.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_default_settings` | Verify defaults load | All defaults populated |
| `test_allowed_origins_parsing` | CORS origins split | Comma-separated → list |
| `test_chat_enabled_requires_db` | Feature flag logic | Returns False if no DB |
| `test_dev_mode_bypass` | Dev mode detection | DEV_MODE=true works |
| `test_optional_urls` | URLs are optional | Empty strings allowed |
| `test_environment_loading` | Env var precedence | ENV overrides defaults |

### 2. Redis Cache Tests (`test_redis_cache.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_start_redis_success` | Connection startup | Ping successful |
| `test_start_redis_no_url` | Graceful skip | No error when no URL |
| `test_stop_redis_closes` | Clean shutdown | aclose() called |
| `test_safe_redis_get_returns_value` | Cache hit | Returns cached data |
| `test_safe_redis_get_returns_none_on_error` | Graceful degradation | No exception |
| `test_safe_redis_set_stores_value` | Cache write | setex() called |
| `test_cache_miss_calls_function` | Cache miss | Function executed |
| `test_cache_hit_returns_cached_value` | **SC-002**: <50ms | Cached return fast |
| `test_cache_decorator_graceful_degradation` | Redis down | App continues |
| `test_serialize_dict` | JSON serialization | Dict → string |
| `test_serialize_list` | List serialization | List → string |
| `test_custom_json_encoder_datetime` | Datetime handling | ISO format |
| `test_custom_json_encoder_time` | Time handling | HH:MM:SS format |

### 3. Rate Limit Tests (`test_rate_limit.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_default_config` | Config defaults | 20 req/min |
| `test_get_window_minutes` | Window calculation | Correct ms conversion |
| `test_default_identifier_with_user_id` | User extraction | user:X format |
| `test_default_identifier_falls_back_to_ip` | IP fallback | ip:X format |
| `test_default_identifier_uses_forwarded_header` | Proxy support | X-Forwarded-For |
| `test_check_rate_limit_allows_request` | Under limit | remaining > 0 |
| `test_check_rate_limit_exceeds_limit` | **SC-004**: 429 | remaining < 0 |
| `test_check_rate_limit_fail_open` | Redis down | Allows request |
| `test_decorator_sets_headers` | Response headers | X-RateLimit-* |
| `test_decorator_raises_429_when_exceeded` | Limit enforcement | HTTPException 429 |
| `test_lua_script_structure` | Script validity | Contains expected ops |

### 4. Health Tests (`test_health.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_health_returns_200` | Liveness check | Status 200 |
| `test_health_response_format` | Response structure | status, version fields |
| `test_ready_success` | Readiness check | Both DB + Redis OK |
| `test_ready_db_failure` | DB down detection | Status 503 |
| `test_ready_redis_failure` | Redis down detection | Status 503 |
| `test_ready_partial_failure` | Mixed state | Correct status |
| `test_ready_without_dependencies` | No deps configured | Healthy |

### 5. Auth Tests (`test_auth.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_get_jwks_caches` | JWKS caching | 1hr cache works |
| `test_get_jwks_fetch_success` | JWKS fetch | Keys loaded |
| `test_get_jwks_fallback_on_error` | Graceful fallback | Uses expired cache |
| `test_verify_jwt_success` | JWT validation | Payload returned |
| `test_verify_jwt_key_not_found` | Missing key | 401 error |
| `test_verify_jwt_invalid_signature` | Bad signature | 401 error |
| `test_verify_opaque_token_success` | Opaque validation | Userinfo returned |
| `test_verify_opaque_token_expired` | Expired token | 401 error |
| `test_current_user_extraction` | Claim extraction | All fields populated |
| `test_current_user_dev_mode` | Dev bypass | Returns dev user |
| `test_current_user_no_credentials` | Missing auth | 401 error |
| `test_current_user_jwt_path` | JWT flow | Via verify_jwt |
| `test_current_user_opaque_fallback` | Opaque fallback | Via userinfo |

### 6. Content Loader Tests (`test_content_loader.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_load_lesson_cache_hit` | Cache hit | Returns cached |
| `test_load_lesson_cache_miss` | Cache miss | Fetches from GitHub |
| `test_load_lesson_github_success` | GitHub fetch | Content returned |
| `test_load_lesson_github_auth_header` | Auth header | Bearer token sent |
| `test_load_lesson_404` | Missing lesson | Graceful error |
| `test_load_lesson_rate_limit` | 403 handling | Error message |
| `test_extract_title_from_frontmatter` | YAML parsing | Title extracted |
| `test_extract_title_from_heading` | Fallback | # heading used |
| `test_extract_title_default` | No title | Returns "Lesson" |
| `test_cache_ttl` | 24hr TTL | Correct expiry |

### 7. PostgreSQL Store Tests (`test_postgres_store.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_default_pool_settings` | Pool config | 20+10 pool |
| `test_validates_database_url_prefix` | URL validation | postgresql:// required |
| `test_converts_postgresql_to_asyncpg` | Driver prefix | +asyncpg added |
| `test_fixes_ssl_parameters` | SSL fix | sslmode → ssl |
| `test_schema_name_default` | Schema name | study_mode_chat |
| `test_context_creation` | Context fields | All fields work |
| `test_store_initialization` | Store init | Engine attached |
| `test_store_creates_engine_from_config` | Engine creation | Pool settings used |
| `test_get_table_name` | Table naming | schema.table format |
| `test_close_disposes_engine` | Cleanup | dispose() called |
| `test_thread_data_serialization` | Thread JSON | Serializes correctly |
| `test_item_data_model_exists` | Item model | Model defined |
| `test_pool_pre_ping_enabled` | **T019**: Pre-ping | Validates connections |
| `test_connection_timeout_configured` | **T020**: Timeout | 30s timeout |
| `test_statement_timeout_configured` | Query timeout | Prevents hangs |
| `test_warm_connection_pool` | Pool warming | Reduces cold start |

### 8. ChatKit Router Tests (`test_chatkit.py`)

| Test | Purpose | Success Criteria |
|------|---------|------------------|
| `test_create_teach_agent` | Teach mode | Socratic prompt |
| `test_create_ask_agent` | Ask mode | Direct answer prompt |
| `test_content_truncation_*` | Long content | Truncated safely |
| `test_prompt_templates` | Template structure | Required elements |
| `test_session_request_*` | Request model | Defaults + values |
| `test_context_includes_metadata` | Context propagation | User name flows |
| `test_server_initialization` | Server setup | Store attached |
| `test_user_context_propagation` | User info flow | Name in metadata |
| `test_rate_limit_integration` | Rate limiting | Decorators applied |

---

## Test Environment Setup

### Environment Variables (conftest.py)

```python
os.environ["DEV_MODE"] = "true"
os.environ["DATABASE_URL"] = ""
os.environ["REDIS_URL"] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://test.com"
```

### Fixtures

| Fixture | Purpose |
|---------|---------|
| `mock_redis` | AsyncMock Redis client |
| `mock_httpx_client` | AsyncMock HTTP client |
| `sample_lesson_content` | Test lesson data |
| `sample_jwt_payload` | Test JWT claims |
| `sample_jwks` | Test JWKS response |

---

## Running Tests

```bash
# All tests
cd apps/study-mode-api
uv run pytest

# With coverage
uv run pytest --cov=src/study_mode_api --cov-report=html

# Specific module
uv run pytest tests/test_auth.py -v

# Specific test
uv run pytest tests/test_rate_limit.py::TestRateLimiter::test_check_rate_limit_exceeds_limit -v
```

---

## Success Criteria Mapping

| Criteria | Test | Target |
|----------|------|--------|
| **SC-002** | `test_cache_hit_returns_cached_value` | <50ms cached response |
| **SC-004** | `test_decorator_raises_429_when_exceeded` | 429 after 20 req/min |
| **T019** | `test_pool_pre_ping_enabled` | Connection validation |
| **T020** | `test_connection_timeout_configured` | 30s timeout |
| **T022** | Rate limit decorators | All endpoints limited |
| **T023** | `test_decorator_sets_headers` | X-RateLimit-* headers |
| **T024** | `test_check_rate_limit_fail_open` | Redis down → allow |

---

## Integration Test Scenarios

### Scenario 1: Full Auth Flow
1. Fetch JWKS from SSO
2. Verify JWT signature
3. Extract user claims
4. Create RequestContext
5. Execute ChatKit request

### Scenario 2: Caching Flow
1. Request lesson content (cache miss)
2. Fetch from GitHub
3. Store in Redis with TTL
4. Request same content (cache hit)
5. Verify <50ms response

### Scenario 3: Rate Limiting Flow
1. Make 19 requests (all succeed)
2. Make 20th request (succeeds)
3. Make 21st request (429 error)
4. Wait for window reset
5. Request succeeds again

### Scenario 4: Graceful Degradation
1. Start with Redis unavailable
2. Requests succeed (no caching)
3. Rate limiting fails open
4. App continues functioning

---

## Production Verification Checklist

- [ ] Health endpoint returns 200
- [ ] Ready endpoint checks DB + Redis
- [ ] Auth works with real SSO tokens
- [ ] Rate limiting enforces 20/min
- [ ] Cached content returns <50ms
- [ ] PostgreSQL pool handles load
- [ ] Logs show request tracing
- [ ] Errors return proper status codes
