# Flask Deployment Reference

## Production Server

Flask's built-in server is for development only. Use gunicorn in production:

```bash
# Development
flask run --debug --host=0.0.0.0 --port=8000

# Production
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Dockerfile CMD

```dockerfile
# Development
CMD ["flask", "run", "--debug", "--host=0.0.0.0", "--port=8000"]

# Production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```

## Health Check Endpoints

```python
"""
Flask Health Check Blueprint

Usage:
    from health import health_bp
    app.register_blueprint(health_bp, url_prefix='/health')
"""

from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

class HealthState:
    initialized: bool = False
    db_healthy: bool = False
    redis_healthy: bool = False

state = HealthState()


@health_bp.route('/live')
def liveness():
    """Liveness: Is process alive?"""
    return jsonify(status='alive')


@health_bp.route('/ready')
def readiness():
    """Readiness: Can serve traffic?"""
    checks = {
        'database': state.db_healthy,
        'redis': state.redis_healthy,
    }

    if not all(checks.values()):
        return jsonify(status='not_ready', checks=checks), 503

    return jsonify(status='ready', checks=checks)


@health_bp.route('/startup')
def startup():
    """Startup: Initialization complete?"""
    if not state.initialized:
        return jsonify(status='initializing'), 503
    return jsonify(status='started')
```

## Application Factory Pattern

```python
from flask import Flask

def create_app():
    app = Flask(__name__)

    from health import health_bp
    app.register_blueprint(health_bp, url_prefix='/health')

    with app.app_context():
        init_database()
        init_redis()
        mark_initialized()

    return app
```

## Graceful Shutdown

Gunicorn handles SIGTERM gracefully. Configure timeout:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 30 --graceful-timeout 30 app:app
```

## Environment Variables

```python
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    REDIS_URL = os.environ.get('REDIS_URL')
```
