# Docker Hardened Images (DHI) Reference

Source: https://docs.docker.com/dhi/

**DHI is OPTIONAL** - Templates use standard `python:X-slim` / `node:X-slim` by default.
DHI provides 95% fewer CVEs but requires Docker Hub authentication.

## When to Use DHI

| Situation | Use DHI? |
|-----------|----------|
| Quick prototyping | No - use default slim images |
| Production with compliance (SOC2, HIPAA) | Yes |
| Enterprise/security-sensitive | Yes |
| Open source / public projects | No - avoid auth friction |

## Authentication & Registry

```bash
# Required before pulling DHI images
docker login dhi.io
```

Credentials: Your Docker ID (same as Docker Hub, free account works)

## Pull Commands

```bash
# Python
docker pull dhi.io/python:3.13

# Node.js
docker pull dhi.io/node:22
```

## Available Tags

### Python
- `dhi.io/python:3.13` - Latest 3.13
- `dhi.io/python:3.12` - Stable 3.12
- `dhi.io/python:3.11` - LTS-like stability
- `dhi.io/python:3.13-alpine3.21` - Alpine-based
- `dhi.io/python:3.13-fips` - FIPS-enabled (Enterprise)
- `dhi.io/python:3.13-dev` - Includes shell for debugging

### Node.js
- `dhi.io/node:22` - Latest LTS
- `dhi.io/node:20` - Previous LTS
- `dhi.io/node:22-alpine` - Alpine-based
- `dhi.io/node:22-fips` - FIPS-enabled (Enterprise)

## Security Benefits

| Metric | Standard | DHI | Reduction |
|--------|----------|-----|-----------|
| CVEs | 150+ | 0-3 | ~95% |
| Size | 400+ MB | 35-50 MB | 91% |
| Packages | 600+ | 80 | 87% |

## Key Characteristics

- **Distroless runtime**: No shell, no package manager
- **Non-root by default**: Runs as unprivileged user
- **VEX support**: Vulnerability Exploitability eXchange standard
- **Signed attestations**: Verify with Docker Scout or Cosign

## Compliance Options

| Requirement | Image Tag |
|-------------|-----------|
| SOC2 | Any DHI (low CVE count) |
| HIPAA/PCI | `*-fips` variants |
| CIS Benchmark | DHI Enterprise |
| Extended Support | DHI ELS (5 year patches) |

## Multi-Stage Pattern

```dockerfile
# Build stage - has tools
FROM python:3.13-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# Production stage - minimal DHI
FROM dhi.io/python:3.13
WORKDIR /app
COPY --from=builder /app/deps /app/deps
COPY ./src /app/src
ENV PYTHONPATH=/app/deps
USER nonroot
CMD ["python", "/app/src/main.py"]
```

## Debugging DHI (No Shell)

Use dev variant for troubleshooting:

```dockerfile
# Development/debugging
FROM dhi.io/python:3.13-dev AS debug
# Has shell access

# Production
FROM dhi.io/python:3.13 AS production
# No shell - secure
```

Build specific target:
```bash
docker build --target debug -t myapp:debug .
docker build --target production -t myapp:prod .
```
