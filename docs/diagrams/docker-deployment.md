# Docker Deployment Architecture

This document describes the multi-container deployment architecture defined in [docker-compose.yml](file:///c:/Users/MOD/Desktop/ai-gym-trainer/docker-compose.yml).

```mermaid
graph TD
    subgraph Host["Host Machine"]
        ClientBrowser["Browser / Client<br/>(Ports: 3000, 8000)"]
    end

    subgraph DockerNet["Docker Network: ai_gym_net (bridge)"]
        subgraph FrontendContainer["Frontend Service (Node.js 20 Alpine)"]
            NextApp["Next.js Application<br/>(Port: 3000)<br/>User: nextjs (non-root)"]
        end

        subgraph BackendContainer["Backend Service (Python 3.11 Slim)"]
            FastAPI["FastAPI / Uvicorn<br/>(Port: 8000)<br/>User: appuser (non-root)"]
            AlembicRunner["Alembic Migrations<br/>(Runs on startup: RUN_MIGRATIONS=true)"]
        end

        subgraph PostgresContainer["Database Service (PostgreSQL 15 Alpine)"]
            PostgresDB["PostgreSQL Engine<br/>Internal Port: 5432<br/>Bound: 127.0.0.1:5432"]
        end

        subgraph OllamaContainer["LLM Service (Ollama)"]
            OllamaEngine["Ollama Server<br/>Internal Port: 11434<br/>Bound: 127.0.0.1:11434"]
        end
    end

    subgraph Volumes["Named Volumes"]
        PgDataVol[("pgdata<br/>/var/lib/postgresql/data")]
        OllamaVol[("ollama_models<br/>/root/.ollama")]
    end

    %% Client traffic
    ClientBrowser -->|"HTTP / (Port 3000)"| NextApp
    ClientBrowser -->|"REST API & WS / (Port 8000)"| FastAPI

    %% Container-to-container traffic
    FastAPI -->|"postgresql+asyncpg://postgres:5432/aigym"| PostgresDB
    FastAPI -->|"http://ollama:11434/api/generate"| OllamaEngine
    AlembicRunner -.->|"Schema migrations"| PostgresDB

    %% Volume mounts
    PostgresDB --- PgDataVol
    OllamaEngine --- OllamaVol

    %% Dependencies and health checks
    FastAPI -.->|"depends_on (service_healthy)"| PostgresDB
    NextApp -.->|"depends_on (service_healthy)"| FastAPI
```

## Service Configuration & Security Constraints

| Service | Image / Build Context | Exposed Ports | Bound Interface | Non-Root User | Health Check |
|---|---|---|---|---|---|
| `frontend` | `docker/frontend.Dockerfile` | `3000:3000` | `0.0.0.0:3000` | `nextjs` (UID 1001) | `wget --spider http://127.0.0.1:3000/` |
| `backend` | `docker/backend.Dockerfile` | `8000:8000` | `0.0.0.0:8000` | `appuser` (UID 10001) | `curl -f http://localhost:8000/health` |
| `postgres` | `postgres:15-alpine` | `5432` | `127.0.0.1:5432` (loopback only) | `postgres` (system) | `pg_isready -U postgres -d aigym` |
| `ollama` | `ollama/ollama:latest` | `11434` | `127.0.0.1:11434` (loopback only) | Root in container (hardened privileges) | N/A |

### Security Measures in Deployment (Phase 19 Hardening)
1. **Loopback Port Binding**: Internal storage and AI engines (`postgres` and `ollama`) are bound strictly to `127.0.0.1`, preventing external network exposure on public interfaces.
2. **Least Privilege (`no-new-privileges:true`)**: All services run with the Linux `no-new-privileges` flag enabled to prevent setuid privilege escalation.
3. **Dedicated Non-Root Execution**: Both `frontend` (`nextjs`) and `backend` (`appuser`) run as dedicated unprivileged user accounts with restricted filesystem write boundaries.
4. **Health-gated Startup**: Startup dependencies use Docker Compose `service_healthy` conditions: the database must pass readiness checks before the backend boots and runs migrations, and the backend must pass health checks before the frontend begins serving traffic.
