# Production Containerization & Docker Architecture Guide

This document details the multi-container architecture, configuration, operation, and verification of the **Real-Time AI Gym Trainer** production environment orchestrated via Docker Compose.

---

## 1. Container Architecture

```
                    ┌─────────────────────────┐
                    │     Client Browser      │
                    │   (Webcam & Pose HUD)   │
                    └────────────┬────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │ HTTP (3000)                   │ HTTP/WS (8000)
                 ▼                               ▼
       ┌───────────────────┐           ┌───────────────────┐
       │ Next.js Frontend  │           │   FastAPI API     │
       │    (Container)    │           │    + WebSocket    │
       │ (Standalone Node) │           │    (Container)    │
       └───────────────────┘           └─────────┬─────────┘
                                                 │
                               ┌─────────────────┴─────────────────┐
                               │ internal: 5432                    │ internal: 11434
                               ▼                                   ▼
                      ┌──────────────────┐               ┌──────────────────┐
                      │    PostgreSQL    │               │  Ollama AI Engine│
                      │    (Container)   │               │    (Container)   │
                      │ Persistent pgdata│               │ Persistent models│
                      └──────────────────┘               └──────────────────┘
```

### Network Topology & Port Mapping
- **Inter-Service Communication**: Handled across the internal Docker bridge network `ai_gym_net` using container service names (`postgres`, `ollama`). Containers **never** use `localhost` to contact peer containers.
- **Client Ingress**:
  - `3000:3000` — Next.js production frontend (Node 20 Alpine standalone server)
  - `8000:8000` — FastAPI production backend (Uvicorn ASGI runner)
- **Protected Internal Services**:
  - `127.0.0.1:5432:5432` — PostgreSQL 15 Alpine (restricted to loopback on host for dev/inspection, isolated from public interfaces)
  - `127.0.0.1:11434:11434` — Ollama AI provider (optional local LLM container)

---

## 2. Docker Compose Services

| Service | Image / Build Context | Internal Port | Host Port | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`postgres`** | `postgres:15-alpine` | `5432` | `127.0.0.1:5432` | Relational storage for users, profiles, workouts, telemetry, and indexes |
| **`backend`** | Multi-layer Python 3.11 Slim (`docker/backend.Dockerfile`) | `8000` | `0.0.0.0:8000` | FastAPI REST endpoints, real-time WebSocket stream, CV/biomechanics |
| **`frontend`** | Multi-stage Node 20 Alpine (`docker/frontend.Dockerfile`) | `3000` | `0.0.0.0:3000` | Next.js 15 standalone application with client pose HUD |
| **`ollama`** | `ollama/ollama:latest` | `11434` | `127.0.0.1:11434` | Optional local LLM inference server with model persistence |

---

## 3. Production Container Implementation Details

### Backend Container (`docker/backend.Dockerfile`)
- **Base Image**: `python:3.11-slim-bookworm` for minimal surface area and glibc compatibility.
- **System Libraries**: Installs minimal `libgl1`, `libglib2.0-0`, and `curl` for OpenCV headless operations and container health checking.
- **Least-Privilege Security**: Runs as non-root user `appuser:appgroup` (`uid=1000, gid=1000`).
- **Entrypoint Script (`docker/entrypoint.sh`)**:
  - Asynchronously pings PostgreSQL database using async SQLAlchemy engine until connection is established.
  - Automatically executes `alembic upgrade head` before handing off process control.
  - Converts CRLF to LF automatically during image build to prevent line-ending failures across operating systems.
- **Production ASGI Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --lifespan on` (no development hot-reloading).

### Frontend Container (`docker/frontend.Dockerfile`)
- **Multi-Stage Build Pipeline**:
  - **Stage 1 (`deps`)**: Installs dependencies with `npm ci` using Alpine `libc6-compat`.
  - **Stage 2 (`builder`)**: Inlines build arguments (`NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_URL`) and produces an optimized standalone bundle via `npm run build`.
  - **Stage 3 (`runner`)**: Runs as non-root user `nextjs:nodejs` (`uid=1001, gid=1001`). Copies only the standalone bundle (`.next/standalone`), static files (`.next/static`), and public folder, discarding all build tools and dev dependencies.
- **Final Runtime Size**: ~62.4 MB content footprint.

---

## 4. Environment Configuration

All environment configuration is driven by standard environment variables with safe defaults in `.env.example`.

| Variable | Default (Docker Compose) | Description |
| :--- | :--- | :--- |
| `POSTGRES_USER` | `postgres` | Database superuser username |
| `POSTGRES_PASSWORD` | `postgres` | Database superuser password |
| `POSTGRES_DB` | `aigym` | Primary application database |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/aigym` | Async SQLAlchemy database URL |
| `JWT_SECRET_KEY` | `dev-secret-key-change-in-production...` | Cryptographic secret for signing tokens |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Host address of Ollama inference service |
| `OLLAMA_MODEL` | `llama3.2` | Target local LLM model name |
| `OLLAMA_TIMEOUT_SECONDS`| `30.0` | Timeout threshold before fallback triggers |
| `RUN_MIGRATIONS` | `true` | Enables automatic Alembic execution on boot |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed web origins |

---

## 5. Standard Operational Commands

### Building and Starting Containers
```bash
# Build production images
docker compose build

# Start services in detached mode
docker compose up -d

# Check service status and health checks
docker compose ps

# View unified logs
docker compose logs -f

# View backend logs specifically
docker compose logs -f backend
```

### Stopping and Teardown
```bash
# Gracefully stop running containers
docker compose stop

# Restart stopped containers (preserves all data in volumes)
docker compose start

# Stop and remove containers and network (preserves volumes)
docker compose down

# Full teardown including volumes (WARNING: wipes persistent database!)
docker compose down -v
```

---

## 6. Database Migrations

Database migrations are managed via Alembic and run automatically on container startup when `RUN_MIGRATIONS=true`.

To inspect or execute manual migrations against the containerized database:
```bash
# Check current migration revision
docker exec ai_gym_backend alembic current

# View full migration chain history
docker exec ai_gym_backend alembic history

# Upgrade to latest revision
docker exec ai_gym_backend alembic upgrade head

# Roll back a revision
docker exec ai_gym_backend alembic downgrade -1
```

---

## 7. Health Checks & Failure Isolation

Each core service defines explicit health check probes:
- **`postgres`**: `pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-aigym}`
- **`backend`**: `curl -f http://localhost:8000/health || exit 1`
- **`frontend`**: `wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/ || exit 1`

### Degraded State Handling
When the database is unreachable:
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "environment": "production",
  "database_connected": false,
  "database_status": "unavailable",
  "ai_engine_ready": true
}
```
The FastAPI application responds with HTTP 200, reports the degraded database state cleanly without exposing database internals or crashing, and recovers automatically once PostgreSQL becomes available.

---

## 8. Real-Time WebSocket Streaming

The containerized backend fully supports long-lived WebSocket streaming:
- **Stream URL**: `ws://localhost:8000/api/v1/ws/stream?token=<JWT_TOKEN>`
- **Handshake Flow**:
  1. Client initiates HTTP Upgrade with Bearer JWT token parameter.
  2. Backend validates token and sends `{"type": "connected", "status": "authenticated"}`.
  3. Client sends `{"type": "start_session", "exercise": "squat"}`.
  4. Client streams 30 FPS pose frames `{"type": "pose_frame", "landmarks": [...]}`.
  5. Backend emits real-time biomechanical analysis `{"type": "analysis_result", ...}`.
  6. Client sends `{"type": "stop_session"}` and receives `{"type": "session_stopped", "summary": {...}}`.

---

## 9. Ollama AI Coach & Offline Fallback

- **Optional Service**: The Ollama container is included in Docker Compose but is completely optional.
- **Model Pulling**: Large LLM weights (e.g., `llama3.2`, 2.0GB+) are **never** baked into images. To pull a model into the persistent volume:
  ```bash
  docker exec -it ai_gym_ollama ollama pull llama3.2
  ```
- **Deterministic Offline Fallback**: If Ollama has no model loaded, is unreachable, or times out, the backend automatically falls back to `DeterministicFallbackCoachProvider`. Athletes receive immediate rule-based coaching feedback based on persisted biomechanical telemetry without any service disruption.
