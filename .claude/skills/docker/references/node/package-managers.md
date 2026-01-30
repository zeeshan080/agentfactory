# Package Manager Patterns

## Detection

| File | Package Manager |
|------|-----------------|
| `pnpm-lock.yaml` | pnpm |
| `yarn.lock` | yarn |
| `package-lock.json` | npm |
| `bun.lockb` | bun (use docker-bun skill) |

## pnpm (Recommended)

**Setup:**
```dockerfile
RUN corepack enable && corepack prepare pnpm@latest --activate
```

**Install with cache:**
```dockerfile
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
```

**Production install:**
```dockerfile
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --prod
```

## npm

**Install with cache:**
```dockerfile
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

**Production install:**
```dockerfile
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev
```

## yarn (Classic)

**Install with cache:**
```dockerfile
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile
```

**Production install:**
```dockerfile
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile --production
```

## yarn (Berry/v2+)

**Install with cache:**
```dockerfile
RUN --mount=type=cache,target=/root/.yarn/berry/cache \
    yarn install --immutable
```

## Cache Mount Paths

| Manager | Cache Path |
|---------|------------|
| pnpm | `/root/.local/share/pnpm/store` |
| npm | `/root/.npm` |
| yarn classic | `/usr/local/share/.cache/yarn` |
| yarn berry | `/root/.yarn/berry/cache` |

## Copy Pattern

Only copy lock files first for better caching:

```dockerfile
# Good - only lock file changes trigger reinstall
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# Bad - any file change triggers reinstall
COPY . .
RUN pnpm install
```

## Corepack

Modern Node.js includes corepack for package manager management:

```dockerfile
# Enable corepack (built into Node 16.9+)
RUN corepack enable

# Optionally pin version
RUN corepack prepare pnpm@9.0.0 --activate
```
