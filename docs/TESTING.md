# Quality Assurance & Testing Architecture

Comprehensive documentation of the testing pyramid, verification strategies, security isolation, AI fact-protection, and performance benchmarks for the Real-Time AI Gym Trainer project.

---

## 1. Test Architecture & Pyramids

The testing suite enforces a clear separation of concerns across unit tests, integration tests, end-to-end workflows, and performance benchmarks:

```
                  ┌───────────────────────────────┐
                  │    E2E User Flows (Node TS)   │
                  │   33 Frontend Tests (tsx)     │
                  ├───────────────────────────────┤
                  │    Integration Tests (Pytest) │
                  │  WebSocket & Multi-Tenant API │
                  ├───────────────────────────────┤
                  │    Unit Tests (Pytest & Torch)│
                  │ CV, Geometry, FSMs, ML Engine │
                  ├───────────────────────────────┤
                  │ Performance Benchmarks & SLA  │
                  │  NumPy, GRU/LSTM, DB Latency  │
                  └───────────────────────────────┘
```

---

## 2. Test Categories

### Unit Tests (`tests/unit/`)
- **CV & Geometry Edge Cases** (`test_cv_geometry_edge_cases.py`):
  - Robustness against NaN, Inf, zero-length vectors, collinear angles, and extreme coordinate scaling (`1e8`).
  - Landmark extraction with incomplete lists, missing attributes, and zero-height torso normalization.
  - MediaPipe detector safety on empty (`0x0`) and single-pixel frames.
- **Biomechanical State Machines** (`test_exercise_state_machine_edges.py`, `test_squat_analysis.py`, etc.):
  - Full repetition cycles for Squat, Push-up, Bicep Curl, Lunge, and Shoulder Press.
  - Detection of incomplete repetitions (reversals before depth/extension).
  - Hysteresis guard bands preventing micro-jitter state oscillation.
  - Robustness to Gaussian landmark noise, time jumps, and `reset()` behaviors.
- **ML & Temporal Inference Robustness** (`test_ml_robustness.py`, `test_ml_temporal.py`):
  - CPU inference verification without gradient calculation (`torch.inference_mode`).
  - Batch inference vs single inference semantic consistency.
  - Graceful fallback to `"other"` (with 0.0 confidence) on empty sequences, malformed inputs, or unloaded models.
- **AI Coach Adversarial Fact-Protection** (`test_coach_fact_protection.py`):
  - Adversarial LLM hallucination resistance (invented reps, form scores, PRs, or calories).
  - Verification that database telemetry (`Workout`, `ExerciseSession`, `ExerciseResult`) remains immutable.
  - Fallback triggers on Ollama timeouts or malformed JSON payloads.
- **Database Cascades & Transactions** (`test_database_integrity.py`):
  - 4-tier cascade deletion: `Workout -> ExerciseSession -> ExerciseResult -> FormIssue`.
  - Transaction atomicity and rollback on simulated mid-flight exceptions.
- **Performance Benchmarks** (`test_performance_benchmarks.py`):
  - Frame parsing and analyzer execution latency (<10ms SLA).
  - Batched fallback inference throughput.
  - Multi-workout longitudinal personalization trends calculation (<100ms SLA).

### Integration Tests (`tests/integration/`)
- **Multi-Tenant User Isolation** (`test_user_isolation_security.py`):
  - Direct API access and resource-ID manipulation (IDOR) prevention.
  - User A is rejected with `403 Forbidden` when accessing User B's workouts, history, or coach evaluations.
  - Analytics and profile endpoints strictly scoped to authenticated user context.
- **WebSocket Streaming Reliability** (`test_websocket_reliability.py`, `test_websocket.py`):
  - Handshake authentication with query-parameter JWTs (rejects missing, invalid, or expired tokens with close code 1008).
  - Oversized payload rejection (>1MB) with `PAYLOAD_TOO_LARGE` error packet.
  - Malformed landmark handling (strings, NaNs, missing coordinates) without session drops.
  - Rapid 40+ frame bursts without connection drops.
  - Verification that frames are processed in-memory without per-frame database writes.
  - Guarantee that Ollama is never invoked inside the frame processing loop.

### Frontend Workflows (`frontend/src/__tests__/`)
- **Quality & Workflows** (`quality_and_edge_cases.test.ts`, `ui_and_workflows.test.ts`):
  - Complete user flow: Registration -> Login -> Profile Config -> Workout Start -> Telemetry -> Rep Counting -> Completion -> History -> Analytics -> Personalized Coach feedback.
  - Camera permission denial and hardware failure error formatting.
  - Resource disposal on component unmount: stopping media tracks, closing WebSocket, clearing intervals, and cancelling animation frame loops.
  - WebSocket error packet parsing and token expiration redirection.

---

## 3. Coverage Results

### Backend & AI Test Coverage
- **Total Tests**: 280 tests
- **Passing**: 280 (100%)
- **Failures**: 0
- **Total Code Coverage**: **87%** across `backend` and `ai` modules.
  - Key Modules:
    - `ai/geometry/angles.py`: 100%
    - `ai/geometry/metrics.py`: 100%
    - `ai/exercises/`: 94% – 100%
    - `ai/classifier/synthetic.py`: 100%
    - `ai/classifier/temporal_pipeline.py`: 98%
    - `backend/app/schemas/`: 94% – 100%
    - `backend/app/services/personalization_service.py`: 96%
    - `backend/app/services/coach_service.py`: 87%
    - `backend/app/services/websocket_service.py`: 87%

### Frontend Quality Suite
- **Total Tests**: 33 tests across 8 suites
- **Passing**: 33 (100%)
- **Typecheck**: 0 TypeScript errors (`tsc --noEmit`)
- **ESLint**: 0 warnings or errors (`next lint`)
- **Production Build**: Successful compilation (`next build`, 10 static routes)

---

## 4. Database Migrations Verification

Database migration reversibility was verified via live Alembic operations:
1. Current schema verified: `004_add_performance_indexes (head)`.
2. Downgraded to previous revision: `alembic downgrade 003_add_user_profile_table` (dropped composite performance indexes cleanly).
3. Upgraded back to head: `alembic upgrade head` (re-created all composite indexes cleanly).
4. Verified application startup and query performance with active schema.

---

## 5. Known Testing Limitations

1. **Local Camera Hardware in CI**:
   - Automated testing relies on synthetic 33-point MediaPipe landmarks and software mock streams. Actual physical webcam hardware initialization is tested with graceful failure handlers (handling `NotAllowedError` and missing device descriptors).
2. **Local Ollama Daemon**:
   - Ollama LLM is strictly mocked in automated test environments to keep the test suite fast (<2.5 minutes), reproducible, and completely offline. Live Ollama integration can be verified in staging environments via `scripts/` when an Ollama daemon is active.
