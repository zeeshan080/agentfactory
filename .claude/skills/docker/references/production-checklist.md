# Production Validation Checklist

## Pre-Generation Validation

Before generating any files, agent MUST verify:

### 1. Project Structure Analysis
```
□ Identified entrypoint (main.py, server.js, etc.)
□ Detected framework and version
□ Found dependency files (requirements.txt, package.json, etc.)
□ Scanned for native dependencies requiring build tools
□ Identified static assets location
□ Found existing Docker files (analyze, don't blindly overwrite)
```

### 2. Environment Analysis
```
□ Scanned all .env* files
□ Classified each variable (SECRET/BUILD_ARG/RUNTIME)
□ Flagged any secrets that would be baked into image
□ Verified .dockerignore excludes .env files
□ Generated .env.example with safe placeholders
```

### 3. Security Pre-Check
```
□ No hardcoded credentials in source code
□ No private keys in repository
□ Base image is from trusted source
□ No `latest` tag used (pin versions)
```

---

## Post-Generation Validation

After generating Dockerfile, agent MUST run:

### 1. Build Verification
```bash
# Must succeed before delivering
docker build --target dev -t app:dev .
docker build --target production -t app:prod .
```

### 2. Security Scan
```bash
# Scan for vulnerabilities
docker scout cves app:prod

# Or with trivy
trivy image app:prod
```

### 3. Runtime Test
```bash
# Start container
docker run -d --name test -p 8000:8000 app:dev

# Wait for startup
sleep 5

# Health check
curl -f http://localhost:8000/health/live || exit 1
curl -f http://localhost:8000/health/ready || exit 1

# Cleanup
docker stop test && docker rm test
```

### 4. Image Analysis
```bash
# Check image size
docker images app:prod --format "{{.Size}}"

# Check layers
docker history app:prod

# Verify non-root user
docker run --rm app:prod whoami
# Should NOT be "root"
```

---

## Security Checklist

### Dockerfile Security
```
□ Non-root USER in production stage
□ No secrets in ENV, ARG, or COPY
□ Multi-stage build (build tools not in production)
□ Pinned base image versions (no :latest)
□ HEALTHCHECK instruction defined
□ Minimal packages installed
□ No unnecessary ports exposed
□ Read-only filesystem where possible
```

### Runtime Security
```
□ Container runs as non-root
□ No privileged mode
□ Dropped capabilities (--cap-drop=ALL)
□ Read-only root filesystem (--read-only)
□ No new privileges (--security-opt=no-new-privileges)
□ Resource limits set (--memory, --cpus)
□ Secrets mounted, not in environment
```

### Supply Chain Security
```
□ Base images from trusted registries
□ Dependencies pinned to exact versions
□ Lock files committed (uv.lock, pnpm-lock.yaml)
□ SBOM generated (docker sbom app:prod)
□ Image signed (cosign, notation)
```

---

## Production Compose Template

```yaml
services:
  app:
    image: app:prod
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 128M
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    tmpfs:
      - /tmp
    volumes:
      - ./secrets:/run/secrets:ro
```

---

## Failure Modes & Recovery

### Build Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `No such file: requirements.txt` | Wrong path in COPY | Check actual file location |
| `pip install failed` | Missing build deps | Add libpq-dev, etc. to builder |
| `Permission denied` | File ownership | Use `--chown=app:app` in COPY |
| `OCI runtime create failed` | Bad CMD | Verify entrypoint path |

### Runtime Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` | Wrong PYTHONPATH or import | Check app structure matches CMD |
| `Connection refused` | App not binding to 0.0.0.0 | Add --host 0.0.0.0 |
| `Permission denied` | Non-root can't write | Use tmpfs or proper volumes |
| Health check failing | Wrong endpoint or slow startup | Increase start_period |

---

## Agent Delivery Checklist

Before presenting to user:

```
□ All files generated (Dockerfile, .dockerignore, compose.yaml)
□ Build tested (--target dev and --target production)
□ Health endpoints verified
□ No secrets in image (verified with docker history)
□ Non-root user confirmed
□ Image size reported
□ Security scan results included (or scan command provided)
□ Rollback instructions provided (if replacing existing Dockerfile)
```
