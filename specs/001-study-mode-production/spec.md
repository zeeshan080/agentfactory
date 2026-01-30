# Feature Specification: Study Mode API Production Hardening

**Feature Branch**: `001-study-mode-production`
**Created**: 2026-01-29
**Status**: Draft
**Input**: Production-harden study-mode-api with ChatKit integration: Copy production patterns from TaskFlow (chatkit_store, auth, config, database) and staging-merge microservices (redis_cache, rate_limit, red_lock). Convert to uv project with pyproject.toml, create Dockerfile, add GitHub content fetching with Redis cache, implement JWT/JWKS auth, add rate limiting, fix CORS, add health checks. Target: 50,000+ concurrent users.

## Context

The study-mode-api provides a Socratic teaching AI for the AgentFactory book. The current implementation has critical production gaps that will cause failures under load (50,000+ users). This specification defines the production hardening required by adopting proven patterns from two reference implementations:

1. **TaskFlow API** - ChatKit store, authentication, database patterns
2. **Staging-Merge Microservices** - Redis caching, rate limiting, distributed locking

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Lesson Content Access with Caching (Priority: P1)

A student opens a lesson page and clicks "Teach Me" to start a Socratic tutoring session. The system fetches the lesson content from GitHub and caches it in Redis, so subsequent requests are fast and don't hit rate limits.

**Why this priority**: Core functionality - without reliable content loading, the entire teaching feature fails. GitHub rate limits (60/hr unauthenticated) would be exhausted in minutes with 50K users.

**Independent Test**: Can be fully tested by requesting lesson content repeatedly and verifying cache hits. Delivers immediate value: fast content loading.

**Acceptance Scenarios**:

1. **Given** a cached lesson exists, **When** user requests that lesson, **Then** content is served from Redis cache within 50ms
2. **Given** lesson is not cached, **When** user requests that lesson, **Then** content is fetched from GitHub, stored in Redis with 24hr TTL, and returned
3. **Given** GitHub is unavailable, **When** user requests a cached lesson, **Then** cached content is still served
4. **Given** GitHub is unavailable and no cache exists, **When** user requests that lesson, **Then** user sees a graceful error message

---

### User Story 2 - Connection Pool Resilience (Priority: P1)

Multiple concurrent users access the ChatKit API simultaneously. The system handles 50,000+ concurrent users without connection exhaustion, stale connections, or timeouts.

**Why this priority**: Without proper connection pooling, the system will crash under load. This is a blocking production requirement.

**Independent Test**: Can be tested with load testing tools simulating concurrent connections. Delivers production stability.

**Acceptance Scenarios**:

1. **Given** 1000 concurrent requests, **When** all hit the ChatKit endpoint, **Then** all receive responses without connection errors
2. **Given** a database connection becomes stale, **When** a request uses that connection, **Then** the system automatically reconnects
3. **Given** pool is exhausted, **When** new requests arrive, **Then** they queue with timeout rather than immediate failure

---

### User Story 3 - Rate Limiting Protection (Priority: P1)

The system protects itself from abuse by limiting requests per user. Rate limits are enforced atomically via Redis to work across multiple container replicas.

**Why this priority**: Without rate limiting, a single user or bot can exhaust resources for all users. Critical for production stability.

**Independent Test**: Can be tested by sending burst requests and verifying 429 responses after limit. Delivers abuse protection.

**Acceptance Scenarios**:

1. **Given** a user has made 20 requests in 1 minute, **When** they make request 21, **Then** they receive 429 with retry-after header
2. **Given** rate limit headers are requested, **When** any response is returned, **Then** rate limit headers are included
3. **Given** Redis is unavailable, **When** rate limit check fails, **Then** system fails open (allows request) but logs error

---

### User Story 4 - Health Checks for Container Orchestration (Priority: P2)

Container orchestrators need to know if the service is alive and ready to accept traffic. The system provides liveness and readiness endpoints.

**Why this priority**: Required for production deployment in containerized environments. Without health checks, failed containers won't be replaced.

**Independent Test**: Can be tested by calling /health and /health/ready endpoints. Delivers container orchestration compatibility.

**Acceptance Scenarios**:

1. **Given** the server is running, **When** /health is called, **Then** 200 OK is returned immediately
2. **Given** the database is connected, **When** /health/ready is called, **Then** 200 OK with database status is returned
3. **Given** the database is unreachable, **When** /health/ready is called, **Then** status indicates unhealthy with error details

---

### User Story 5 - JWT/JWKS Authentication (Priority: P2)

Users authenticate via SSO. The API validates JWT tokens using JWKS public keys fetched from the SSO provider and cached for 1 hour.

**Why this priority**: Security requirement but can be implemented after core functionality. Currently bypassed in development mode.

**Independent Test**: Can be tested by sending valid/invalid JWT tokens and verifying access. Delivers security.

**Acceptance Scenarios**:

1. **Given** a valid JWT token, **When** request is made with Authorization header, **Then** request proceeds with user context
2. **Given** an expired JWT token, **When** request is made, **Then** 401 Unauthorized is returned
3. **Given** JWKS keys are cached, **When** a new request arrives, **Then** cached keys are used (no SSO call per request)
4. **Given** SSO is unavailable, **When** cached JWKS exists, **Then** expired cache is used as fallback

---

### User Story 6 - CORS Security (Priority: P2)

The API only accepts requests from allowed origins (the learn-app frontend). Wildcard CORS is removed.

**Why this priority**: Security requirement to prevent cross-site attacks. Current wildcard is a critical vulnerability.

**Independent Test**: Can be tested by sending requests with different Origin headers. Delivers CSRF protection.

**Acceptance Scenarios**:

1. **Given** request from allowed origin, **When** preflight or request is made, **Then** CORS headers allow the request
2. **Given** request from disallowed origin, **When** preflight is made, **Then** CORS headers reject the request

---

### User Story 7 - Container Deployment (Priority: P3)

The API can be built as a container using a multi-stage build with uv for dependency management.

**Why this priority**: Deployment infrastructure. Can be done after functionality is production-ready.

**Independent Test**: Can be tested by building the image and running it. Delivers deployability.

**Acceptance Scenarios**:

1. **Given** the Dockerfile, **When** container build is run, **Then** image builds successfully with all dependencies
2. **Given** the built image, **When** container runs with required env vars, **Then** API starts and serves requests
3. **Given** the container is running, **When** health check is executed, **Then** container reports healthy

---

### Edge Cases

- What happens when Redis connection fails during startup? → Log error, allow startup without caching (degraded mode)
- What happens when GitHub token is missing? → Fall back to unauthenticated access with warning about rate limits
- What happens when database pool is exhausted? → Queue requests with 30s timeout, return 503 if timeout exceeded
- What happens when a user ID collision occurs? → Use crypto-secure UUIDs to prevent collisions
- What happens when lesson content is corrupted in cache? → Cache includes TTL, corrupted entries expire naturally
- How does system handle concurrent schema initialization? → Check if schema exists before creating (idempotent)

## Requirements _(mandatory)_

### Functional Requirements

#### Project Structure

- **FR-001**: System MUST use uv for dependency management with pyproject.toml
- **FR-002**: System MUST follow src/study_mode_api/ package structure

#### Database & Connection Pooling

- **FR-003**: System MUST use async session factory for session management
- **FR-004**: System MUST configure connection pool with appropriate size for 50K users
- **FR-005**: System MUST enable connection health checks before use
- **FR-006**: System MUST set command timeout and statement timeout for all connections
- **FR-007**: System MUST warm connection pool on startup
- **FR-008**: System MUST use typed wrappers for serialization
- **FR-009**: System MUST implement proper error handling with rollback on failure

#### Redis & Caching

- **FR-010**: System MUST use async Redis with retry and exponential backoff
- **FR-011**: System MUST implement cache decorator for automatic caching
- **FR-012**: System MUST cache lesson content with 24-hour TTL
- **FR-013**: System MUST manage Redis connection lifecycle in lifespan handler

#### Content Loading

- **FR-014**: System MUST fetch lesson content from GitHub raw URLs
- **FR-015**: System MUST use authenticated GitHub requests to avoid rate limits
- **FR-016**: System MUST check Redis cache before fetching from GitHub
- **FR-017**: System MUST handle both .md and .mdx file extensions

#### Rate Limiting

- **FR-018**: System MUST implement rate limiting using atomic Redis operations
- **FR-019**: System MUST include rate limit headers in responses
- **FR-020**: System MUST configure requests per minute per user limit
- **FR-021**: System MUST fail open if Redis is unavailable

#### Authentication

- **FR-022**: System MUST validate JWT tokens using JWKS public keys
- **FR-023**: System MUST cache JWKS keys with appropriate TTL
- **FR-024**: System MUST support opaque token fallback via userinfo endpoint
- **FR-025**: System MUST extract user identity from validated JWT claims
- **FR-026**: System MUST support development mode bypass for local testing

#### CORS

- **FR-027**: System MUST configure allowed origins from environment variable
- **FR-028**: System MUST NOT use wildcard origins in production

#### Health Checks

- **FR-029**: System MUST provide liveness endpoint
- **FR-030**: System MUST provide readiness endpoint with database connectivity check

#### Schema & Data Integrity

- **FR-031**: System MUST check if schema exists before creating (idempotent)
- **FR-032**: System MUST use composite unique constraints for user isolation
- **FR-033**: System MUST support organization context for multi-tenancy

#### Container

- **FR-034**: System MUST include multi-stage Dockerfile with uv
- **FR-035**: System MUST run as non-root user in container
- **FR-036**: System MUST include container health check

### Key Entities

- **Lesson Content**: Markdown content fetched from GitHub, cached in Redis with path as key
- **Thread**: ChatKit conversation thread with user isolation, stored in database
- **Thread Item**: Individual message in a thread (user or assistant)
- **Request Context**: User identity and metadata passed through all store operations
- **Rate Limit Entry**: Per-user request counter with TTL, stored in Redis

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: System handles 1000 concurrent users without connection errors or timeouts
- **SC-002**: Cached lesson content is served within 50ms (p95)
- **SC-003**: First request for uncached lesson completes within 2 seconds
- **SC-004**: Rate limit enforcement prevents more than configured requests per minute per user
- **SC-005**: Health check endpoints respond within 100ms
- **SC-006**: Container image size is under 500MB
- **SC-007**: Cold start time (container ready to serve) is under 10 seconds
- **SC-008**: Zero security vulnerabilities from wildcard CORS or unauthenticated access in production mode

## Assumptions

1. SSO Provider uses JWKS endpoint for public key distribution
2. GitHub repository contains lesson content in apps/learn-app/docs/
3. Redis is available via Upstash or similar managed service
4. Database is PostgreSQL with async driver support
5. All secrets provided via environment variables
6. Frontend origin is configured via environment variable

## Dependencies

- TaskFlow API codebase (patterns for ChatKit store, auth, config)
- Staging-Merge Microservices codebase (patterns for Redis caching, rate limiting)
- GitHub API for fetching lesson content
- Redis for caching and rate limiting
- SSO Provider for authentication
