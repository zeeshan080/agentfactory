# Next.js Docker Reference

## Standalone Output

Next.js standalone mode creates a minimal production build:

```js
// next.config.js
module.exports = {
  output: 'standalone',
}
```

Output structure:
```
.next/
├── standalone/     # Self-contained server
│   ├── server.js   # Entry point
│   └── node_modules/ # Minimal deps only
├── static/         # Static assets (copy separately)
└── ...
```

## Dockerfile Pattern

```dockerfile
# Build stage
FROM node:22-slim AS builder
# ... build commands
RUN pnpm build

# Production stage
FROM dhi.io/node:22 AS production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
CMD ["node", "server.js"]
```

## Environment Variables

Next.js has two types:

| Type | Available | Baked at |
|------|-----------|----------|
| `NEXT_PUBLIC_*` | Client + Server | Build time |
| Regular | Server only | Runtime |

**Pattern for build-time vars:**
```dockerfile
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build
```

**Pattern for runtime vars:**
```dockerfile
# No ARG needed - just set at runtime
ENV DATABASE_URL=${DATABASE_URL}
```

## Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/api/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"
```

Or create `/pages/api/health.ts`:
```typescript
export default function handler(req, res) {
  res.status(200).json({ status: 'healthy' });
}
```

## Graceful Shutdown

Next.js standalone handles SIGTERM, but add explicit handling:

```typescript
// Custom server (if needed)
const server = app.listen(port);

process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
});
```

## Static Assets

The `.next/static` folder must be copied separately:

```dockerfile
COPY --from=builder /app/.next/static ./.next/static
```

## ISR (Incremental Static Regeneration)

For ISR to work, the `.next/cache` folder needs persistence:

```yaml
# compose.yaml
volumes:
  - nextjs_cache:/app/.next/cache

# Or in Kubernetes, use a PVC
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Missing static files | Ensure `public/` and `.next/static` are copied |
| NEXT_PUBLIC_ not working | Must be set at build time, not runtime |
| Large image size | Use standalone output + multi-stage |
| Sharp (images) issues | Install `sharp` in deps stage, copy to runner |
