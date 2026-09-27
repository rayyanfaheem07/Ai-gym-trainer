# Development Guide: Real-Time AI Gym Trainer

This guide covers local development workflows, code standards, testing, database migrations, Docker workflows, and instructions for extending exercises, form rules, and AI Coach behaviors.

---

## 1. Repository Structure

```
ai-gym-trainer/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI: pytest, ruff, bandit, pip-audit, npm build/lint/test
├── ai/                            # Computer Vision & Machine Learning core
│   ├── classifier/                # Temporal & heuristic exercise classification
│   ├── exercises/                 # Exercise state machines (squat, pushup, curl, lunge, press)
│   ├── pose/                      # MediaPipe pose detector & landmark parser
│   └── tracker/                   # Biomechanical angle calculators & metrics
├── backend/                       # FastAPI backend
│   ├── alembic/                   # Database migrations (001 to 004)
│   ├── app/
│   │   ├── api/v1/                # API route handlers (auth, workouts, coach, ws, profile, etc.)
│   │   ├── core/                  # Configuration, database engine, rate limiting, security
│   │   ├── models/                # SQLAlchemy ORM models (User, Workout, ExerciseSession, etc.)
│   │   ├── repositories/          # Database query repositories
│   │   ├── schemas/               # Pydantic v2 validation DTOs
│   │   └── services/              # Domain business services (Auth, Coach, Personalization, etc.)
│   └── main.py                    # ASGI application entrypoint & middleware setup
├── docker/                        # Production Dockerfiles (backend.Dockerfile, frontend.Dockerfile)
├── docs/                          # Architecture, API, and development documentation
│   └── diagrams/                  # Mermaid architecture flow diagrams
├── frontend/                      # Next.js 15 App Router web application
│   ├── src/
│   │   ├── app/                   # App Router pages (login, register, workout, history, dashboard)
│   │   ├── components/            # UI components (CameraFeed, TelemetryHUD, TrendChart, etc.)
│   │   └── lib/                   # API clients, WebSocket hook, types, audio feedback
├── scripts/                       # Maintenance & evaluation helper scripts
├── tests/                         # Pytest test suite (unit, integration, performance)
├── docker-compose.yml             # Multi-service local & production composition
└── README.md                      # Project overview & quickstart
```

---

## 2. Local Development Environment

### Prerequisites
- **Python**: 3.11 or 3.12+ (tested on Python 3.11–3.13)
- **Node.js**: 18.x or 20.x+
- **PostgreSQL**: 15+ (or use local SQLite for rapid prototyping)
- **Ollama**: (Optional) For local LLM coaching (`ollama pull llama3.2`)

### Backend Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your local database URL and JWT secret
   ```
4. Run database migrations:
   ```bash
   alembic upgrade head
   ```
5. Start the backend development server:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
4. Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 3. Database Migrations (Alembic)

Database schema changes must be managed via Alembic:

### Creating a New Migration
```bash
alembic revision --autogenerate -m "describe_schema_change"
```
Always inspect the generated file in `backend/alembic/versions/` to verify that both `upgrade()` and `downgrade()` handle dialect differences cleanly.

### Applying Migrations
```bash
alembic upgrade head
```

### Reverting the Last Migration
```bash
alembic downgrade -1
```

---

## 4. Testing & Code Quality

### Running Backend Tests
```bash
# Run entire test suite
pytest

# Run with test coverage report
pytest --cov=backend --cov=ai --cov-report=term-missing --cov-fail-under=80

# Run specific performance benchmarks
pytest tests/unit/test_performance_benchmarks.py -v
```

### Running Backend Linters & Security Scanners
```bash
# Code formatting and lint checks
ruff check .

# Static Application Security Testing (SAST)
bandit -r backend ai -ll -ii

# Known vulnerability scan
pip-audit -r requirements.txt
```

### Running Frontend Tests & Checks
```bash
cd frontend

# Run Jest unit tests
npm test

# Run TypeScript typecheck
npx tsc --noEmit

# Run ESLint
npm run lint

# Build production bundle
npm run build
```

---

## 5. Docker Development Workflows

Run the complete multi-container stack locally with Docker Compose:

```bash
# Build and start all services (postgres, backend, frontend, ollama)
docker compose up -d --build

# Inspect running logs
docker compose logs -f backend

# Verify health status of all containers
docker compose ps

# Stop containers without losing data
docker compose down
```

---

## 6. How-To Guides

### 6.1 Adding a New Exercise
1. **Create the Exercise Analyzer**:
   Create a new file in `ai/exercises/<exercise_name>.py` extending `BaseExercise`. Implement:
   - Biomechanical landmark extraction (e.g., knee, hip, shoulder angles).
   - State machine stages (`READY` $\rightarrow$ `CONCENTRIC` $\rightarrow$ `PEAK` $\rightarrow$ `COMPLETE`).
   - Repetition validation and form fault rules.
2. **Register in Registry**:
   Open `ai/exercises/registry.py` and register the new class:
   ```python
   from ai.exercises.<exercise_name> import <ExerciseName>Exercise
   ExerciseRegistry.register("<exercise_name>", <ExerciseName>Exercise)
   ```
3. **Update Database Types**:
   Add the exercise name to `ExerciseType` in `backend/app/models/workout.py`.
4. **Update Frontend UI**:
   Add the exercise key and display metadata to the exercise selector in `frontend/src/app/workout/page.tsx`.
5. **Add Unit Tests**:
   Create `tests/unit/test_<exercise_name>_detector.py` validating inflection angles, rep count increments, and fault detection.

### 6.2 Modifying Form Rules & Fault Thresholds
1. Locate the exercise detector in `ai/exercises/<exercise_name>.py`.
2. Locate the form fault check method (e.g., `_check_form_faults(landmarks, angles)`).
3. Adjust the geometric angle threshold or add a new condition:
   ```python
   # Example: Adjusting knee valgus threshold
   if knee_angle < 15.0:
       faults.append(FormIssueData(issue_code="KNEE_VALGUS", severity=IssueSeverity.MODERATE, feedback_text="Push knees outward"))
   ```
4. Verify tests pass and form penalties decrement appropriately.

### 6.3 Modifying AI Coach Behavior
1. **Adjusting System Guardrails**:
   Open `backend/app/services/coach_provider.py` and update `OllamaCoachProvider.SYSTEM_PROMPT`. Ensure you preserve the fact-protection rules prohibiting hallucination of unrecorded metrics.
2. **Customizing Fallback Cues**:
   Update `DeterministicFallbackCoachProvider.generate_coaching()` in `coach_provider.py` to refine the rule-based cues mapped to specific biomechanical fault codes.
3. **Modifying Output Fields**:
   If adding new coaching fields:
   - Update `CoachStructuredOutput` schema in `backend/app/schemas/coach.py`.
   - Update `coaching_feedbacks` table in `backend/app/models/workout.py`.
   - Generate and apply an Alembic migration (`alembic revision --autogenerate -m "add_field_to_coaching_feedback"`).
