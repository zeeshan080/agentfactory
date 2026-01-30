# Environment Variable Analysis

## Files to Scan
- `.env`, `.env.example`, `.env.local`, `.env.development`, `.env.production`
- `docker-compose*.yml`, `compose*.yaml` (environment sections)
- Source code (os.environ, process.env usage)

## Classification

| Category | Pattern | Action |
|----------|---------|--------|
| **SECRET** | `*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`, `*_CREDENTIAL`, `DATABASE_URL`, `REDIS_URL` (with password) | **NEVER bake** - use Docker secrets or runtime env |
| **BUILD_ARG** | `NEXT_PUBLIC_*`, `VITE_*`, `REACT_APP_*` | Pass as `--build-arg`, baked at build time |
| **RUNTIME** | `PORT`, `HOST`, `NODE_ENV`, `LOG_LEVEL`, `DEBUG` | Set in compose.yaml or K8s ConfigMap |
| **UNSAFE** | Anything with `admin`, `root`, `master` in name | **Flag for review** |

## Detection Patterns

```python
SECRET_PATTERNS = [
    r".*_(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|API_KEY)$",
    r"^(DATABASE_URL|REDIS_URL|MONGO_URI|AWS_.*|GCP_.*|AZURE_.*)$",
    r".*_PRIVATE_.*",
    r"^(JWT_SECRET|SESSION_SECRET|ENCRYPTION_KEY)$",
]

BUILD_ARG_PATTERNS = [
    r"^NEXT_PUBLIC_.*",
    r"^VITE_.*",
    r"^REACT_APP_.*",
    r"^VUE_APP_.*",
]
```

## Agent Actions

### 1. Scan .env Files
```bash
# Find all env files
find . -name ".env*" -o -name "*.env"
```

### 2. Classify Each Variable
```
DATABASE_URL=postgresql://user:password@host:5432/db
→ Category: SECRET (contains password)
→ Action: Remove from .env, use Docker secrets

NEXT_PUBLIC_API_URL=https://api.example.com
→ Category: BUILD_ARG
→ Action: Pass via --build-arg at build time

PORT=3000
→ Category: RUNTIME
→ Action: Set in compose.yaml
```

### 3. Generate Recommendations

**If secrets found in .env:**
```
⚠️ SECURITY WARNING: Found secrets in .env files

These should NOT be in your Docker image:
- DATABASE_URL (contains credentials)
- JWT_SECRET (authentication key)
- AWS_SECRET_ACCESS_KEY (cloud credentials)

Recommendations:
1. Remove from .env, add to .env.example as placeholders
2. Use Docker secrets: docker secret create db_url ./secrets/db_url.txt
3. Or mount at runtime: -v ./secrets:/run/secrets:ro
4. For K8s: Use sealed-secrets or external-secrets operator
```

**If build args needed:**
```
📦 BUILD-TIME VARIABLES DETECTED

These are baked into the image at build time:
- NEXT_PUBLIC_API_URL
- NEXT_PUBLIC_ANALYTICS_ID

Generated build command:
docker build \
  --build-arg NEXT_PUBLIC_API_URL=https://api.prod.example.com \
  --build-arg NEXT_PUBLIC_ANALYTICS_ID=UA-XXXXX \
  -t app:prod .
```

## Dockerfile Generation

```dockerfile
# SAFE: Runtime env vars (not secrets, just defaults)
ENV NODE_ENV=production \
    PORT=3000

# SAFE: Build args for public client-side vars
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# NEVER DO THIS:
# ENV DATABASE_URL=postgresql://... ← SECRET LEAKED
# COPY .env /app/.env ← SECRETS IN IMAGE
```

## Compose.yaml Generation

```yaml
services:
  app:
    environment:
      # Runtime config (not secrets)
      - NODE_ENV=production
      - PORT=3000

    # Secrets from Docker secrets (swarm) or external file
    secrets:
      - db_password
      - jwt_secret

    # Or mount secrets directory
    volumes:
      - ./secrets:/run/secrets:ro

secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
```

## Validation Checklist

Before generating Dockerfile, verify:

- [ ] No secrets in Dockerfile ENV or ARG
- [ ] No `.env` COPY in Dockerfile
- [ ] No secrets in docker-compose environment section
- [ ] .dockerignore excludes `.env*` files
- [ ] Secrets strategy documented (Docker secrets, mounted files, or external vault)
- [ ] .env.example exists with placeholder values
