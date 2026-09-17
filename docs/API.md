# REST & WebSocket API Specification (v1)

FastAPI production backend architecture implementing a 4-tier layer (API $\rightarrow$ Service $\rightarrow$ AI/CV $\rightarrow$ Repository/Database) with secure JWT Bearer authentication, role/ownership enforcement, Pydantic v2 schemas, and PostgreSQL/SQLite with Alembic migrations.

---

## 1. Authentication & Identity (`/api/v1/auth`)

### `POST /api/v1/auth/register`
Registers a new user account with secure `bcrypt` salted password hashing and normalized email.

#### Request Body
```json
{
  "email": "athlete@gymtrainer.com",
  "password": "StrongPassword123!",
  "full_name": "Alex Athlete"
}
```

#### Response (201 Created)
```json
{
  "id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "email": "athlete@gymtrainer.com",
  "full_name": "Alex Athlete",
  "is_active": true,
  "created_at": "2026-09-10T10:00:00Z",
  "updated_at": "2026-09-10T10:00:00Z"
}
```
*Note: Passwords and password hashes are never exposed in API responses.*

#### Status Codes & Error Responses
- `201 Created`: User successfully registered.
- `409 Conflict`: `DUPLICATE_ENTITY` (email already registered).
- `422 Unprocessable Entity`: `VALIDATION_ERROR` (invalid email format or weak password).

---

### `POST /api/v1/auth/login`
Authenticates user credentials and returns a signed JWT access token.

#### Request Body
```json
{
  "email": "athlete@gymtrainer.com",
  "password": "StrongPassword123!"
}
```

#### Response (200 OK)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
    "email": "athlete@gymtrainer.com",
    "full_name": "Alex Athlete",
    "is_active": true,
    "created_at": "2026-09-10T10:00:00Z",
    "updated_at": "2026-09-10T10:00:00Z"
  }
}
```

#### Status Codes & Error Responses
- `200 OK`: Successful authentication.
- `401 Unauthorized`: `AUTHENTICATION_REQUIRED` (invalid email or password).

---

### `GET /api/v1/auth/me` *(Protected)*
Returns current profile information for the authenticated user.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Response (200 OK)
```json
{
  "id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "email": "athlete@gymtrainer.com",
  "full_name": "Alex Athlete",
  "is_active": true,
  "created_at": "2026-09-10T10:00:00Z",
  "updated_at": "2026-09-10T10:00:00Z"
}
```

---

## 2. System Health & Diagnostics

### `GET /health` and `GET /api/v1/health`
Public endpoint checking backend uptime, database connectivity (via `SELECT 1`), and AI engine readiness.

#### Response (200 OK)
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "database_connected": true,
  "ai_engine_ready": true
}
```

---

## 3. Workout Management (`/api/v1/workouts`) *(Protected)*

All workout endpoints require a valid Bearer token. Ownership is strictly derived from the JWT (`get_current_user`).

### `POST /api/v1/workouts/start`
Initializes a new workout session for the authenticated user.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Request Body
```json
{
  "notes": "Morning Leg and Core Strength Session"
}
```

#### Response (201 Created)
```json
{
  "id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "status": "in_progress",
  "started_at": "2026-09-10T10:00:00Z",
  "ended_at": null,
  "total_duration_sec": 0.0,
  "total_calories": 0.0,
  "overall_form_score": 0.0,
  "notes": "Morning Leg and Core Strength Session",
  "created_at": "2026-09-10T10:00:00Z",
  "updated_at": "2026-09-10T10:00:00Z"
}
```

---

### `POST /api/v1/workouts/{id}/finish`
Completes an active workout session. Validates state transitions and enforces that only the workout owner can finalize the session.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Request Body
```json
{
  "notes": "Completed 4 sets of heavy squats.",
  "total_duration_sec": 1850.0,
  "total_calories": 245.0,
  "overall_form_score": 93.5
}
```

#### Status Codes & Error Responses
- `200 OK`: Successfully finished workout.
- `400 Bad Request`: `INVALID_STATE_TRANSITION` (e.g. workout is already completed or cancelled).
- `401 Unauthorized`: Missing or invalid Bearer token.
- `403 Forbidden`: `FORBIDDEN` (workout belongs to another user).
- `404 Not Found`: `NOT_FOUND` (workout ID does not exist).

---

### `GET /api/v1/workouts`
Retrieves a paginated list of workouts belonging strictly to the authenticated user.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Query Parameters
- `limit` *(optional, default 50, max 100)*: Pagination limit.
- `offset` *(optional, default 0)*: Pagination offset.

#### Response (200 OK)
```json
[
  {
    "id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
    "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
    "status": "completed",
    "started_at": "2026-09-10T10:00:00Z",
    "ended_at": "2026-09-10T10:30:50Z",
    "total_duration_sec": 1850.0,
    "total_calories": 245.0,
    "overall_form_score": 93.5,
    "notes": "Completed 4 sets of heavy squats.",
    "created_at": "2026-09-10T10:00:00Z",
    "updated_at": "2026-09-10T10:30:50Z"
  }
]
```

### `GET /api/v1/workouts/history`
Retrieves a paginated list of completed or active workouts with exercise filter, status filter, and date-range filters, populated with nested exercise sessions.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Query Parameters
- `page` *(optional, default 1, min 1)*: Page number.
- `page_size` *(optional, default 10, min 1, max 100)*: Items per page.
- `exercise` *(optional, string)*: Filter workouts containing specific exercise (e.g., `squat`, `pushup`).
- `start_date` *(optional, ISO 8601 string / datetime)*: Filter workouts started on or after timestamp.
- `end_date` *(optional, ISO 8601 string / datetime)*: Filter workouts started on or before timestamp.
- `status` *(optional, string)*: Filter by status (`completed`, `in_progress`, `cancelled`).

#### Response (200 OK)
```json
{
  "items": [
    {
      "id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
      "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
      "status": "completed",
      "started_at": "2026-09-10T10:00:00Z",
      "ended_at": "2026-09-10T10:30:50Z",
      "total_duration_sec": 1850.0,
      "total_calories": 245.0,
      "overall_form_score": 93.5,
      "notes": "Completed 4 sets of heavy squats.",
      "created_at": "2026-09-10T10:00:00Z",
      "updated_at": "2026-09-10T10:30:50Z",
      "exercise_sessions": [
        {
          "id": "8f3b41e9-b251-4c33-84ec-da938bfa7921",
          "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
          "exercise_type": "squat",
          "session_order": 1,
          "started_at": "2026-09-10T10:05:00Z",
          "ended_at": "2026-09-10T10:25:00Z",
          "total_reps": 12,
          "valid_reps": 11,
          "invalid_reps": 1,
          "average_form_score": 93.5,
          "average_tempo_sec": 2.2,
          "created_at": "2026-09-10T10:05:00Z",
          "reps": []
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

---

### `GET /api/v1/workouts/{id}`
Returns full hierarchical details of a workout session, including nested `exercise_sessions`, rep-by-rep `results`, and `form_issues`. Enforces cross-user isolation.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Response (200 OK)
```json
{
  "id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "status": "completed",
  "started_at": "2026-09-10T10:00:00Z",
  "ended_at": "2026-09-10T10:30:50Z",
  "total_duration_sec": 1850.0,
  "total_calories": 245.0,
  "overall_form_score": 93.5,
  "notes": "Completed 4 sets of heavy squats.",
  "created_at": "2026-09-10T10:00:00Z",
  "updated_at": "2026-09-10T10:30:50Z",
  "exercise_sessions": [
    {
      "id": "ses_818290ab-1290",
      "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
      "exercise_name": "squat",
      "session_order": 1,
      "status": "completed",
      "target_reps": 10,
      "completed_reps": 10,
      "valid_reps": 9,
      "invalid_reps": 1,
      "average_form_score": 93.5,
      "average_tempo_sec": 2.4,
      "results": [
        {
          "id": "res_192039ab-3920",
          "rep_number": 1,
          "is_valid": 1,
          "form_score": 96.0,
          "duration_sec": 2.3,
          "eccentric_duration_sec": 1.3,
          "concentric_duration_sec": 1.0,
          "min_joint_angle": 84.5,
          "max_joint_angle": 174.0,
          "faults_detected": [],
          "form_issues": [],
          "created_at": "2026-09-10T10:05:00Z"
        }
      ],
      "created_at": "2026-09-10T10:02:00Z"
    }
  ]
}
```

---

## 4. Supported Exercises Catalog (`/api/v1/exercises`)

### `GET /api/v1/exercises`
Public catalog of supported exercises introspected from `ExerciseRegistry` along with movement standards and biomechanical form rules.

#### Response (200 OK)
```json
{
  "exercises": [
    {
      "name": "squat",
      "display_name": "Bodyweight & Barbell Squat",
      "category": "compound_lower",
      "target_muscles": ["Quadriceps", "Gluteus Maximus", "Hamstrings", "Core"],
      "primary_joints": ["Left Hip", "Right Hip", "Left Knee", "Right Knee"],
      "description": "Full lower-body compound movement emphasizing hip hinge, knee flexion past parallel, and upright thoracic posture.",
      "form_rules": [
        "Depth check: Hips must descend below knee level (knee angle <= 90 deg)",
        "Knee valgus: Knees must track over toes without collapsing inward",
        "Back alignment: Torso must avoid excessive forward lean",
        "Lockout: Full hip and knee extension at the top of the rep"
      ]
    }
  ],
  "count": 5
}
```

---

## 5. Structured AI Pose Analysis (`/api/v1/analysis`) *(Protected)*

### `POST /api/v1/analysis`
Processes structured 2D/3D pose landmarks through the decoupled AI inference and exercise biomechanics engines.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Request Body
```json
{
  "landmarks": [
    {"x": 0.51, "y": 0.32, "z": -0.12, "visibility": 0.98}
  ],
  "exercise_hint": "squat",
  "timestamp_ms": 1200.0
}
```

#### Response (200 OK)
```json
{
  "detected_exercise": "squat",
  "confidence": 1.0,
  "probabilities": {
    "squat": 1.0,
    "push_up": 0.0,
    "bicep_curl": 0.0,
    "lunge": 0.0,
    "shoulder_press": 0.0,
    "other": 0.0
  },
  "stage": "descending",
  "rep_count": 3,
  "valid_reps": 3,
  "invalid_reps": 0,
  "form_score": 94.5,
  "form_issues": [],
  "is_stub": false,
  "model_info": "production"
}
```

---

## 6. AI Biomechanics Coach (`/api/v1/coach`) *(Protected)*

### `POST /api/v1/coach/evaluate`
Generates LLM-driven post-workout feedback, strengths, and corrective advice for a user's completed workout.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Request Body
```json
{
  "session_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "target_focus": "form_improvement"
}
```

#### Response (200 OK)
```json
{
  "session_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "llm_model": "llama3.2",
  "summary": "Solid squat depth and consistent tempo across all sets.",
  "strengths": ["Consistent tempo", "Good depth on eccentric phase"],
  "areas_to_improve": ["Maintain steady knee alignment without inward collapse"],
  "recovery_advice": "Hydrate and perform light quad and hamstring stretches."
}
```

---

## 7. Real-Time Streaming (`WS /api/v1/ws/stream`) *(Protected)*

Bidirectional low-latency WebSocket endpoint for real-time camera pose telemetry streaming, live repetition counting, form scoring, joint angle tracking, and instant corrective audio/visual cues.

### 7.1 Authentication & Handshake

Browser WebSocket clients cannot set arbitrary HTTP headers (like `Authorization: Bearer <token>`) during the initial HTTP upgrade handshake. Therefore, WebSocket authentication requires supplying the JWT access token via query string:

```
ws://<host>:<port>/api/v1/ws/stream?token=<access_token>
```

#### Connection Flow:
1. **Client connects** with `?token=<JWT>`.
2. **Server authenticates**:
   - Decodes JWT signature and expiration.
   - Extracts subject claim (`sub`) containing `user_id`.
   - Verifies user exists and is active in the database.
   - Rejects unauthenticated/invalid connections cleanly with WebSocket close code `1008` (*Policy Violation*).
3. **Server sends `connected` acknowledgement**:
   ```json
   {
     "type": "connected",
     "status": "authenticated",
     "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
     "session_id": "8f3b41e9b2514c3384ecda938bfa7921",
     "message": "WebSocket connected and authenticated successfully."
   }
   ```
4. **Security Enforcement**: The authenticated identity is strictly bound to the validated JWT. Any `user_id` passed in client JSON payloads is ignored and cannot override the authenticated user.

---

### 7.2 Client-to-Server Messages

#### A. Start Exercise Session (`start_session`)
Initializes a new exercise tracking session. Optionally links with an active workout ID for later session summary persistence.

```json
{
  "type": "start_session",
  "exercise": "squat",
  "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea"
}
```

#### B. Stream Pose Frame (`pose_frame`)
Streams real-time 33-point MediaPipe pose landmarks for biomechanical form analysis and rep progression.

```json
{
  "type": "pose_frame",
  "timestamp_ms": 1250.0,
  "exercise": "squat",
  "landmarks": [
    {"x": 0.51, "y": 0.32, "z": -0.12, "visibility": 0.98},
    {"x": 0.53, "y": 0.30, "z": -0.10, "visibility": 0.97}
  ]
}
```

#### C. Stop Exercise Session (`stop_session`)
Ends the exercise session, computes aggregated statistics (total reps, valid/invalid reps, average form score, duration), and persists to the database if linked to a `workout_id`.

```json
{
  "type": "stop_session",
  "save_to_db": true
}
```

#### D. Heartbeat / Ping (`ping`)
Simple keepalive mechanism for maintaining active WebSocket connections.

```json
{
  "type": "ping"
}
```

#### E. Set Exercise / Reset (`set_exercise`, `reset`)
Dynamically switches the active exercise analyzer or resets current rep counters.

```json
{
  "type": "set_exercise",
  "exercise": "pushup"
}
```

---

### 7.3 Server-to-Client Messages

#### A. Live Analysis Result (`analysis_result`)
Returned in real time (<15ms processing latency) for each streamed pose frame.

```json
{
  "type": "analysis_result",
  "timestamp": 1250.0,
  "timestamp_ms": 1250.0,
  "exercise": "squat",
  "detected_exercise": "squat",
  "stage": "descending",
  "rep_count": 5,
  "valid_reps": 5,
  "invalid_reps": 0,
  "is_valid_rep": true,
  "confidence": 0.95,
  "current_angles": {
    "knee_angle": 112.4,
    "hip_angle": 138.1
  },
  "primary_angle": 112.4,
  "form_score": 92.0,
  "warnings": [],
  "feedback": ["Maintain chest up", "Drive through heels"],
  "issues": [],
  "audio_cue": "Drive through heels",
  "rep_duration_sec": 2.1,
  "metrics": {
    "depth_ratio": 0.88
  }
}
```

#### B. Session Started (`session_started`)
```json
{
  "type": "session_started",
  "session_id": "8f3b41e9b2514c3384ecda938bfa7921",
  "exercise": "squat",
  "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "started_at": "2026-09-10T10:00:00Z"
}
```

#### C. Session Stopped (`session_stopped`)
```json
{
  "type": "session_stopped",
  "session_id": "8f3b41e9b2514c3384ecda938bfa7921",
  "summary": {
    "session_id": "8f3b41e9b2514c3384ecda938bfa7921",
    "exercise": "squat",
    "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
    "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
    "total_reps": 10,
    "valid_reps": 9,
    "invalid_reps": 1,
    "average_form_score": 91.5,
    "duration_sec": 45.2,
    "frames_processed": 1350,
    "persisted_to_db": true
  }
}
```

#### D. Heartbeat Pong (`pong`)
```json
{
  "type": "pong",
  "timestamp": 1725964800.123
}
```

#### E. Structured Error (`error`)
Returned when an incoming message is malformed, unrecognized, or exceeds limits.

```json
{
  "type": "error",
  "code": "INVALID_JSON",
  "message": "Malformed JSON payload. Please provide valid JSON."
}
```

---

### 7.4 Performance & Database Safety Guardrails

- **Zero DB Writes Per Frame**: Real-time pose evaluation, joint angle computation, and repetition state machines execute strictly in-memory.
- **Batched/Aggregated Persistence**: Database writes occur only when an exercise session is completed (`stop_session`) associated with an active workout.
- **Payload Size Guards**: Incoming frames are constrained to $\le 1\text{MB}$ to prevent denial-of-service memory exhaustion.
- **Fail-Safe ML Integration**: Leverages the decoupled `ai_inference_service` with transparent fallback indicators (`is_stub=true`) when temporal ML weights are unavailable, ensuring zero fabricated predictions.

---

## 8. Analytics & Performance Telemetry (`/api/v1/analytics`) *(Protected)*

Provides aggregated athlete lifetime statistics, exercise-specific performance metrics, and chronological progression trends calculated strictly from persisted database records. All endpoints require a valid JWT Bearer token and enforce user isolation.

### `GET /api/v1/analytics/summary`
Calculates lifetime aggregate metrics across all completed and logged workouts for the authenticated user.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Response (200 OK)
```json
{
  "total_workouts": 14,
  "total_reps": 168,
  "total_valid_reps": 152,
  "overall_valid_rep_percentage": 90.48,
  "overall_average_form_score": 88.6,
  "total_duration_sec": 4820.5,
  "most_practiced_exercise": "squat",
  "recent_workout_count_30d": 12,
  "exercise_breakdown": {
    "squat": {
      "sessions": 8,
      "total_reps": 96,
      "valid_reps": 89,
      "avg_form_score": 91.2
    },
    "pushup": {
      "sessions": 6,
      "total_reps": 72,
      "valid_reps": 63,
      "avg_form_score": 85.1
    }
  }
}
```

---

### `GET /api/v1/analytics/exercises/{exercise}`
Returns deep-dive performance statistics for a specific exercise (e.g. `squat`, `pushup`, `bicep_curl`, `lunge`, `shoulder_press`).

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Path Parameters
- `exercise` *(required, string)*: Valid registered exercise name (canonical or aliased, e.g. `push-up` or `pushup`).

#### Response (200 OK)
```json
{
  "exercise": "squat",
  "total_sessions": 8,
  "total_reps": 96,
  "total_valid_reps": 89,
  "valid_rep_percentage": 92.71,
  "average_form_score": 91.2,
  "best_form_score": 98.0,
  "average_duration_sec": 340.2,
  "total_duration_sec": 2721.6,
  "common_form_issues": [
    {
      "issue": "Knees caving inward (valgus collapse)",
      "count": 4
    },
    {
      "issue": "Incomplete depth",
      "count": 2
    }
  ],
  "recent_sessions": [
    {
      "session_id": "8f3b41e9-b251-4c33-84ec-da938bfa7921",
      "date": "2026-09-15T18:30:00Z",
      "total_reps": 12,
      "valid_reps": 12,
      "form_score": 95.0,
      "duration_sec": 36.0
    }
  ]
}
```

---

### `GET /api/v1/analytics/trends`
Provides chronological time-series data points for charting performance trends across recent sessions.

#### Headers
```http
Authorization: Bearer <access_token>
```

#### Query Parameters
- `exercise` *(optional, string)*: Filter trend points to a specific exercise.
- `days` *(optional, integer, default 30, min 1, max 365)*: Number of past days to query.
- `limit` *(optional, integer, default 50, min 1, max 200)*: Maximum number of chronological data points.

#### Response (200 OK)
```json
{
  "exercise": "squat",
  "days": 30,
  "form_score_trend": [
    {
      "date": "2026-09-10T10:00:00Z",
      "value": 85.0,
      "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    },
    {
      "date": "2026-09-15T18:30:00Z",
      "value": 95.0,
      "workout_id": "aa123456-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    }
  ],
  "reps_trend": [
    {
      "date": "2026-09-10T10:00:00Z",
      "value": 10,
      "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    },
    {
      "date": "2026-09-15T18:30:00Z",
      "value": 12,
      "workout_id": "aa123456-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    }
  ],
  "valid_percentage_trend": [
    {
      "date": "2026-09-10T10:00:00Z",
      "value": 90.0,
      "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    },
    {
      "date": "2026-09-15T18:30:00Z",
      "value": 100.0,
      "workout_id": "aa123456-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    }
  ],
  "duration_trend": [
    {
      "date": "2026-09-10T10:00:00Z",
      "value": 32.5,
      "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    },
    {
      "date": "2026-09-15T18:30:00Z",
      "value": 36.0,
      "workout_id": "aa123456-6e62-4fa4-9bce-3849a76aceea",
      "exercise": "squat"
    }
  ]
}
```


