# System Architecture: Real-Time AI Gym Trainer

## 1. High-Level Architecture Overview

The system is architected as a modular, 4-tier system designed for sub-millisecond local computation, strict separation of concerns, pluggable AI/CV subsystems, and multi-tenant security:

```
                    +------------------------------------------+
                    |           Client / REST Consumers        |
                    |         (Next.js / Browser / Native)     |
                    +--------------------+---------------------+
                                         | HTTP / Bearer Auth / WebSockets
                                         v
                    +------------------------------------------+
                    |          FastAPI API Layer (/api/v1/)    |
                    |  - /auth (register, login, me)           |
                    |  - /workouts (start, finish, list, get)  |
                    |  - /exercises (list supported exercises) |
                    |  - /analysis (structured frame/seq ML)   |
                    |  - /coach (LLM evaluation & insights)    |
                    |  - /health (system & DB health checks)   |
                    |  - /ws/stream (Real-time telemetry)      |
                    +--------------------+---------------------+
                                         |
                                         v
                    +------------------------------------------+
                    |              Service Layer               |
                    |  - AuthService (Registration & JWT auth) |
                    |  - WorkoutService (State machine & rules)|
                    |  - ExerciseService (Registry catalog)    |
                    |  - AnalysisService (Orchestrator)        |
                    |  - CoachService (LLM insights)           |
                    +--------------------+---------------------+
                         |                          |
                         v                          v
+------------------------------------+   +------------------------------------+
|         AI / CV Layer              |   |    Repository / Database Layer     |
| - AIInferenceService (Interface)   |   | - WorkoutRepository                |
| - TemporalExerciseInferenceEngine  |   | - UserRepository                   |
| - ExerciseInferenceEngine          |   | - SQLAlchemy 2.0 AsyncSession      |
| - ExerciseRegistry & Analyzers     |   | - Alembic Migration Engine         |
+------------------------------------+   +-----------------+------------------+
                                                           |
                                                           v
                                         +------------------------------------+
                                         |  PostgreSQL / SQLite Database      |
                                         |  - users (with bcrypt hash)        |
                                         |  - workouts                        |
                                         |  - exercise_sessions               |
                                         |  - exercise_results                |
                                         |  - form_issues                     |
                                         +------------------------------------+
```

---

## 2. Authentication & Authorization Security Architecture (Phase 9)

```
[ Client ] ──── POST /auth/register ────► [ AuthService ] ──── bcrypt.hashpw ───► [ PostgreSQL / DB ]
                                                                                   (Stores $2b$ hash)

[ Client ] ──── POST /auth/login ───────► [ AuthService ] ──── bcrypt.checkpw ──► [ JWT Engine ]
                                                                                   │
                                                                                   ▼ Issues HS256 Token
                                                                          (sub, email, exp, iat, iss)

[ Client ] ──── Bearer Token Header ────► [ get_current_user ] ── decode_access_token
                                                                   │
                                                                   ├─► Invalid/Expired? ──► 401 Unauthorized
                                                                   └─► Valid ──► Loads User & Enforces Ownership
```

### Security Principles & Threat Mitigation:
1. **Zero-Trust Client Identity**: Endpoints never trust client-supplied `user_id` in request payloads. The authenticated user ID is strictly derived from the decoded JWT claims via the `get_current_user` FastAPI dependency.
2. **Multi-Tenant Cross-User Isolation**: User A is strictly forbidden from accessing, modifying, finishing, or evaluating User B's workouts, exercise sessions, or telemetry. Server-side checks return `403 Forbidden` on unauthorized access attempts.
3. **Robust Password Hashing**: Passwords are never stored or logged in plaintext. Salted `bcrypt` (12 rounds) is enforced for hashing and constant-time verification.
4. **Safe Response Schemas**: Pydantic v2 schemas (`UserResponse`, `TokenResponse`) explicitly omit sensitive fields like `password` and `password_hash`.
5. **Standardized Token Expiration**: JWT tokens include standard claims (`sub`, `email`, `iat`, `exp`, `iss`) with configurable TTL (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## 3. Decoupled AI Integration Contract

The backend interacts with the machine learning and computer vision pipelines exclusively through the `BaseAIInferenceService` interface:

```python
class BaseAIInferenceService(ABC):
    @abstractmethod
    def predict_exercise(self, landmarks: np.ndarray, exercise_hint: str | None = None) -> dict[str, Any]:
        """Classifies movement sequence and computes calibrated probabilities."""
        pass

    @abstractmethod
    def is_model_available(self) -> bool:
        """Returns True if a real trained deep learning model is active."""
        pass
```

### ML Pipeline Resolution Order:
1. **Phase 7 PyTorch Temporal Model (`.pt`)**: Checks `models/temporal_exercise_classifier.pt`. If present and valid, activates `TemporalExerciseInferenceEngine`.
2. **Phase 6 Scikit-Learn Model (`.joblib`)**: Checks `models/exercise_classifier.joblib`. If present and valid, activates `ExerciseInferenceEngine`.
3. **Explicit Fallback / Stub**: When no trained weights are present on disk, the service operates transparently with `is_stub=True` and `model_info="heuristic_fallback_stub"` without fabricating ML confidence scores or false evaluation metrics.

---

## 4. Database Schema Hierarchy

The database schema reflects the true application entities managed through **Alembic**:

```
User (users)
  │ (id, email, password_hash, full_name, is_active, timestamps)
  │
  └── 1-to-many ──► Workout (workouts)
                      │ (id, user_id, status, started_at, ended_at, duration, calories, form_score)
                      │
                      └── 1-to-many ──► ExerciseSession (exercise_sessions)
                                          │ (id, workout_id, exercise_name, target/valid reps, scores)
                                          │
                                          └── 1-to-many ──► ExerciseResult (exercise_results)
                                                              │ (id, rep_number, is_valid, angles, faults)
                                                              │
                                                              └── 1-to-many ──► FormIssue (form_issues)
                                                                  (id, issue_code, severity, feedback)
```

- **Cascading Deletes**: Deleting a User or Workout automatically removes child sessions, rep records, and form deviation logs.
- **Async Execution**: Powered by `SQLAlchemy 2.0` with `asyncpg` (PostgreSQL) and `aiosqlite` (local development).
- **Alembic Migrations**: Fully versioned via `alembic upgrade head` and reversible with `alembic downgrade base`.

---

## 5. Real-Time WebSocket Streaming Architecture (Phase 10)

```
[ Browser / Webcam Client ]
         │
         │  1. WS Connect: /api/v1/ws/stream?token=<JWT>
         ▼
[ FastAPI WebSocket Layer ] ── authenticate_and_accept ──► [ JWT Decode & User Validation ]
         │                                                      │
         │ (Accept connection & send 'connected')               └─► Invalid? ──► Close (Code 1008)
         ▼
[ WebSocketService ]
         │
         ├──► 'ping' ───────────► Returns 'pong'
         │
         ├──► 'start_session' ──► Initializes WebSocketSessionTracker (In-Memory)
         │
         ├──► 'pose_frame' ─────► [ WebSocketSessionTracker ]
         │                           │
         │                           ▼
         │                        [ ExerciseRegistry / Analyzer ] (Squat, Push-up, Curl, Lunge, Press)
         │                           │
         │                           ▼
         │                        [ In-Memory Form & Rep State ] (Zero DB Writes)
         │                           │
         │                           ▼
         │                        Returns 'analysis_result' (<15ms)
         │
         └──► 'stop_session' ───► Aggregates Session Stats & Form Metrics
                                     │
                                     ▼ (If workout_id provided)
                                  [ WorkoutService.add_exercise_session ] ──► [ PostgreSQL / DB ]
```

### Real-Time Streaming Design Rules:
1. **Thin Route & Service Decoupling**: The route handler in `backend/app/api/v1/websocket.py` remains minimal, delegating all state tracking, analyzer routing, and JSON serialization to `WebSocketService` and `WebSocketConnectionManager`.
2. **In-Memory Biomechanics Pipeline**: Per-frame telemetry is evaluated entirely in memory. Frame processing latency stays under 15ms. Database writes are never performed per frame.
3. **Session Persistence Boundary**: Upon receiving `stop_session`, the tracker aggregates total reps, valid reps, form scores, and form fault history, executing a single batched database transaction if linked to an active `workout_id`.
4. **Resilience & Guardrails**: Messages are guarded against payload overflows (>1MB), malformed JSON, and invalid landmark coordinates, returning structured error packets without dropping connections or leaking server internals.

---

## 6. Next.js 15 Frontend Architecture (Phase 11)

```
[ Webcam MediaStream ]
          │ (HTMLVideoElement 30 FPS)
          ▼
[ BrowserPoseDetector ] (MediaPipe Pose 33 3D Keypoints)
          │
          ▼
[ useWebSocket Hook ] ─── ws://host/api/v1/ws/stream?token=<JWT>
          │ (Live Bidirectional Stream)
          ▼
[ LiveTelemetryOverlay HUD ]
  - Rep Count (Valid / Invalid)
  - Biomechanical Form Score Gauge
  - FSM Movement Stage (Standing, Descending, Bottom, Ascending, Completed Rep)
  - Joint Angles (Knee, Hip, Elbow, Shoulder)
  - Live Audio / Visual Coaching Cues
          │
          ▼ (On Stop Session)
[ SessionSummaryModal ] ──► POST /workouts/{id}/finish ──► Persists to PostgreSQL
```

### Frontend Architecture Guarantees:
1. **No Duplicated Business Logic**: All rep counting FSM transitions, Euclidean joint angle formulas, and form scoring rules execute strictly on the backend. The frontend acts purely as a telemetry capture and HUD rendering layer.
2. **Decoupled Pose Extraction**: The browser camera and MediaPipe landmark detection layer extract 33 points and stream them over the authenticated WebSocket, avoiding raw video streaming.
3. **Zero-Trust Token Management**: JWTs are kept in client memory / localStorage and attached as `Bearer` headers to REST calls and `?token=` query params to WebSockets. Secret keys are never bundled in frontend artifacts.
4. **Optimized Render Cycles**: High-frequency frame capture loops utilize `requestAnimationFrame` and React refs to prevent unnecessary component-wide re-renders.

---

## 7. Analytics & Workout History Architecture (Phase 12)

```
[ Frontend: /history & /dashboard ]
                  │
                  │ (HTTP GET with Bearer JWT)
                  ▼
[ Analytics API Layer ]
  - GET /api/v1/analytics/summary
  - GET /api/v1/analytics/exercises/{exercise}
  - GET /api/v1/analytics/trends
  - GET /api/v1/workouts/history?page=1&exercise=squat
                  │
                  ▼
[ AnalyticsService ] (Validation, Aliasing & Aggregation Business Logic)
                  │
                  ▼
[ AnalyticsRepository ]
  - SQL aggregate queries (SUM, COUNT, AVG, MAX)
  - Exercise joins across Workout, ExerciseSession, FormIssue
  - Chronological time-series filtering
                  │
                  ▼
[ PostgreSQL / SQLite Relational Database ]
  - workouts (status, started_at, ended_at, total_duration_sec, overall_form_score)
  - exercise_sessions (exercise_type, total_reps, valid_reps, avg_form_score)
  - form_issues (issue_type, severity, count)
```

### Analytics Guarantees & Constraints:
1. **100% Persisted Source of Truth**: All numbers (reps, durations, form scores, trends) originate directly from database queries. Zero client-side statistical fabrication or simulated data.
2. **Enforced User Isolation**: All repository queries include `Workout.user_id == user_id` conditions, strictly isolated by the JWT identity claim.
3. **Pure SVG Telemetry Charts**: Frontend visualizers (`PerformanceTrendChart`) render clean vector lines and area fills with zero external charting bloat, supporting multi-metric toggles (Form Score, Total Reps, Rep Accuracy %, Duration).
4. **Resilient Empty & Single-Point States**: Safe defaults and graceful UI fallback banners when an athlete has 0 or 1 session recorded.



