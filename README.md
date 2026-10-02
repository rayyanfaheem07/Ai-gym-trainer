# Real-Time AI Gym Trainer

[![CI Quality Gates](https://github.com/rayyanfaheem07/Ai-gym-trainer/actions/workflows/ci.yml/badge.svg)](https://github.com/rayyanfaheem07/Ai-gym-trainer/actions/workflows/ci.yml)

## Overview

The **Real-Time AI Gym Trainer** is a computer vision and biomechanical analysis system that tracks physical exercises using a standard webcam. The platform computes body kinematics locally in the user's browser using MediaPipe Pose (33 3D body keypoints), streaming normalized coordinates over an authenticated WebSocket to a FastAPI backend.

On the server, a deterministic Finite State Machine (FSM) coupled with geometric joint angle calculations tracks exercise repetitions, measures movement cadence, and identifies specific biomechanical form faults (such as knee valgus or back arching) with sub-millisecond per-frame latency. Workout sessions and fine-grained repetition metrics are persisted in a PostgreSQL relational database. An asynchronous AI Coach powered by a local Ollama Large Language Model (`llama3.2`) analyzes structured post-workout telemetry to deliver grounded form recommendations, supported by a deterministic offline fallback system when the local LLM is unavailable.

---

## Key Features

- **Real-Time Pose Estimation**: Captures 33 3D body keypoints in the browser via MediaPipe Pose, processing coordinates at ~30 FPS without sending raw video frames to the server.
- **5 Supported Exercises**: Biomechanical analyzers for **Squat**, **Push-up**, **Bicep Curl**, **Lunge**, and **Shoulder Press**.
- **Deterministic State Machines**: Robust movement stage tracking (`READY` $\rightarrow$ `CONCENTRIC` $\rightarrow$ `PEAK` $\rightarrow$ `COMPLETE`) ensuring accurate repetition counting.
- **Biomechanical Form Scoring**: Normalized form scores (0–100) based on joint angle thresholds, calculating deductions for specific movement errors.
- **Fine-Grained Form Issue Detection**: Identifies faults such as knee valgus, incomplete depth, flared elbows, sagging hips, trunk sway, and lumbar hyperextension.
- **Pluggable Machine Learning Subsystem**: Supports PyTorch temporal sequence models (`.pt`) and scikit-learn classifiers (`.joblib`), with explicit, transparent fallback to deterministic biomechanical heuristics when trained model files are not present.
- **High-Performance FastAPI Backend**: Async architecture built with Python 3.11+, Pydantic v2 validation, and SQLAlchemy 2.0.
- **Bidirectional WebSocket Streaming**: In-memory frame processing pipeline delivering live repetition counts, joint angles, and corrective cues in <15ms.
- **Stateless JWT Authentication**: Secure user registration, bcrypt password hashing (12 rounds), role/ownership authorization, and token-authenticated WebSocket handshakes.
- **Relational Persistence**: PostgreSQL database managed through versioned Alembic migrations (revisions 001 through 004).
- **Workout Analytics & Progression**: Aggregate workout volume, exercise breakdowns, personal bests, and SVG trajectory charts.
- **Personalized Fitness Profiling**: Captures experience level, fitness goals, and coaching styles to tailor post-workout feedback.
- **Local AI Coach with Ollama**: Generates structured post-workout feedback using local `llama3.2`, constrained by strict system prompt guardrails and fact-checking against recorded database metrics.
- **Containerized Deployment**: Multi-stage Dockerfiles and Docker Compose orchestrating frontend, backend, PostgreSQL, and Ollama.
- **Automated Testing & CI/CD**: 306 backend tests (pytest) with >=80% coverage enforcement, 33 frontend tests, Ruff linting, ESLint, TypeScript typechecks, and GitHub Actions CI.
- **Security Hardening**: Sliding-window rate limiting on sensitive routes, browser security headers middleware, non-root container users, and loopback port bindings.

---

## Architecture

The system operates across a decoupled, client-server hybrid computing model:
- **Client (Browser / Next.js 15)**: Captures webcam video, runs client-side MediaPipe landmark extraction, renders a live HUD overlay, and interacts with REST & WebSocket endpoints.
- **Application Server (FastAPI)**: Ingests landmark coordinates, evaluates kinematic state machines, tracks repetitions, calculates form deductions in memory, and persists completed session data.
- **Database (PostgreSQL 15)**: Stores user identities, profiles, workouts, exercise sets, repetition metrics, detected form faults, and AI coaching feedback.
- **Local LLM (Ollama)**: Evaluates structured, authoritative post-workout metrics out-of-band to generate actionable recovery and technique advice.

For detailed architectural specifications, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the flow diagrams in [docs/diagrams/](docs/diagrams/).

---

## Technology Stack

| Domain | Technologies |
|---|---|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons, Zustand |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), Alembic, Uvicorn |
| **AI / CV** | OpenCV, MediaPipe Pose (33 3D Keypoints), NumPy, scikit-learn, PyTorch, Ollama (`llama3.2`) |
| **Database** | PostgreSQL 15 (Production) / SQLite via `aiosqlite` (Local test fallback) |
| **Testing & Quality** | pytest, pytest-asyncio, Node.js Test Runner (via `tsx`), Ruff, ESLint, TypeScript (`tsc --noEmit`), Bandit, pip-audit |
| **Infrastructure** | Docker, Docker Compose, GitHub Actions |

---

## System Flow

```
[ Client Browser ]
      │
      ├─► 1. Captures webcam video stream (HTMLVideoElement, 30 FPS)
      ├─► 2. MediaPipe extracts 33 3D body landmark coordinates (Client-side)
      │
      ▼ (Transmits coordinates over WebSocket: /api/v1/ws/stream?token=<JWT>)
[ FastAPI Backend ]
      │
      ├─► 3. Decodes & validates JWT; checks message bounds (<1MB)
      ├─► 4. Ingests coordinates into pre-allocated NumPy (33, 4) float32 buffer
      ├─► 5. Evaluates exercise state machine (FSM) & computes joint angles
      ├─► 6. Detects biomechanical faults & calculates form score deductions
      ├─► 7. Dispatches real-time 'analysis_result' JSON to browser (<15ms)
      │
      ▼ (On session completion: stop_session / finish workout)
[ PostgreSQL Database ]
      │
      ├─► 8. Atomically commits workout, sets, reps, and form fault records
      │
      ▼ (Post-workout coach request: /api/v1/coach/session/{id})
[ AI Coach Pipeline ]
      │
      ├─► 9. Extracts verified telemetry facts into bounded CoachContext
      ├─► 10. Sends context to local Ollama LLM (or engages deterministic fallback)
      └─► 11. Validates structured JSON schema & stores coaching summary
```

---

## Supported Exercises

| Exercise | Primary Biomechanical Angles | Tracked Movement Faults |
|---|---|---|
| **Squat** | Hip-Knee-Ankle (Knee), Shoulder-Hip-Knee (Hip) | `KNEE_VALGUS` (knees caving inward), `INSUFFICIENT_DEPTH` (thighs not parallel), `FORWARD_TRUNK_LEAN` (excessive torso angle), `ASYMMETRIC_HIP_SHIFT` |
| **Push-up** | Shoulder-Elbow-Wrist (Elbow), Shoulder-Hip-Ankle (Spine) | `ELBOW_FLARE` (excessive shoulder abduction), `SAGGING_HIPS` (lumbar extension), `HIKED_HIPS` (lumbar flexion), `INSUFFICIENT_DEPTH` |
| **Bicep Curl** | Shoulder-Elbow-Wrist (Elbow), Hip-Shoulder-Elbow | `ELBOW_SWAY` (elbow drifting forward/backward), `TRUNK_SWAY` (momentum swinging), `INCOMPLETE_RANGE_OF_MOTION` |
| **Lunge** | Lead Knee Angle, Trailing Knee Angle, Torso Angle | `FRONT_KNEE_OVER_TOES` (excessive forward tracking), `TORSO_LEAN`, `INSUFFICIENT_DEPTH` |
| **Shoulder Press** | Elbow Extension Angle, Lumbar Spine Angle | `ARCHED_BACK` (lumbar hyperextension), `INCOMPLETE_LOCKOUT` (arms not fully extended), `ASYMMETRICAL_PRESS` |

---

## AI / Computer Vision Pipeline

1. **Camera Frame Acquisition**: The browser accesses the local webcam via `navigator.mediaDevices.getUserMedia` at ~30 FPS.
2. **Pose Landmark Extraction**: MediaPipe Pose evaluates the frame inside the browser, extracting 33 normalized coordinates $(x, y, z, \text{visibility})$. Raw video frames are never transmitted over the network.
3. **Normalization & Buffering**: Coordinates are parsed on the backend into a pre-allocated `(33, 4)` NumPy float32 array, avoiding per-frame memory allocation thrashing.
4. **Kinematic State Machine**: Joint angles are calculated using Euclidean vector geometry. The active exercise state machine advances movement stages (`READY`, `CONCENTRIC`, `PEAK`, `COMPLETE`).
5. **Repetition Detection**: A repetition is completed when the movement traverses the required inflection angle threshold and returns to starting extension.
6. **Form Analysis & Penalty Scoring**: Biomechanical rules evaluate joint deviations. Penalties (5, 10, or 20 points depending on severity) are deducted from a base score of 100.
7. **Machine Learning Classifier Integration**: The decoupled `BaseAIInferenceService` evaluates sequence patterns using PyTorch or scikit-learn models if model weight files exist, falling back gracefully to heuristic state machines when absent.
8. **Real-Time WebSocket Response**: Server sends a JSON `analysis_result` packet returning current rep count, form score, active stage, and corrective feedback cues.
9. **Relational Persistence**: Upon set completion (`stop_session`), aggregated metrics are written to PostgreSQL.

---

## Authentication & Security

- **JWT Authentication**: User identity is verified using HMAC-SHA256 signed JSON Web Tokens (`HS256`). Algorithm confusion attacks are blocked by explicit decoder constraints.
- **Password Hashing**: Passwords are encrypted using salted `bcrypt` with 12 computation rounds. Password hashes are never returned in API responses.
- **Ownership Authorization**: Strict multi-tenant checks prevent User A from viewing, modifying, or evaluating workouts belonging to User B (HTTP 403 Forbidden).
- **WebSocket Handshake Security**: WebSockets require token verification in the connection query string (`?token=<JWT>`), closing unauthenticated connections with code `1008`.
- **Input Validation**: Pydantic v2 models validate data bounds (e.g., repetition bounds, valid form scores 0–100, string lengths).
- **Sliding-Window Rate Limiting**: In-memory rate limiting applied to authentication (10 req/min), AI Coach generation (10 req/min), and WebSocket handshakes (30 connections/min).
- **Security Headers Middleware**: Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy: camera=(self)`.
- **Production Secret Validation**: In `production` mode, the backend validates that `JWT_SECRET_KEY` is not set to any known default key and is at least 32 characters long.
- **Container Least Privilege**: All Docker containers execute with `no-new-privileges:true`. Frontend runs as non-root `nextjs` (UID 1001), backend as non-root `appuser` (UID 10001).
- **Automated Security Scanning**: Zero security alerts across 10,500+ lines in Bandit SAST scans; zero known vulnerabilities in `pip-audit`.

For the complete security specification, see [docs/SECURITY.md](docs/SECURITY.md).

---

## AI Coach

The AI Coach provides personalized post-workout recommendations grounded strictly in verified workout telemetry:

- **Factual Telemetry Grounding**: The LLM consumes an authoritative `CoachContext` constructed directly from database records (reps, form scores, tempo, detected fault counts). **Zero raw video frames or camera images are sent to the LLM.**
- **Local Ollama Inference**: Connects via HTTP to a local Ollama instance running `llama3.2`, avoiding cloud API costs and keeping workout data private.
- **Strict Guardrails**: The system prompt prohibits hallucinating workout statistics, changing numerical values, or providing medical diagnoses.
- **Pydantic Output Validation**: LLM responses are parsed into a strict JSON schema (`CoachStructuredOutput`) containing an executive summary, strengths, areas to improve, next-session focus, and safety notes.
- **Deterministic Offline Fallback**: If Ollama is offline, unreachable, or times out (>30s), `DeterministicFallbackCoachProvider` automatically generates structured recommendations derived from recorded fault codes.

---

## Personalization

- **Athlete Fitness Profile**: Captures user fitness goals (`strength`, `muscle_gain`, `fat_loss`, `general_fitness`, `endurance`), experience level (`beginner`, `intermediate`, `advanced`), preferred focus (`form`, `strength`, `consistency`, `balanced`), and coaching style (`concise`, `supportive`, `detailed`, `technical`).
- **Longitudinal Trend Tracking**: Personalization service aggregates performance trajectories over the user's past 10 workouts to detect recurring faults and progress.
- **Adaptive Coaching Feedback**: The AI Coach adapts vocabulary and pedagogical depth to the athlete's experience level and coaching style.
- **Strict User Isolation**: Personal profiles and trends are scoped strictly to the authenticated user ID. The system does not make medical or health-diagnosis claims.

---

## Analytics

- **Lifetime Overview**: `/api/v1/analytics/summary` aggregates total completed sessions, total reps, valid reps, accuracy percentage, average form scores, and 30-day activity volume.
- **Exercise-Specific Metrics**: `/api/v1/analytics/exercises/{exercise}` tracks session count, rep totals, all-time best form score, and historical distribution of form issues.
- **Progression Trajectories**: `/api/v1/analytics/trends` provides chronological time-series points across 7, 14, 30, or 90 days.
- **Frontend Visualizations**: Pure SVG trend charts and paginated workout history with set-by-set and rep-by-rep inspection modals.

---

## Project Structure

```
ai-gym-trainer/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI pipeline
├── ai/                            # Computer Vision & Biomechanics engine
│   ├── classifier/                # Sequence classifiers & inference engines
│   ├── exercises/                 # Exercise state machines (Squat, Pushup, Curl, Lunge, Press)
│   ├── pose/                      # MediaPipe pose detector & landmark parser
│   └── tracker/                   # Angle calculators & filtering
├── alembic/                       # Database migration scripts (001 to 004)
│   └── versions/                  # Migration revision files
├── backend/                       # FastAPI backend
│   ├── app/
│   │   ├── api/v1/                # Route handlers (auth, workouts, coach, ws, profile, etc.)
│   │   ├── core/                  # Config, database setup, rate limiter, security
│   │   ├── models/                # SQLAlchemy ORM entities (User, Workout, ExerciseSession)
│   │   ├── repositories/          # Database query repositories
│   │   ├── schemas/               # Pydantic v2 request/response schemas
│   │   ├── services/              # Domain logic (Auth, Coach, Personalization, Workout, WS)
│   │   └── main.py                # ASGI application entrypoint
│   ├── requirements.txt           # Production backend dependencies
│   └── requirements-dev.txt       # Development & test dependencies
├── docker/                        # Production Dockerfiles (backend.Dockerfile, frontend.Dockerfile)
├── docs/                          # Comprehensive technical documentation
│   ├── diagrams/                  # Mermaid architecture diagrams
│   ├── API.md                     # REST & WebSocket API specification
│   ├── ARCHITECTURE.md            # Detailed system architecture guide
│   ├── DEVELOPMENT.md             # Developer setup, testing, and contribution guide
│   ├── DOCKER.md                  # Docker deployment specifications
│   ├── SECURITY.md                # Security architecture & hardening guide
│   └── TESTING.md                 # Testing methodology & quality gates
├── frontend/                      # Next.js 15 App Router web application
│   ├── src/
│   │   ├── app/                   # App Router pages (login, register, workout, history, dashboard)
│   │   ├── components/            # UI components (CameraFeed, TelemetryHUD, TrendChart, etc.)
│   │   └── lib/                   # API clients, WebSocket hook, types, audio feedback
│   └── package.json               # Frontend dependencies & scripts
├── models/                        # Model weights directory (optional .pt and .joblib files)
├── scripts/                       # Maintenance & CI runner scripts
├── tests/                         # Backend test suite (unit, integration, performance)
├── docker-compose.yml             # Multi-service composition configuration
├── pyproject.toml                 # Ruff & pytest configuration
└── README.md                      # Project documentation
```

---

## Installation

### Prerequisites
- **Python**: 3.11 or 3.12+
- **Node.js**: 18.x or 20.x+ & npm
- **PostgreSQL**: 15+ (or use SQLite for rapid local testing)
- **Ollama**: (Optional) For local LLM coaching (`ollama pull llama3.2`)
- **Docker & Docker Compose**: (Optional) For containerized deployment

---

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rayyanfaheem07/Ai-gym-trainer.git
   cd ai-gym-trainer
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   cp frontend/.env.example frontend/.env.local
   ```

3. **Backend setup**:
   ```bash
   # Create and activate virtual environment
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate

   # Install dependencies
   pip install -r backend/requirements.txt
   pip install -r backend/requirements-dev.txt

   # Run database migrations
   alembic upgrade head

   # Start backend development server
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Frontend setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Access the web app at `http://localhost:3000`.

5. **Ollama setup (Optional)**:
   ```bash
   ollama pull llama3.2
   ollama serve
   ```
   *(If Ollama is not running, the backend transparently uses the deterministic offline fallback coach).*

---

### Docker Deployment

Run the complete multi-container stack with a single command:

```bash
# Build and start all services (postgres, backend, frontend, ollama)
docker compose up -d --build

# Verify container status and health checks
docker compose ps

# View backend logs
docker compose logs -f backend
```

- **Frontend Web UI**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Swagger Docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) (or [http://localhost:8000/docs](http://localhost:8000/docs))
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Environment Variables

Key variables from `.env.example`:

| Variable | Description | Default / Example | Production Requirement |
|---|---|---|---|
| `ENVIRONMENT` | Runtime environment (`development`, `production`, `testing`) | `development` | Set to `production` |
| `JWT_SECRET_KEY` | Secret key for signing HS256 JWT tokens | `dev-secret-key-change-in-production...` | **REQUIRED**: Must be 32+ char random key |
| `DATABASE_URL` | Async database connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/aigym` | Set to production PostgreSQL URL |
| `POSTGRES_USER` | PostgreSQL database username | `postgres` | Use secure credentials |
| `POSTGRES_PASSWORD` | PostgreSQL database password | `postgres_secure_password` | **REQUIRED**: Use strong password |
| `POSTGRES_DB` | PostgreSQL database name | `aigym` | Customize as needed |
| `RUN_MIGRATIONS` | Automatically apply Alembic migrations on startup | `true` | Recommended `true` |
| `OLLAMA_BASE_URL` | Ollama LLM HTTP service URL | `http://localhost:11434` (`http://ollama:11434` in Docker) | Target local Ollama instance |
| `OLLAMA_MODEL` | LLM model tag | `llama3.2` | Ensure model is pulled |
| `REALTIME_PROCESSING_FPS`| Frame processing rate cap | `30` | 30 FPS recommended |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend REST API base URL | `http://localhost:8000/api/v1` | Point to backend domain |
| `NEXT_PUBLIC_WS_URL` | Frontend WebSocket streaming URL | `ws://localhost:8000/api/v1/ws/stream` | Point to backend WS endpoint |

---

## API Overview

Comprehensive API documentation is available in [docs/API.md](docs/API.md).

| Group | Method | Path | Purpose | Authentication |
|---|---|---|---|---|
| **Health** | `GET` | `/health` | Check backend, DB, and AI readiness | Public |
| **Auth** | `POST` | `/api/v1/auth/register` | Register new user account | Public (Rate-limited: 10/min) |
| **Auth** | `POST` | `/api/v1/auth/login` | Authenticate user & issue JWT | Public (Rate-limited: 10/min) |
| **Auth** | `GET` | `/api/v1/auth/me` | Get authenticated user info | Bearer Token |
| **Profile** | `GET` | `/api/v1/profile` | Retrieve personal fitness profile | Bearer Token |
| **Profile** | `PUT` | `/api/v1/profile` | Update personal fitness profile | Bearer Token |
| **Workouts** | `POST` | `/api/v1/workouts/start` | Initialize new workout session | Bearer Token |
| **Workouts** | `POST` | `/api/v1/workouts/{id}/finish` | Conclude workout session | Bearer Token (Owned) |
| **Workouts** | `GET` | `/api/v1/workouts/{id}` | Get detailed workout telemetry | Bearer Token (Owned) |
| **Workouts** | `GET` | `/api/v1/workouts/history` | Paginated workout history | Bearer Token |
| **Analytics** | `GET` | `/api/v1/analytics/summary` | Athlete lifetime stats | Bearer Token |
| **Analytics** | `GET` | `/api/v1/analytics/exercises/{exercise}` | Exercise-specific metrics | Bearer Token |
| **Analytics** | `GET` | `/api/v1/analytics/trends` | Time-series progression trends | Bearer Token |
| **Coach** | `POST` | `/api/v1/coach/session/{session_id}` | Generate AI coaching feedback | Bearer Token (Rate-limited: 10/min) |
| **Coach** | `GET` | `/api/v1/coach/session/{session_id}` | Retrieve cached coaching feedback | Bearer Token (Owned) |
| **Exercises** | `GET` | `/api/v1/exercises` | List supported exercises | Public |
| **WebSocket** | `WS` | `/api/v1/ws/stream?token=<JWT>` | Real-time pose telemetry stream | JWT Query Param (Rate-limited: 30/min) |

---

## Testing

### Backend Tests & Verification
```bash
# Run complete test suite (306 tests)
pytest

# Run with test coverage enforcement (>=80%)
pytest --cov=backend --cov=ai --cov-fail-under=80

# Run Ruff linter
ruff check .

# Run Static Application Security Testing (Bandit)
bandit -r backend ai -ll -ii

# Run dependency vulnerability audit
pip-audit -r backend/requirements.txt
```

### Frontend Tests & Verification
```bash
cd frontend

# Run frontend tests (33 tests via tsx)
npm test

# Run TypeScript type check
npx tsc --noEmit

# Run ESLint
npm run lint

# Build standalone production bundle
npm run build
```

---

## Docker

Multi-container orchestration is defined in [docker-compose.yml](docker-compose.yml):
- **Services**: `postgres` (PostgreSQL 15), `backend` (FastAPI), `frontend` (Next.js 15), `ollama` (Local LLM).
- **Networking**: Isolated bridge network `ai_gym_net`.
- **Port Bindings**:
  - Frontend: `0.0.0.0:3000`
  - Backend: `0.0.0.0:8000`
  - PostgreSQL: `127.0.0.1:5432` (restricted to loopback)
  - Ollama: `127.0.0.1:11434` (restricted to loopback)
- **Least Privilege**: All services enforce `security_opt: [no-new-privileges:true]`. Backend runs as unprivileged `appuser` (UID 10001), frontend as `nextjs` (UID 1001).
- **Health Checks & Migrations**: Backend waits for PostgreSQL health checks before starting; automatically executes `alembic upgrade head` when `RUN_MIGRATIONS=true`.

For full details, see [docs/DOCKER.md](docs/DOCKER.md) and [docs/diagrams/docker-deployment.md](docs/diagrams/docker-deployment.md).

---

## Security

Security architecture and Phase 19 hardening controls are detailed in [docs/SECURITY.md](docs/SECURITY.md):
- In-memory sliding-window rate limiting on auth, coach, and WebSocket connections.
- HTTP security headers middleware (`CSP`, `X-Content-Type-Options`, `X-Frame-Options`).
- Non-root container privileges and loopback port bindings.
- Zero plaintext credential storage (12-round bcrypt hashes).
- Production validation rejecting default JWT secrets.

---

## Performance

Measured benchmark results on local test environment (`tests/unit/test_performance_benchmarks.py`):

- **Pose Frame Parsing & Biomechanical Analysis Latency** (100 frames through landmark parser and squat analyzer):
  - Average: **0.332 ms** / frame
  - 95th Percentile: **0.535 ms** / frame
  - Maximum: **3.670 ms** / frame
  *(Well within the 33.3 ms budget for 30 FPS real-time operation).*
- **Batch Sequence Inference Throughput** (16 sequence windows):
  - Total: **2.007 ms** (0.125 ms / window).
- **Personalization Trends Database Query** (10 historical workouts with full session/rep/fault data):
  - Execution Time: **37.503 ms** (sub-50ms SLA).

---

## Known Limitations

- **In-Memory Rate Limiting**: The sliding-window rate limiter is currently maintained in server memory. Distributed or horizontally scaled deployments across multiple instances require a centralized cache such as Redis.
- **WebSocket Browser Authentication**: Because the standard browser WebSocket API does not support custom headers, JWT tokens are passed via the query parameter during the initial handshake. TLS encryption (WSS) is required in production to protect token parameters in transit.
- **Local Ollama Latency**: While deterministic offline fallback is instantaneous (<1ms), responses from local Ollama LLMs depend on host CPU/GPU hardware. AI coaching is decoupled from real-time exercise streaming to ensure frame rates are unaffected.
- **Client-Side MediaPipe CPU Usage**: High webcam resolutions (such as 4K) can cause high CPU utilization during MediaPipe landmark extraction on lower-end client devices. A 720p stream is recommended.
- **Known Transitive npm Vulnerabilities**: `npm audit` identifies 3 transitive vulnerabilities within Next.js 15.1.0 build dependencies (`sharp`, `postcss`). Upgrading these packages requires upstream Next.js updates.

---

## Roadmap

Planned future enhancements (not currently implemented):
- Redis-backed distributed rate limiter and session cache.
- WebAssembly (WASM) optimized client-side landmark smoothing filters.
- Additional exercise state machines (Deadlift, Plank, Overhead Squat).
- Multi-camera angle support for depth occlusion handling.

---

## License

This project is licensed under the terms of the MIT License.
