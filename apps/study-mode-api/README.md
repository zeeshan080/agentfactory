# OpenAI ChatKit Server for Study Mode

This is the ChatKit-powered backend for Interactive Study Mode. It provides:
- **Streaming responses** (token-by-token)
- **Built-in conversation memory**
- **Server-side session persistence**
- **Two modes**: Teach (explain + check) and Ask (direct answers)

## Quick Start

### 1. Install Dependencies

```bash
cd api/chatkit-server
pip install -r requirements.txt
```

### 2. Set Environment Variables

Copy `.env.example` to `.env` and add your OpenAI API key:

```bash
cp .env.example .env
```

The `.env` file should contain:
```
OPENAI_API_KEY=sk-your-key-here
PORT=8000
```

### 3. Run the Server

```bash
python server.py
```

Or with uvicorn directly:
```bash
uvicorn server:app --reload --port 8000
```

### 4. Test the Endpoint

```bash
curl http://localhost:8000/health
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/chatkit` | POST | Main ChatKit endpoint (handles all ChatKit protocol messages) |

## Modes

### Teach Mode (Explain + Check)
1. Explain one concept (2-3 sentences)
2. Ask ONE checking question
3. Wait for response
4. Acknowledge + explain next concept
5. Repeat

### Ask Mode (Direct Answers)
- Instant answers like Google search
- 1-2 sentences max
- No follow-up questions

## Frontend Integration

The frontend uses `@openai/chatkit-react`:

```tsx
import { ChatKit, useChatKit } from '@openai/chatkit-react';

function StudyMode() {
  const { control } = useChatKit({
    api: {
      url: 'http://localhost:8000/chatkit',
      domainKey: 'study-mode',
      headers: {
        'X-Study-Mode': 'teach', // or 'ask'
        'X-Lesson-Path': '/path/to/lesson',
      },
    },
  });

  return <ChatKit control={control} />;
}
```

## Architecture

```
Frontend (React)                    Backend (Python)
┌─────────────────┐                ┌─────────────────┐
│ ChatKit Widget  │  ──WebSocket── │ ChatKitServer   │
│ @openai/chatkit │                │ (FastAPI)       │
└─────────────────┘                └────────┬────────┘
                                            │
                                   ┌────────▼────────┐
                                   │ OpenAI Agents   │
                                   │ - teach_agent   │
                                   │ - ask_agent     │
                                   └─────────────────┘
```

## Comparison with Previous Approach

| Feature | Old (Node.js) | New (ChatKit) |
|---------|---------------|---------------|
| Streaming | No | Yes (token-by-token) |
| Memory | SessionStorage | Server-side |
| Code | ~500 lines | ~150 lines |
| UI | @chatscope | OpenAI ChatKit |

## Run the Docker image with .env                                        
                                                                          
> After building                                                         
docker build -t study-mode-api:prod .                                    
                                                                          
> Run with .env file                                                     
docker run --env-file .env -p 8000:8000 study-mode-api:prod    