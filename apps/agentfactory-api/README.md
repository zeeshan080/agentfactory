# AgentFactory API

AI-powered lesson personalization service using OpenAI Agents SDK.

## Features

- **Generate Once, Read Many** - Content deduplicated globally
- **Streaming responses** - Real-time content display
- **Hybrid storage** - PostgreSQL pointers + Cloudflare R2 content

## Quick Start (Local Development)

```bash
# Install dependencies
uv sync

# Start server
uv run python -m agentfactory_api.main
```

Server runs at `http://localhost:8080`

## Environment Variables

See `.env.example` for all options.

## Deployment to Google Cloud Run

### Prerequisites

1. [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed
2. A GCP project with billing enabled
3. Neon PostgreSQL database (or any PostgreSQL)
4. Cloudflare R2 bucket configured

### One-Time Setup

```bash
# Authenticate
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com containerregistry.googleapis.com
```

### Manual Deploy (First Time)

```bash
cd apps/agentfactory-api

# Build and deploy
gcloud run deploy agentfactory-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "AGENTFACTORY_DATABASE_URL=postgresql+asyncpg://user:pass@host/db" \
  --set-env-vars "AGENTFACTORY_R2_ACCOUNT_ID=xxx" \
  --set-env-vars "AGENTFACTORY_R2_ACCESS_KEY_ID=xxx" \
  --set-env-vars "AGENTFACTORY_R2_SECRET_ACCESS_KEY=xxx" \
  --set-env-vars "AGENTFACTORY_R2_BUCKET_NAME=agentfactory-content" \
  --set-env-vars "AGENTFACTORY_OPENAI_API_KEY=sk-xxx" \
  --set-env-vars "AGENTFACTORY_AUTH_SERVER_URL=https://your-sso.com" \
  --set-env-vars "AGENTFACTORY_CORS_ORIGINS=https://your-frontend.com"
```

### Automatic Deploy (CI/CD)

The `cloudbuild.yaml` configures automatic deployment on push:

```bash
# Set up Cloud Build trigger
gcloud builds triggers create github \
  --repo-name=agentfactory \
  --repo-owner=YOUR_GITHUB_USER \
  --branch-pattern="^main$" \
  --build-config=apps/agentfactory-api/cloudbuild.yaml
```

### Using Secrets (Recommended for Production)

Store sensitive values in Secret Manager instead of environment variables:

```bash
# Create secrets
echo -n "your-api-key" | gcloud secrets create openai-api-key --data-file=-
echo -n "your-db-url" | gcloud secrets create agentfactory-db-url --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Deploy with secrets
gcloud run deploy agentfactory-api \
  --source . \
  --region us-central1 \
  --set-secrets "AGENTFACTORY_OPENAI_API_KEY=openai-api-key:latest"
```

## Health Checks

- `GET /health` - Basic health check
- `GET /health/detailed` - Component-level status

## API Endpoints

- `POST /api/personalize` - Generate personalized content
- `GET /api/preferences` - Get user preferences
- `POST /api/preferences` - Update user preferences
