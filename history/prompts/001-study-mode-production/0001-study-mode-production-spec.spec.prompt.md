---
id: "0001"
title: study-mode-production-spec
stage: spec
date: 2026-01-29
surface: claude-code
model: claude-opus-4-5-20250514
feature: 001-study-mode-production
branch: 001-study-mode-production
user: mjunaidca
command: /sp.specify
labels: [production-hardening, chatkit, redis, authentication]
links:
  spec: specs/001-study-mode-production/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/001-study-mode-production/spec.md
  - specs/001-study-mode-production/checklists/requirements.md
tests:
  - null
---

## Prompt

Production-harden study-mode-api with ChatKit integration: Copy production patterns from TaskFlow (chatkit_store, auth, config, database) and staging-merge microservices (redis_cache, rate_limit, red_lock). Convert to uv project with pyproject.toml, create Dockerfile, add GitHub content fetching with Redis cache, implement JWT/JWKS auth, add rate limiting, fix CORS, add health checks. Target: 50,000+ concurrent users.

## Response snapshot

Created comprehensive specification for study-mode-api production hardening with:

- 7 prioritized user stories (P1: content caching, connection pooling, rate limiting; P2: health checks, auth, CORS; P3: container)
- 36 functional requirements across 9 categories
- 8 measurable success criteria
- 6 edge cases documented
- Dependencies on TaskFlow and Staging-Merge patterns identified

## Outcome

- ✅ Impact: Specification ready for planning phase
- 🧪 Tests: N/A (spec phase)
- 📁 Files: 2 files created (spec.md, requirements.md checklist)
- 🔁 Next prompts: /sp.plan, /sp.tasks
- 🧠 Reflection: Deep analysis of reference codebases (TaskFlow, staging-merge) informed comprehensive requirements

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Checklist PASS (all items checked)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
