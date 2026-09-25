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

---

## 8. Performance Engineering Architecture (Phase 15)

```
[ Browser / Camera HUD ]
  │
  ├─► Frame Throttling (~30 FPS / 33.3ms) & Concurrency Guard (skip in-flight detect)
  │
  └─► WS /api/v1/ws/stream (Pre-allocated NumPy buffer, zero per-frame DB writes)
        │
        ▼
[ Server Frame Pipeline ]
  ├─► Pre-allocated (33, 4) Float32 Landmark Buffer
  ├─► Frame Resolution Clamping (1280x720)
  ├─► torch.inference_mode() + Vectorized Batched Forward Passes
  ├─► Zero DB writes per frame / Zero LLM calls in frame loop
  └─► Latency Telemetry (latency_ms) returned in AnalysisResultResponse
        │
        ▼
[ Database Query Optimization ]
  ├─► Composite Index: workouts(user_id, started_at)
  ├─► Composite Index: exercise_sessions(workout_id, session_order)
  ├─► Composite Index: exercise_results(exercise_session_id, rep_number)
  ├─► Composite Index: form_issues(exercise_result_id, issue_code)
  └─► Personalization Trends: Targeted SQL aggregations replacing deep eager-loads
```

### 8.1 Key Bottlenecks Identified
1. **Landmark Array Allocation Thrashing**: The WebSocket landmark conversion constructed nested Python lists and instantiated fresh `np.array` instances on every frame (30–60+ times/sec per client).
2. **Uncapped Client Frame Dispatch**: High-refresh browser monitors (60Hz, 120Hz, 144Hz) queued concurrent `detect()` executions and saturated WebSocket channels.
3. **Deep Eager Loading in Personalization**: `PersonalizationService.calculate_personal_trends` loaded a user's entire workout history using 3-level deep `selectinload` across all sessions, reps, and form faults.
4. **Sequential ML Forward Passes**: `predict_batch` iterated sequential single-window inferences rather than performing a single batched tensor evaluation.
5. **Missing Multi-Column Database Indexes**: High-frequency ordered queries on user workout history, session ordering, and rep telemetry scanned unindexed secondary columns.

### 8.2 Optimizations Implemented
1. **Pre-allocated NumPy Landmark Buffering**:
   - `parse_landmarks_to_numpy`: Pre-allocates `np.empty((33, 4), dtype=np.float32)` and fills by index.
   - `ai/pose/detector.py`: Normalized landmark and 3D world landmark extraction optimized with pre-allocated buffers.
2. **Client-Side Frame Throttling & In-Flight Guards**:
   - `frontend/src/app/workout/page.tsx`: Throttled to ~30 FPS (`TARGET_INTERVAL_MS = 1000 / 30`) with an `isProcessingRef` guard, preventing overlapping MediaPipe detections and unnecessary React component re-renders.
3. **PyTorch ML Inference Optimization**:
   - `ai/classifier/temporal_inference.py`: Switched to `torch.inference_mode()` (disabling autograd view tracking and version counters).
   - Vectorized `predict_batch`: Combines sequences into a single `(B, W, F)` tensor evaluated in one forward pass.
   - Replaced `np.array(window)` copies with zero-copy `np.asarray(window)`.
4. **Database Performance & Composite Indexes (Migration 004)**:
   - Created `004_add_performance_indexes.py` establishing:
     - `ix_workouts_user_started` on `workouts(user_id, started_at)`
     - `ix_exercise_sessions_workout_order` on `exercise_sessions(workout_id, session_order)`
     - `ix_exercise_results_session_rep` on `exercise_results(exercise_session_id, rep_number)`
     - `ix_form_issues_result_code` on `form_issues(exercise_result_id, issue_code)`
   - Verified reversible migration cycle: `upgrade -> downgrade -> upgrade`.
5. **Targeted Aggregation for Personalization Trends**:
   - Replaced deep recursive `selectinload` of all lifetime results with targeted join queries for recurring issues and lifetime metrics.
6. **Configurable Runtime Settings & Observability**:
   - Added `REALTIME_PROCESSING_FPS`, `FRAME_MAX_WIDTH`, `FRAME_MAX_HEIGHT`, `WEBSOCKET_MAX_MESSAGE_SIZE` in `Settings` and `.env.example`.
   - Added `latency_ms` telemetry to `AnalysisResultResponse`.

### 8.3 Benchmark Results (Measured)
Measured using `tests/unit/test_performance_benchmarks.py` on local test environment:
- **Pose Analysis Latency** (100 frames through landmark parsing and squat analyzer):
  - Average: **0.332 ms** / frame
  - P95: **0.535 ms** / frame
  - Max: **3.670 ms** / frame
  *(Real-time 30 FPS budget is 33.3 ms; 0.332 ms utilizes < 1% of frame budget)*
- **ML Classifier Batch Inference Throughput** (16 sequence windows):
  - Total: **2.007 ms** (0.125 ms / window)
- **Personalization Trends Database Query** (10 historical workouts with full session/rep/fault data):
  - Execution time: **37.503 ms** (well within sub-100ms SLA)

### 8.4 Expected / Theoretical Improvements
- **Network & Client CPU Utilization**: Capping high-refresh displays from 120Hz/144Hz to 30 FPS yields a theoretical ~75% reduction in outbound WebSocket message traffic and client detection overhead on gaming/high-refresh monitors.
- **Database Scalability**: As user history grows beyond 50+ workouts, the targeted aggregation query avoids loading thousands of ORM objects into Python memory, shifting memory scaling from O(Workouts * Reps) to O(Recent_Workouts).

### 8.5 Known Limitations
- When browser webcam resolution is set to 4K (3840x2160), MediaPipe JavaScript detection in the browser consumes noticeable client CPU; client-side downscaling or lower webcam constraints (e.g. 720p) are recommended for lower-end hardware.
- Offline fallback AI coach is instantaneous, but when connected to a local Ollama instance with large models (e.g., 8B/13B parameter LLMs), response latency is bounded by the host GPU/CPU inference speed, which is why AI Coach runs asynchronously outside the real-time frame loop.



