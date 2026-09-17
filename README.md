# Real-Time AI Gym Trainer

A real-time AI-powered computer vision fitness coach and telemetry platform. It features MediaPipe Pose 3D body landmark extraction, temporal PyTorch deep learning exercise recognition, a deterministic Finite State Machine (FSM) for rep counting, a secure multi-tenant FastAPI backend with JWT authentication and PostgreSQL/Alembic storage, an offline local Large Language Model (via Ollama) for personalized coaching, and a modern Next.js 15 App Router web application with real-time HUD telemetry.

---

## Architecture Overview

```
                      +-----------------------------------+
                      |   Next.js 15 Client (Webcam UI)   |
                      +-----------------+-----------------+
                                        | (REST + JWT Bearer / WebSocket Stream)
                                        v
+---------------------------------------+---------------------------------------+
| FastAPI Real-Time Backend Service                                             |
|                                                                               |
|  +---------------------+   +---------------------+   +---------------------+  |
|  | JWT Bearer Auth &   |-->| MediaPipe Pose &    |-->| 1€ Adaptive Filter  |  |
|  | User Isolation      |   | Landmark Extraction |   | Smoothing Pipeline  |  |
|  +---------------------+   +---------------------+   +----------+----------+  |
|                                                                 |             |
|  +---------------------+   +---------------------+              v             |
|  | Real-Time Feedback  |<--| Safety Rule Engine  |<--+---------------------+  |
|  | & Audio Synthesizer |   | Violation Detection |   | Rep Counter FSM     |  |
|  +---------------------+   +---------------------+   | (State Transitions) |  |
|  +---------------------+   +---------------------+   | & PyTorch Temporal  |  |
|  | Multi-Tenant Access |<--| Biomechanical Angle |<--+---------------------+  |
|  | Boundary Check      |   | Metric Calculation  |                            |
|  +---------------------+   +---------------------+                            |
+---------------------------------------+---------------------------------------+
                                        |
             +--------------------------+--------------------------+
             |                                                     |
             v                                                     v
+--------------------------+                         +--------------------------+
| PostgreSQL / SQLite DB   |                         | Local Ollama LLM         |
| Session & Rep Telemetry  |                         | Post-Workout Coach Agent |
| Users & Password Hashes  |                         +--------------------------+
+--------------------------+
```

---

## Technology Stack

- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons, Zustand
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), WebSockets, PyJWT, Bcrypt, Uvicorn
- **AI / Computer Vision**: PyTorch, Scikit-learn, MediaPipe Pose (33 3D Keypoints), OpenCV, NumPy, One-Euro Filter
- **Local AI Coach**: Ollama (`llama3.2` / `mistral`)
- **Database & Migrations**: PostgreSQL (Production) / SQLite (Local Dev fallback via aiosqlite), Alembic
- **DevOps & Testing**: Docker, Docker Compose, Pytest, Pytest-Asyncio, Ruff, TSX / Node Test Runner

---

## Next.js Frontend & Real-Time Workout UI (Phase 11)

- **Authentication UI**: Complete `/login` and `/register` flows using secure JWT Bearer tokens with automated redirection and profile management.
- **Athlete Dashboard**: Real-time `/dashboard` displaying athlete profile, supported exercise catalog dynamically fetched from backend, and recent workout activity.
- **Live AI Workout Arena**: Interactive `/workout` suite integrating webcam video preview, 2D/3D skeleton canvas rendering, live repetition counting, form scoring gauges, joint angle telemetry, and audio cues.
- **Biomechanical Telemetry Stream**: Decoupled browser pose landmark capture transmitting 33 MediaPipe keypoints over `ws://host/api/v1/ws/stream?token=<JWT>`.
- **Session Lifecycle & Modal**: Atomic workout creation, real-time in-memory streaming, and post-session aggregation modal saving results to PostgreSQL.

---

## Analytics & Workout History (Phase 12)

- **Strict Database Ground Truth**: 100% of summary statistics, exercise profiles, and time-series trends are computed from persisted PostgreSQL/SQLite models. Zero fabricated data.
- **Lifetime Athlete Overview**: `/api/v1/analytics/summary` aggregates total sessions, total reps, valid repetitions, accuracy percentage, average form scores, and 30-day activity.
- **Exercise-Specific Deep Dive**: `/api/v1/analytics/exercises/{exercise}` breaks down session volume, all-time best form score, average duration, and historical form faults.
- **Performance Progression Charts**: `/api/v1/analytics/trends` and pure SVG `PerformanceTrendChart` visualizes multi-metric trajectories over 7, 14, 30, or 90 days.
- **Paginated Workout History**: `/history` page with server-side pagination, exercise filtering, and date range query parameters.
- **Workout Inspection Modal**: Deep-dive into completed sessions with rep-by-rep breakdowns, form score gauges, and fault summaries.


---

## Authentication & Security (Phase 9 & 10)

- **Registration & Password Security**: `POST /api/v1/auth/register` validates email and password strength, encrypting credentials using salted `bcrypt` (12 rounds). Plaintext passwords are never stored.
- **Login & JWT Token Issuance**: `POST /api/v1/auth/login` verifies credentials and issues standard HS256 JWT tokens containing `sub`, `email`, `iat`, `exp`, and `iss`.
- **Zero-Trust Identity & Route Protection**: Protected routes (`/workouts/*`, `/analysis`, `/coach/evaluate`, `/ws/stream`) utilize JWT validation to resolve user identity strictly from token claims.
- **Cross-Tenant Isolation**: Server-side checks enforce that athletes can only view, modify, and analyze their own workout data, returning `403 Forbidden` on unauthorized cross-user access attempts.

---

## Real-Time WebSocket Streaming (Phase 10 & 11)

- **Endpoint**: `WS /api/v1/ws/stream?token=<JWT>`
- **Token-Based Handshake**: Authenticates clients during initial WebSocket upgrade using JWT validation; unauthenticated connections are cleanly closed with close code `1008`.
- **In-Memory Biomechanical Telemetry**: Evaluates real-time pose frames against exercise analyzers in memory with zero per-frame database writes and sub-15ms processing latency.
- **Supported Exercises**: Squat, Push-up, Bicep Curl, Lunge, Shoulder Press.

---

## Repository Structure

```
ai-gym-trainer/
├── ai/                 # Core CV, 3D geometry math, pose smoothing, and exercise FSMs
├── alembic/            # Database migration scripts and versioned schemas
├── backend/            # FastAPI REST & WebSocket server, ORM models, auth services, repositories
├── frontend/           # Next.js 15 TypeScript application with Tailwind CSS and HUD components
│   ├── src/
│   │   ├── app/        # App Router pages (/login, /register, /dashboard, /workout, /history)
│   │   ├── components/ # Reusable UI, camera feed, skeleton canvas, and telemetry HUD
│   │   ├── hooks/      # useAuth, useWebSocket, useCamera custom hooks
│   │   ├── lib/        # API client, token management, and pose detector
│   │   ├── store/      # Zustand auth and workout stores
│   │   └── types/      # TypeScript interfaces matching backend models
├── models/             # PyTorch temporal and scikit-learn exercise classification weights
├── tests/              # Pytest unit and integration test suite
├── docs/               # Architecture, API specifications, and biomechanical rules
├── scripts/            # Cross-platform development and run scripts
├── docker/             # Container configuration files
├── docker-compose.yml  # Multi-container orchestration (Backend, Postgres, Ollama)
└── pytest.ini          # Test runner configuration
```

---

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- (Optional) Docker & Docker Compose
- (Optional) Ollama for local LLM inference

### 1. Environment Setup
```bash
# Create root .env file from template
cp .env.example .env

# Create frontend .env.local file from template
cp frontend/.env.example frontend/.env.local
```

### 2. Backend Setup & Migrations
```bash
# Apply database migrations
alembic upgrade head

# Install dependencies into virtual environment
pip install -r backend/requirements.txt

# Run FastAPI backend server
python -m uvicorn backend.app.main:app --reload --port 8000
```
Backend will be available at `http://localhost:8000` (Interactive Swagger UI with Bearer Authentication at `http://localhost:8000/api/v1/docs`).

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Frontend will be available at `http://localhost:3000`.

---

## Running Tests & Quality Checks

```bash
# Backend test suite (173 tests)
pytest

# Backend linter and formatting checks
ruff check backend/ tests/

# Frontend unit tests
cd frontend
npm test

# Frontend TypeScript check and linter
npm run typecheck
npm run lint

# Frontend production build
npm run build
```
