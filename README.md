# Real-Time AI Gym Trainer

[![CI Quality Gates](https://github.com/rayyanfaheem07/Ai-gym-trainer/actions/workflows/ci.yml/badge.svg)](https://github.com/rayyanfaheem07/Ai-gym-trainer/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![Next.js 15](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)
![PostgreSQL 15](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

A full-stack, real-time computer vision and biomechanical analysis system that evaluates physical exercise form via standard monocular webcams. The platform performs client-side landmark extraction using MediaPipe Pose (33 3D body keypoints) in the browser, streaming normalized coordinates over an authenticated WebSocket to a FastAPI backend. On the server, deterministic Finite State Machines (FSM) and vector trigonometry track exercise repetitions, compute movement cadence, and identify biomechanical form faults with sub-millisecond processing latency per frame. Workout telemetry is persisted in PostgreSQL with versioned Alembic migrations, while an asynchronous AI Coach powered by a local Ollama Large Language Model (`llama3.2`) delivers grounded post-workout technique recommendations with automatic fallback to deterministic rule-based analysis.

---

## Overview

The Real-Time AI Gym Trainer addresses the need for accessible, privacy-preserving exercise technique assessment without requiring wearable sensors or specialized motion-capture hardware. The system integrates:

- **Edge Computer Vision**: In-browser pose estimation executing via MediaPipe Pose, processing 33 3D body landmark coordinates locally at ~30 FPS without streaming raw camera video over the network.
- **Biomechanical Kinematics**: Deterministic planar and 3D joint angle calculators using vector geometry, coupled with state machines to monitor movement phases and detect form anomalies.
- **Machine Learning Subsystem**: Pluggable inference architecture supporting classical and temporal sequence classifiers with transparent fallback to deterministic heuristics.
- **High-Throughput Asynchronous Backend**: FastAPI service implementing a four-tier architecture (API, Service, AI/CV, Repository) with Pydantic v2 validation and async database interactions.
- **Real-Time Bidirectional WebSockets**: Low-latency frame ingestion pipeline utilizing pre-allocated NumPy buffers and in-memory evaluation to eliminate database I/O bottlenecks during active exercise sets.
- **Persistent Analytics & Progression**: PostgreSQL relational database storing structured workout histories, set-by-set telemetry, rep-level angles, and longitudinal performance trajectories.
- **Grounded AI Coaching**: Local LLM integration (`llama3.2` via Ollama) that ingests verified workout metrics into an authoritative context, strictly isolated from raw video data and protected against hallucinations.

---

## Key Features

- **Client-Side Pose Estimation**: Ingests 33 3D body landmarks at ~30 FPS via MediaPipe Pose in the browser; raw camera video never leaves the client device.
- **5 Supported Exercise Analyzers**: Dedicated biomechanical evaluators for **Squat**, **Push-up**, **Bicep Curl**, **Lunge**, and **Shoulder Press**.
- **Deterministic Finite State Machines**: Phase tracking (`READY` $\rightarrow$ `CONCENTRIC` $\rightarrow$ `PEAK` $\rightarrow$ `COMPLETE`) ensures reliable repetition counts without false triggers from micro-jitters.
- **Biomechanical Form Scoring**: Normalized form scores (0–100) computed per repetition with graded deductions for minor (5 pt), moderate (10 pt), and severe (20 pt) faults.
- **Detailed Form Fault Detection**: Detects specific biomechanical errors including knee valgus, insufficient depth, flared elbows, sagging hips, trunk sway, and lumbar hyperextension.
- **Pluggable ML Subsystem**: Decoupled inference interface (`BaseAIInferenceService`) supporting PyTorch temporal models and scikit-learn classifiers, with explicit fallback logging when weights are unloaded.
- **Zero-Allocation In-Memory Frame Processing**: Pre-allocated `(33, 4)` NumPy float32 buffers enable sub-millisecond per-frame analysis without garbage collection overhead.
- **Stateless JWT Authentication**: Secure user registration, bcrypt password hashing (12 rounds), role/ownership authorization, and token-validated WebSocket handshakes.
- **Multi-Tenant Data Isolation**: Strict user-level authorization preventing cross-user data access (IDOR protection) across workouts, analytics, and coaching insights.
- **Relational Data Persistence**: PostgreSQL schema managed via Alembic migrations (revisions 001 through 004) with composite performance indexes and cascade deletions.
- **Longitudinal Trend Tracking**: Personalization service aggregates historical performance to identify recurring form issues and measure long-term technique improvements.
- **Local AI Coach with Ollama**: Asynchronous post-workout qualitative review using local `llama3.2`, constrained by strict system prompt guardrails and fact-checked against database records.
- **Deterministic Offline Fallback Coach**: Instantaneous rule-based coaching fallback that generates structured recommendations when Ollama is offline or times out.
- **Multi-Container Docker Deployment**: Fully orchestrated local stack with Docker Compose, non-root users, loopback network bindings, and automated container health checks.
- **Comprehensive Quality Gates**: 306 backend tests (pytest) with 87.25% coverage, 33 frontend tests, Ruff linting, ESLint, TypeScript verification, Bandit security analysis, and pip-audit scanning.

---

## Supported Exercises

The system features five specialized exercise analyzers. Each analyzer implements an independent state machine and joint angle evaluator tailored to the biomechanics of the movement:

| Exercise | Primary Joint Angles Measured | Tracked Movement Faults | Valid Repetition Criteria |
| :--- | :--- | :--- | :--- |
| **Squat** | Hip-Knee-Ankle (Knee Flexion), Shoulder-Hip-Knee (Hip Flexion) | `KNEE_VALGUS` (knees caving inward), `INSUFFICIENT_DEPTH` (thighs above parallel), `FORWARD_TRUNK_LEAN` (excessive torso forward lean), `ASYMMETRIC_HIP_SHIFT` | Knee flexion $\le 100^\circ$ at bottom, full hip and knee lockout at top extension |
| **Push-up** | Shoulder-Elbow-Wrist (Elbow Flexion), Shoulder-Hip-Ankle (Core Alignment) | `ELBOW_FLARE` (excessive shoulder abduction $> 75^\circ$), `SAGGING_HIPS` (lumbar extension $< 160^\circ$), `HIKED_HIPS` (lumbar flexion $> 195^\circ$), `INSUFFICIENT_DEPTH` | Elbow flexion $\le 90^\circ$ at bottom inflection, straight spinal alignment maintained throughout |
| **Bicep Curl** | Shoulder-Elbow-Wrist (Elbow Flexion), Hip-Shoulder-Elbow (Upper Arm Sway) | `ELBOW_SWAY` (elbow drifting anteriorly/posteriorly), `TRUNK_SWAY` (torso swinging for momentum), `INCOMPLETE_RANGE_OF_MOTION` | Forearm flexion $\le 45^\circ$ at top, controlled extension $\ge 150^\circ$ at bottom |
| **Lunge** | Lead Knee Flexion, Trailing Knee Flexion, Torso-Vertical Angle | `FRONT_KNEE_OVER_TOES` (excessive forward tibia translation), `TORSO_LEAN` (excessive forward torso pitch), `INSUFFICIENT_DEPTH` | Lead knee angle $\approx 90^\circ$ with upright torso alignment |
| **Shoulder Press** | Elbow Extension Angle, Shoulder Abduction, Lumbar Spine Angle | `ARCHED_BACK` (lumbar hyperextension $> 15^\circ$), `INCOMPLETE_LOCKOUT` (arms not fully extended overhead), `ASYMMETRICAL_PRESS` | Full overhead elbow lockout with neutral spine alignment |

---

## How It Works

The real-time analysis pipeline processes video data entirely through client-side feature extraction and server-side kinematic evaluation:

```
[ User Webcam ]
       │
       ▼
1. Video Capture (Browser HTMLVideoElement @ ~30 FPS)
       │
       ▼
2. Pose Landmark Extraction (MediaPipe Pose Client-Side WASM / WebGL)
   - Extracts 33 normalized 3D keypoints (x, y, z, visibility)
   - Discards raw pixel frames; video never leaves the client
       │
       ▼
3. WebSocket Transmission (Authenticated ws://.../api/v1/ws/stream?token=<JWT>)
   - Serialized JSON pose_frame payload (<1 MB bounded payload)
       │
       ▼
4. Landmark Ingestion & Geometry Buffering (FastAPI Backend)
   - Validates message schema and parses coordinates into NumPy (33, 4) float32 buffer
       │
       ▼
5. Kinematic Analysis & State Machine Evaluation (ai/exercises/)
   - Computes Euclidean joint angles with zero-division and NaN protection
   - Advances FSM: READY ──► CONCENTRIC ──► PEAK ──► COMPLETE
       │
       ▼
6. Biomechanical Form Fault Scoring
   - Compares joint angles against biomechanical thresholds
   - Calculates rep score: Form Score = max(0, 100 - Penalties)
       │
       ▼
7. Real-Time Feedback Dispatch (<15ms server turn-around)
   - Returns analysis_result JSON: rep count, form score, active stage, corrective cues
       │
       ▼
8. Set Completion & Persistence (On finish_session / stop_session)
   - Commits set aggregates, reps, joint angles, and fault records to PostgreSQL
       │
       ▼
9. Asynchronous AI Coaching (On-demand post-workout)
   - Passes verified database telemetry to local Ollama LLM or deterministic fallback
```

---

## Architecture

The application adopts a decoupled, client-server hybrid architecture separating real-time geometric evaluation from transactional storage and qualitative LLM feedback.

```mermaid
flowchart TD
    subgraph Client ["Client Browser (Next.js 15 App Router)"]
        UI[User Interface & HUD Overlay]
        Cam[Camera Stream 30 FPS]
        MP[MediaPipe Pose Detector]
        WSClient[WebSocket Client Hook]
        Cam --> MP
        MP --> WSClient
        WSClient --> UI
    end

    subgraph Backend ["Application Server (FastAPI / Python 3.11)"]
        WSRoute["WebSocket Handler (/api/v1/ws/stream)"]
        APIRoute["REST API Handlers (/api/v1/*)"]
        SecMiddleware["Security & Rate Limiting Middleware"]

        subgraph CoreAI ["Kinematic & ML Engine (ai/)"]
            Buffer["NumPy (33, 4) Buffer"]
            FSM["Exercise State Machines (5 Exercises)"]
            Angles["Joint Angle Calculators"]
            MLInference["BaseAIInferenceService (PyTorch / Heuristic)"]
        end

        subgraph Services ["Service Tier"]
            AuthSvc[AuthService]
            WorkoutSvc[WorkoutService]
            PersonSvc[PersonalizationService]
            CoachSvc[CoachService]
        end

        SecMiddleware --> APIRoute
        APIRoute --> Services
        WSRoute --> Buffer
        Buffer --> Angles
        Angles --> FSM
        FSM --> MLInference
    end

    subgraph Storage ["Persistence Tier (PostgreSQL 15)"]
        DB[(PostgreSQL Database)]
        Alembic[Alembic Migrations 001-004]
        Services --> DB
    end

    subgraph LLM ["AI Coaching Subsystem"]
        CoachSvc --> Ollama["Local Ollama Service (llama3.2)"]
        CoachSvc --> Fallback["Deterministic Fallback Coach"]
    end

    WSClient <-->|Bi-directional Telemetry Stream| WSRoute
    UI <-->|HTTP REST / JWT Bearer| SecMiddleware
```

### Architectural Tiers

1. **Client Tier (`frontend/`)**: Next.js 15 standalone application with React 19, TypeScript, and Tailwind CSS. Manages webcam lifecycle via `getUserMedia`, runs MediaPipe Pose client-side, renders real-time HUD overlays, and connects via authenticated WebSockets and REST APIs.
2. **API & Routing Tier (`backend/app/api/v1/`)**: FastAPI routers validating incoming requests using Pydantic v2 schemas, enforcing sliding-window rate limiting, and decoding JWT access tokens.
3. **Domain Service Tier (`backend/app/services/`)**: Orchestrates business workflows including workout management, historical aggregation, user personalization, and AI coaching.
4. **Kinematic & AI Subsystem (`ai/`)**: Standalone computational engine containing vector geometry functions, exercise state machines, feature extractors, and ML sequence evaluators. Decoupled from web frameworks and databases.
5. **Persistence Tier (`backend/app/repositories/`, `alembic/`)**: SQLAlchemy 2.0 async repositories interacting with PostgreSQL 15, structured across versioned migrations with composite performance indexes.
6. **AI Coach Subsystem (`backend/app/services/coach_service.py`)**: Asynchronous evaluation pipeline consuming authoritative database telemetry to interface with local Ollama LLMs or rule-based fallback providers.

For comprehensive architectural specifications and diagrams, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/diagrams/](docs/diagrams/).

---

## Technology Stack

| Layer | Technology | Version / Specification | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | Next.js | 15 (App Router), React 19 | Client application, routing, and UI presentation |
| **Frontend Language** | TypeScript | Strict Mode (`tsc --noEmit`) | Type safety across client components and API contracts |
| **Styling & Icons** | Tailwind CSS, Lucide Icons | Modern dark-theme aesthetic | Responsive layout, telemetry HUD, and iconography |
| **Client State** | Zustand | Single-store reactive state | Active workout state, HUD telemetry, and camera status |
| **Computer Vision** | MediaPipe Pose | 33 3D Normalized Landmarks | Client-side in-browser body tracking via WASM/WebGL |
| **Backend Framework** | FastAPI | 0.115+ (Python 3.11+) | Async REST API, WebSocket routing, and ASGI server |
| **Data Validation** | Pydantic | v2 | Request/response validation, bounds checking, and DTO schemas |
| **ORM & Database** | SQLAlchemy, asyncpg | 2.0 (AsyncSession), PostgreSQL 15 | Relational persistence, composite indexing, and transactions |
| **Schema Migrations** | Alembic | Revisions 001–004 | Version-controlled database schema migrations |
| **Mathematical Compute** | NumPy | Float32 pre-allocated arrays | Vector geometry, joint angle trigonometry, and buffer reuse |
| **Machine Learning** | PyTorch, scikit-learn | Temporal sequence & classical models | Experimental sequence classification with fallback architecture |
| **Local LLM Engine** | Ollama | `llama3.2` | Local, offline-capable post-workout qualitative coaching |
| **Testing Tools** | pytest, pytest-asyncio, tsx | Unit, integration, and performance suites | Automated verification across backend, AI, and frontend |
| **Linters & SAST** | Ruff, ESLint, Bandit, pip-audit | Automated code quality & security | Static analysis, vulnerability auditing, and formatting |
| **Containerization** | Docker, Docker Compose | Multi-stage Dockerfiles | Multi-service orchestration and non-root execution |
| **CI/CD** | GitHub Actions | 5 automated quality jobs | Continuous integration on push and pull requests |

---

## AI / ML Components

The platform combines deterministic mathematical kinematics, experimental machine learning classifiers, and grounded local language models:

### 1. Computer Vision & Landmark Geometry
- **Landmark Extraction**: Evaluates 33 body keypoints with normalized coordinates $(x, y, z)$ and visibility scores.
- **Euclidean Vector Trigonometry**: Joint angles are calculated in `ai/geometry/angles.py` using 2D and 3D vector dot products:
  $$\theta = \arccos\left(\frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}\right)$$
- **Numerical Robustness**: Angle calculations explicitly guard against zero-length vectors and apply `np.clip(cos_theta, -1.0, 1.0)` before computing `arccos`, preventing `NaN` and `ZeroDivisionError` edge cases.

### 2. Exercise State Machines & Biomechanical Rules
- **Finite State Machine (FSM)**: Each exercise implements an independent FSM tracking four primary stages:
  - `READY`: Athlete is in starting position; joint angles meet initial extension bounds.
  - `CONCENTRIC`: Movement initiates and traverses past the inflection threshold.
  - `PEAK`: Maximum inflection reached (e.g. bottom of squat, lowest point of push-up).
  - `COMPLETE`: Athlete returns to full starting extension; repetition count increments.
- **Hysteresis Guard Bands**: Directional thresholds prevent noisy frame fluctuations from double-counting repetitions.
- **Form Evaluation**: Deviations from target kinematic ranges deduct points from an initial base score of 100 per rep.

### 3. Machine Learning Subsystem
- **Feature Pipeline**: Extracts 73 kinematic features per frame, including normalized coordinates, inter-joint distances, joint angles, and frame-to-frame velocity vectors.
- **Temporal Windows**: The temporal architecture (`ai/classifier/temporal_pipeline.py`) segments movements into sliding windows of 30 frames.
- **Transparent Fallback Mode**: The backend utilizes a decoupled `BaseAIInferenceService`. When trained model weights (`models/exercise_classifier.joblib` or `models/temporal_exercise_classifier.pt`) are not loaded on disk or are undergoing evaluation, the engine operates via a deterministic heuristic classifier. It explicitly returns `is_stub=True` and `model_info="heuristic_fallback_stub"` rather than fabricating simulated probabilities.
- **Non-Medical Boundary**: The ML and kinematic algorithms are strictly designed for recreational exercise tracking and athletic form feedback; they are not certified for medical diagnosis, clinical rehabilitation, or injury prevention.

### 4. AI Coach
- **Grounded Context**: The AI Coach operates exclusively after a workout session concludes. It consumes an authoritative `CoachContext` constructed directly from verified database records (reps, form scores, tempo, detected fault counts). **Zero raw video frames, images, or raw landmark coordinates are sent to the LLM.**
- **Local Ollama Integration**: Connects over HTTP to a local Ollama instance running `llama3.2`, ensuring user workout data remains private and local without external cloud API dependencies.
- **System Prompt Guardrails**: Strict prompt instructions prohibit fabricating workout statistics, altering recorded numerical counts, or dispensing medical advice.
- **Strict Output Validation**: Responses are validated against the `CoachStructuredOutput` Pydantic schema (summary, strengths, areas to improve, next session focus).
- **Deterministic Offline Fallback**: If Ollama is offline, unreachable, or times out (>30s), the `DeterministicFallbackCoachProvider` automatically derives structured recommendations from recorded fault codes with zero latency.

---

## Backend Architecture

The backend is built with FastAPI and Python 3.11+, following a four-tier architecture:

- **Presentation / API Tier (`backend/app/api/v1/`)**: REST and WebSocket route handlers managing request lifecycle, input validation, response serialization, and status codes.
- **Domain Service Tier (`backend/app/services/`)**: Encapsulates core application logic, transaction coordination, workout lifecycle management, and rate limiting.
- **Kinematic & AI Tier (`ai/`)**: Stateless computational modules evaluating joint trigonometry, exercise state machines, and sequence inferences.
- **Persistence Tier (`backend/app/repositories/`)**: Async SQLAlchemy 2.0 query repositories isolating database operations and relationship loading.

### Core Capabilities
- **REST Endpoints**: Comprehensive resource management for authentication, user profiles, workout sessions, exercise sets, repetition metrics, and longitudinal analytics.
- **Database Migrations**: Version-controlled Alembic migrations (`001_initial_schema` through `004_add_performance_indexes`) supporting SQLite for rapid local testing and PostgreSQL for production.
- **Eager Loading Optimization**: Repository queries employ SQLAlchemy `selectinload` to fetch nested relationships (`Workout` $\rightarrow$ `ExerciseSession` $\rightarrow$ `ExerciseResult` $\rightarrow$ `FormIssue`) in single optimized round-trips, eliminating N+1 query patterns.
- **Interactive API Documentation**: Swagger UI mounted at `/api/v1/docs` (with root redirect from `/docs`) and ReDoc mounted at `/api/v1/redoc` (with root redirect from `/redoc`).

For the complete endpoint specification, see [docs/API.md](docs/API.md).

---

## Real-Time WebSocket Pipeline

The real-time streaming pipeline handles continuous frame evaluations over an authenticated WebSocket connection (`/api/v1/ws/stream`):

1. **Authentication Handshake**: The client establishes a WebSocket connection supplying a signed JWT in the query parameter (`?token=<JWT>`). The backend validates the signature, expiration, and active status of the user; invalid tokens are rejected with WebSocket close code `1008 (Policy Violation)`.
2. **Payload Protection**: Incoming messages are capped at 1 MB (`WEBSOCKET_MAX_MESSAGE_SIZE`). Malformed JSON payloads or non-conforming messages return structured error packets without severing the connection.
3. **Zero Database I/O During Streaming**: Landmark frames are processed entirely in memory. Database writes are deferred until set completion (`stop_session`) or workout termination (`finish_workout`), ensuring sub-millisecond per-frame turn-around.
4. **Pre-Allocated Geometry Buffers**: Coordinates are parsed directly into pre-allocated NumPy `(33, 4)` float32 arrays, eliminating dynamic memory allocation and Python garbage collection pauses during active sets.
5. **Real-Time Telemetry Packets**: The server returns an `analysis_result` JSON packet containing the active repetition count, current form score, movement phase, joint angles, and real-time corrective cues.

---

## Authentication & Security

Security hardening was verified during Phase 19 audits and is documented in [docs/SECURITY.md](docs/SECURITY.md):

- **Password Hashing**: User passwords are encrypted with salted `bcrypt` over 12 computation rounds. Password hashes are excluded from all API response models.
- **JWT Cryptography**: Signed using HMAC-SHA256 (`HS256`). Algorithm confusion attacks are blocked by explicitly restricting decoding algorithms to `[settings.JWT_ALGORITHM]`.
- **Resource Ownership Verification**: Multi-tenant authorization checks verify that `Workout.user_id == current_user.id` on all mutating and data-retrieval routes, preventing Insecure Direct Object References (IDOR). Violations return `403 Forbidden` without leaking resource state.
- **Sliding-Window Rate Limiting**: In-memory rate limiting mitigates brute-force and resource-exhaustion attacks on sensitive endpoints:
  - User Registration: 5 requests / min per IP
  - User Login: 10 requests / min per IP
  - AI Coach Generation: 10 requests / min per IP
  - WebSocket Connections: 30 connections / min per IP
- **HTTP Security Headers Middleware**: Injects defensive browser headers on every response:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(self)`
  - `Content-Security-Policy`
- **Production Secret Validation**: In `production` mode, `validate_production_security()` verifies that `JWT_SECRET_KEY` is not set to any known default key and is at least 32 characters long.
- **Least-Privilege Docker Containers**: Containers run with `security_opt: [no-new-privileges:true]`. The backend executes as non-root `appuser` (UID 10001), and the frontend executes as non-root `nextjs` (UID 1001).
- **Network Isolation**: PostgreSQL (`5432`) and Ollama (`11434`) ports are bound strictly to host loopback (`127.0.0.1`) in Docker Compose, preventing public exposure.
- **Static Security & Dependency Auditing**: Bandit SAST scanner identified 0 medium/high-severity issues across 10,500+ lines of Python code; `pip-audit` detected 0 known vulnerabilities in production dependencies.

### Known Security Constraints
- **In-Memory Rate Limiting**: The sliding-window rate limiter runs in single-instance memory. Horizontally scaled deployments across multiple server replicas require a centralized distributed cache (e.g. Redis).
- **WebSocket Query Parameter Tokens**: Standard browser WebSocket APIs do not support custom request headers during handshakes, requiring JWT tokens to be passed via query string. Transport Layer Security (WSS / HTTPS) is required in production to protect tokens from proxy logging.

---

## Performance

Runtime latency and throughput metrics were empirically measured on local developer hardware using the automated benchmark suite in [tests/unit/test_performance_benchmarks.py](tests/unit/test_performance_benchmarks.py):

| Benchmark Description | Workload / Dataset | Measured Latency | Engineering SLA Target |
| :--- | :--- | :--- | :--- |
| **Pose Frame Parsing & Squat Analysis** | 100 consecutive landmark frames through parser and squat FSM | **Average: 0.332 ms** / frame<br>**P95: 0.535 ms** / frame<br>**Max: 3.670 ms** / frame | $< 10.0\text{ ms}$ SLA<br>*(Well under 33.3 ms budget for 30 FPS)* |
| **Batch Sequence Inference Throughput** | 16 sequence windows (30 frames $\times$ 33 keypoints) via fallback classifier | **Total: 2.007 ms**<br>(**0.125 ms** / window) | $< 50.0\text{ ms}$ SLA |
| **Personalization Trends Database Query** | 10 historical workouts with full sessions, rep telemetry, and fault records | **37.503 ms** total execution | $< 100.0\text{ ms}$ SLA |

> **Note on Benchmark Environment**: Figures represent local benchmarks measured on developer workstations during test suite execution. They reflect algorithm and query efficiency under test conditions and should not be construed as cloud service level guarantees.

---

## Testing & Quality

The codebase enforces strict quality gates across automated testing, static analysis, type checking, and container configuration:

- **Backend Test Suite (pytest)**: **306 passed** tests across unit, integration, security, and performance test suites.
- **Backend Code Coverage**: **87.25%** overall coverage across `backend` and `ai` modules, exceeding the mandatory $\ge 80\%$ CI threshold.
- **Frontend Test Suite (tsx / Node.js test runner)**: **33 passed** tests covering UI components, user flows, and error handling.
- **TypeScript Type Safety**: 0 errors verified via `npx tsc --noEmit`.
- **Python Linting & Formatting**: 0 errors or warnings verified via `ruff check .`.
- **Frontend Linting**: 0 warnings or errors verified via `npm run lint` (`next lint`).
- **Production Build**: Clean compilation of 10 static and prerendered routes via `npm run build`.
- **Database Migration Cycle**: Full reversible migration verification: `upgrade head` $\rightarrow$ `downgrade -1` $\rightarrow$ `upgrade head`.
- **Static Application Security Testing**: 0 alerts via `bandit -r backend/ ai/ -ll`.
- **Dependency Auditing**: 0 known vulnerabilities verified via `pip-audit -r backend/requirements.txt`.
- **Docker Compose Syntax**: Verified via `docker compose config --quiet`.
- **Continuous Integration**: Multi-job GitHub Actions pipeline executing all verification steps on every push and pull request.

For detailed test methodology, see [docs/TESTING.md](docs/TESTING.md) and [docs/CI_CD.md](docs/CI_CD.md).

---

## Project Structure

```
ai-gym-trainer/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated 5-job GitHub Actions CI pipeline
├── ai/                            # Computer Vision & Biomechanics Engine
│   ├── classifier/                # Sequence classifiers & feature extractors
│   ├── exercises/                 # Exercise state machines (Squat, Pushup, Curl, Lunge, Press)
│   ├── geometry/                  # Vector trigonometry, angles, and metrics
│   ├── pose/                      # MediaPipe pose detector & landmark parser
│   └── tracker/                   # Angle tracking & velocity calculations
├── alembic/                       # Database migration scripts (001 to 004)
│   └── versions/                  # Revision files for schema evolution
├── backend/                       # FastAPI application backend
│   ├── app/
│   │   ├── api/v1/                # Route handlers (auth, workouts, coach, ws, profile, health)
│   │   ├── core/                  # Config, database engine, rate limiting, security headers
│   │   ├── models/                # SQLAlchemy ORM models (User, Workout, ExerciseSession, etc.)
│   │   ├── repositories/          # Database query repositories with eager loading
│   │   ├── schemas/               # Pydantic v2 validation DTOs
│   │   ├── services/              # Domain business services (Auth, Coach, Personalization, etc.)
│   │   └── main.py                # ASGI application factory & middleware setup
│   ├── requirements.txt           # Production backend dependencies
│   └── requirements-dev.txt       # Development & test dependencies
├── docker/                        # Production container definitions
│   ├── backend.Dockerfile         # Multi-layer Python 3.11 slim image
│   └── frontend.Dockerfile        # Multi-stage Node 20 alpine standalone image
├── docs/                          # Comprehensive technical documentation
│   ├── diagrams/                  # Mermaid architecture flow diagrams
│   ├── API.md                     # REST & WebSocket API specification
│   ├── ARCHITECTURE.md            # Comprehensive architecture guide
│   ├── CI_CD.md                   # CI/CD pipeline and quality gate specifications
│   ├── DEVELOPMENT.md             # Developer setup, testing, and contribution guide
│   ├── DOCKER.md                  # Docker architecture & deployment specifications
│   ├── PHASE_21_CODE_REVIEW.md    # Phase 21 comprehensive code review audit
│   ├── PHASE_22_RELEASE_READINESS.md # Phase 22 final release readiness report
│   ├── SECURITY.md                # Security architecture & hardening specifications
│   └── TESTING.md                 # Testing methodology & quality gates
├── frontend/                      # Next.js 15 App Router web application
│   ├── src/
│   │   ├── app/                   # App Router pages (login, register, workout, history, dashboard)
│   │   ├── components/            # UI components (CameraFeed, TelemetryHUD, TrendChart, etc.)
│   │   └── lib/                   # API client, WebSocket hook, types, and pose detector
│   └── package.json               # Frontend dependencies & scripts
├── models/                        # Model weights directory (.pt and .joblib artifacts)
├── scripts/                       # Maintenance and CI runner utility scripts
├── tests/                         # Automated test suite (306 tests)
│   ├── unit/                      # Geometry, state machines, ML, and benchmark unit tests
│   └── integration/               # Multi-tenant API, WebSocket, and database tests
├── docker-compose.yml             # Multi-service local & production composition
├── pyproject.toml                 # Ruff, pytest, and coverage configurations
└── README.md                      # Project documentation
```

---

## Getting Started

### Prerequisites
- **Python**: 3.11 or 3.12+
- **Node.js**: 18.x or 20.x+ & npm
- **PostgreSQL**: 15+ (or use local SQLite for rapid prototyping)
- **Ollama**: (Optional) For local LLM coaching (`ollama pull llama3.2`)
- **Docker & Docker Compose**: (Optional) For containerized deployment

---

### Option 1: Docker Compose Deployment (Recommended)

Run the complete multi-service stack with a single command:

```bash
# 1. Clone repository
git clone https://github.com/rayyanfaheem07/Ai-gym-trainer.git
cd ai-gym-trainer

# 2. Configure environment variables
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# 3. Build and launch services
docker compose up -d --build

# 4. Verify running container health
docker compose ps
```

Access the running services:
- **Frontend Application**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Interactive Docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) (or [http://localhost:8000/docs](http://localhost:8000/docs))
- **ReDoc Specification**: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc) (or [http://localhost:8000/redoc](http://localhost:8000/redoc))
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Option 2: Local Manual Setup

#### 1. Backend Setup

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

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Frontend Setup

In a separate terminal window:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

#### 3. Local Ollama LLM Setup (Optional)

```bash
# Install and run Ollama, then pull the lightweight llama3.2 model
ollama pull llama3.2
ollama serve
```

*(Note: If Ollama is not running, the application automatically engages the deterministic rule-based coach fallback with zero errors).*

---

## Environment Variables

Key configuration variables defined in `.env.example`:

| Variable | Description | Default / Example Value | Production Requirement |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Runtime environment (`development`, `production`, `testing`) | `development` | Set to `production` |
| `JWT_SECRET_KEY` | Secret key for signing HS256 JWT tokens | `dev-secret-key-change-in-production...` | **REQUIRED**: Must be 32+ char cryptographically random key |
| `DATABASE_URL` | Async database connection URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/aigym` | Set to production PostgreSQL URL |
| `POSTGRES_USER` | PostgreSQL username | `postgres` | Use secure credentials |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres_secure_password` | **REQUIRED**: Use strong password |
| `POSTGRES_DB` | PostgreSQL database name | `aigym` | Set project database name |
| `RUN_MIGRATIONS` | Apply Alembic migrations on startup | `true` | Recommended `true` |
| `OLLAMA_BASE_URL` | Ollama HTTP endpoint | `http://localhost:11434` (`http://ollama:11434` in Docker) | Point to running Ollama daemon |
| `OLLAMA_MODEL` | LLM model tag | `llama3.2` | Ensure model is pulled |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend REST API URL | `http://localhost:8000/api/v1` | Point to public backend URL |
| `NEXT_PUBLIC_WS_URL` | Frontend WebSocket streaming URL | `ws://localhost:8000/api/v1/ws/stream` | Point to public WebSocket URL |

---

## API Documentation

| Group | Method | Endpoint Path | Description | Access / Rate Limit |
| :--- | :--- | :--- | :--- | :--- |
| **Health** | `GET` | `/health` | Application, database, and system readiness | Public |
| **Auth** | `POST` | `/api/v1/auth/register` | Register new user account | Public (Rate-limited: 5/min) |
| **Auth** | `POST` | `/api/v1/auth/login` | Authenticate credentials & return JWT | Public (Rate-limited: 10/min) |
| **Auth** | `GET` | `/api/v1/auth/me` | Fetch authenticated user details | Bearer Token |
| **Profile** | `GET` | `/api/v1/profile` | Retrieve user fitness profile | Bearer Token |
| **Profile** | `PUT` | `/api/v1/profile` | Update user fitness profile | Bearer Token |
| **Workouts** | `POST` | `/api/v1/workouts/start` | Initialize new workout session | Bearer Token |
| **Workouts** | `POST` | `/api/v1/workouts/{id}/finish` | Conclude workout session & calculate totals | Bearer Token (Owned) |
| **Workouts** | `GET` | `/api/v1/workouts/{id}` | Detailed workout session telemetry | Bearer Token (Owned) |
| **Workouts** | `GET` | `/api/v1/workouts/history` | Paginated workout history | Bearer Token |
| **Analytics** | `GET` | `/api/v1/analytics/summary` | Aggregate lifetime volume and stats | Bearer Token |
| **Analytics** | `GET` | `/api/v1/analytics/exercises/{exercise}` | Exercise-specific history and personal bests | Bearer Token |
| **Analytics** | `GET` | `/api/v1/analytics/trends` | Time-series progression trends | Bearer Token |
| **Coach** | `POST` | `/api/v1/coach/session/{session_id}` | Generate AI coaching feedback | Bearer Token (Rate-limited: 10/min) |
| **Coach** | `GET` | `/api/v1/coach/session/{session_id}` | Retrieve cached coaching feedback | Bearer Token (Owned) |
| **Exercises** | `GET` | `/api/v1/exercises` | List supported exercise configurations | Public |
| **WebSocket** | `WS` | `/api/v1/ws/stream?token=<JWT>` | Real-time pose telemetry stream | JWT Query Param (Rate-limited: 30/min) |

For comprehensive payload schemas, response structures, and error codes, refer to [docs/API.md](docs/API.md).

---

## Limitations

The Real-Time AI Gym Trainer implements robust real-time kinematics and software architecture, but operates under explicit real-world boundaries documented throughout the project:

- **Monocular 2D/3D Depth Approximation**: Pose estimation runs on a single standard RGB webcam without depth sensors (LiDAR/ToF). Inferred 3D coordinates ($z$-axis) represent relative depth approximations; extreme camera angles, loose clothing, or poor lighting conditions can impair landmark fidelity.
- **Hardware Camera Dependency**: Live pose tracking requires an active camera device and browser permissions (`navigator.mediaDevices.getUserMedia`). Automated CI environments test the algorithms using synthetic 33-point fixtures and mock landmark sequences.
- **In-Memory Rate Limiting**: The sliding-window rate limiter is currently maintained in server process memory. Multi-replica or horizontally scaled deployments require a shared distributed cache (e.g. Redis) to synchronize rate limits across instances.
- **Browser WebSocket Handshake Authentication**: Standard browser WebSocket APIs do not support setting custom HTTP authorization headers. Tokens are transmitted via the query string (`?token=<JWT>`), making TLS encryption (`wss://`) essential in production to prevent token exposure in intermediary proxy access logs.
- **Local Ollama Inference Latency**: Ollama LLM execution speed depends entirely on host CPU/GPU hardware. To prevent frame drops, the AI Coach is completely decoupled from real-time exercise streaming, and the deterministic fallback activates if the model is slow or unreachable.
- **Client-Side CPU Utilization**: Running MediaPipe Pose at 1080p or 4K resolutions can lead to elevated CPU/GPU usage on low-end client laptops. A 720p stream is recommended for optimal performance.
- **Non-Medical / Non-Diagnostic Scope**: This software is an engineering demonstration and athletic tracking tool. It does not provide medical advice, clinical diagnostics, physical therapy rehabilitation, or injury prevention guarantees.

---

## Future Research & Extensions

Potential architectural extensions supported by the codebase design:
- **Distributed Rate Limiting**: Integrate a Redis-backed token bucket or sliding-window rate limiter for multi-replica Kubernetes deployments.
- **WebAssembly Landmark Smoothing**: Implement client-side One Euro or Kalman filtering in WebAssembly to reduce landmark jitter before WebSocket dispatch.
- **Multi-Camera Angle Fusion**: Support simultaneous front and lateral video streams to resolve joint occlusion during complex compound lifts.
- **Additional Exercise State Machines**: Extend `BaseExercise` to support additional movements such as Deadlift, Overhead Squat, and Plank.

---

## Documentation Index

Detailed architectural and operational documentation is available in the `docs/` directory:

| Document | Description |
| :--- | :--- |
| [docs/API.md](docs/API.md) | Comprehensive REST and WebSocket API specification |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technical system architecture, component boundaries, and data pipelines |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local development setup, coding standards, and contribution guide |
| [docs/TESTING.md](docs/TESTING.md) | Testing pyramid, assertion strategies, coverage reports, and QA gates |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat model, authentication, authorization, and Phase 19 security hardening |
| [docs/DOCKER.md](docs/DOCKER.md) | Multi-container Docker deployment guide, networking, and service configs |
| [docs/CI_CD.md](docs/CI_CD.md) | GitHub Actions CI/CD workflows and automated quality gates |
| [docs/PHASE_21_CODE_REVIEW.md](docs/PHASE_21_CODE_REVIEW.md) | Comprehensive repository code review and audit report |
| [docs/PHASE_22_RELEASE_READINESS.md](docs/PHASE_22_RELEASE_READINESS.md) | Final release readiness assessment and verification logs |
| [docs/diagrams/](docs/diagrams/) | Visual Mermaid architecture and sequence diagrams |
