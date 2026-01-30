# Django Deployment Reference

## Production Server

Django's runserver is for development only. Use gunicorn in production:

```bash
# Development
python manage.py runserver 0.0.0.0:8000

# Production
gunicorn -w 4 -b 0.0.0.0:8000 project.wsgi:application
```

## Dockerfile CMD

```dockerfile
# Development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "project.wsgi:application"]
```

## Health Check Endpoints

```python
"""
Django Health Check Views

Add to urls.py:
    path('health/', include('health.urls')),
"""

# health/views.py
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache


def liveness(request):
    """Liveness: Is process alive?"""
    return JsonResponse({'status': 'alive'})


def readiness(request):
    """Readiness: Can serve traffic?"""
    checks = {}

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['database'] = True
    except Exception:
        checks['database'] = False

    # Check cache/redis
    try:
        cache.set('health_check', 'ok', 1)
        checks['cache'] = cache.get('health_check') == 'ok'
    except Exception:
        checks['cache'] = False

    if not all(checks.values()):
        return JsonResponse({'status': 'not_ready', 'checks': checks}, status=503)

    return JsonResponse({'status': 'ready', 'checks': checks})


def startup(request):
    """Startup: Initialization complete?"""
    return JsonResponse({'status': 'started'})


# health/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('live', views.liveness, name='liveness'),
    path('ready', views.readiness, name='readiness'),
    path('startup', views.startup, name='startup'),
]
```

## Settings for Production

```python
# settings.py
import os

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

STATIC_ROOT = '/app/staticfiles'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

## Startup Commands

Run migrations and collect static before starting:

```dockerfile
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn -w 4 -b 0.0.0.0:8000 project.wsgi:application"]
```

Or use an entrypoint script:

```bash
#!/bin/bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn -w 4 -b 0.0.0.0:8000 project.wsgi:application
```

## Graceful Shutdown

Gunicorn handles SIGTERM gracefully:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 --timeout 30 --graceful-timeout 30 project.wsgi:application
```
