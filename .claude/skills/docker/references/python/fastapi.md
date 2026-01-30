# FastAPI Deployment Reference

Source: https://fastapi.tiangolo.com/deployment/docker/

## Docker CMD

```dockerfile
# Development
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0"]

# Production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--workers", "4"]

# With graceful shutdown
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--timeout-graceful-shutdown", "30"]

# Behind proxy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--proxy-headers"]
```

## Lifespan Events (Modern Pattern)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Before first request
    app.state.db_pool = await create_connection_pool()
    yield
    # SHUTDOWN: After last request
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)
```

## Health Check Endpoints

```python
from fastapi import FastAPI, Response

app = FastAPI()

# Liveness: Is the process alive?
@app.get("/health/live")
async def liveness():
    return {"status": "alive"}

# Readiness: Can we accept traffic?
@app.get("/health/ready")
async def readiness():
    try:
        await check_database()
        await check_redis()
        return {"status": "ready"}
    except Exception:
        return Response(status_code=503)

# Startup: One-time initialization complete?
@app.get("/health/startup")
async def startup_check():
    if app.state.initialized:
        return {"status": "started"}
    return Response(status_code=503)
```

## Graceful Shutdown Pattern

```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown - wait for in-flight requests
    shutdown_event.set()
    await asyncio.sleep(5)

app = FastAPI(lifespan=lifespan)

@app.get("/long-task")
async def long_task():
    if shutdown_event.is_set():
        return {"status": "shutting_down"}
    return {"result": "done"}
```

## Resource Management Examples

### Database Pool
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)
    yield
    await app.state.pool.close()
```

### Redis Connection
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await aioredis.from_url(REDIS_URL)
    yield
    await app.state.redis.close()
```

### ML Model Loading
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = load_model("model.pkl")
    yield
    del app.state.model
```

## Deprecated Event Handlers

```python
# OLD - Don't use with lifespan parameter
@app.on_event("startup")
async def startup():
    pass

@app.on_event("shutdown")
async def shutdown():
    pass
```
