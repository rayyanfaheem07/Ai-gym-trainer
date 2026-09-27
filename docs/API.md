# REST & WebSocket API Specification (v1)

FastAPI production backend architecture implementing a 4-tier layer (API $\rightarrow$ Service $\rightarrow$ AI/CV $\rightarrow$ Repository/Database) with secure JWT Bearer authentication, role/ownership enforcement, Pydantic v2 schemas, and PostgreSQL/SQLite with Alembic migrations.

## Base URLs
- **REST Base URL**: `http://localhost:8000/api/v1` (Docker: `http://ai_gym_backend:8000/api/v1`)
- **WebSocket URL**: `ws://localhost:8000/api/v1/ws/stream?token=<JWT>`

## Authentication & Security
- **Bearer Token**: All protected endpoints require an `Authorization: Bearer <access_token>` header.
- **WebSocket Auth**: Native browser WebSocket connections authenticate via the `?token=<JWT>` query parameter.
- **Rate Limiting (In-Memory)**:
  - Auth routes (`/auth/*`): 10 requests / minute per IP.
  - Coach routes (`/coach/*`): 10 requests / minute per IP.
  - WebSocket handshakes (`/ws/*`): 30 connections / minute per IP.
- **Security Headers**: All responses return `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Content-Security-Policy`.

---

## 1. Authentication & Identity (`/api/v1/auth`)

### `POST /api/v1/auth/register`
Registers a new user account with secure `bcrypt` salted password hashing and normalized email.
- **Auth**: Public (Rate-limited: 10 req/min)

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

#### Status Codes
- `201 Created`: User successfully registered.
- `409 Conflict`: Email already exists.
- `422 Unprocessable Entity`: Validation failure (weak password, malformed email).
- `429 Too Many Requests`: Exceeded 10 requests / minute.

---

### `POST /api/v1/auth/login`
Authenticates user credentials and returns a signed JWT access token.
- **Auth**: Public (Rate-limited: 10 req/min)

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

#### Status Codes
- `200 OK`: Successful authentication.
- `401 Unauthorized`: Invalid credentials.
- `429 Too Many Requests`: Exceeded 10 requests / minute.

---

### `GET /api/v1/auth/me`
Returns current profile information for the authenticated user.
- **Auth**: Bearer Token required

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

## 2. Personal Fitness Profile (`/api/v1/profile`)

### `GET /api/v1/profile`
Retrieves personalization preferences, experience level, fitness goals, and coaching style for the authenticated athlete.
- **Auth**: Bearer Token required

#### Response (200 OK)
```json
{
  "id": "prf_83a1b021-4f32-411a-8c5e-72bc912384ee",
  "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "fitness_goal": "strength",
  "experience_level": "intermediate",
  "preferred_focus": "form",
  "coaching_style": "supportive",
  "created_at": "2026-09-10T10:05:00Z",
  "updated_at": "2026-09-10T10:05:00Z"
}
```

---

### `PUT /api/v1/profile`
Updates personalization preferences, experience level, fitness goals, and coaching style.
- **Auth**: Bearer Token required

#### Request Body
```json
{
  "fitness_goal": "muscle_gain",
  "experience_level": "advanced",
  "preferred_focus": "strength",
  "coaching_style": "technical"
}
```

#### Valid Enum Values:
- `fitness_goal`: `strength`, `muscle_gain`, `fat_loss`, `general_fitness`, `endurance`
- `experience_level`: `beginner`, `intermediate`, `advanced`
- `preferred_focus`: `form`, `strength`, `consistency`, `endurance`, `balanced`
- `coaching_style`: `concise`, `supportive`, `detailed`, `technical`

---

## 3. Workouts & Telemetry Lifecycle (`/api/v1/workouts`)

### `POST /api/v1/workouts/start`
Initializes a new workout session for the authenticated user.
- **Auth**: Bearer Token required

#### Request Body (Optional)
```json
{
  "notes": "Leg day focused on squat depth"
}
```

#### Response (201 Created)
```json
{
  "id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "status": "in_progress",
  "started_at": "2026-09-15T18:00:00Z",
  "ended_at": null,
  "total_duration_sec": 0.0,
  "total_calories": 0.0,
  "overall_form_score": 0.0,
  "notes": "Leg day focused on squat depth"
}
```

---

### `POST /api/v1/workouts/{id}/finish`
Concludes an active workout, calculating total duration and aggregating form scores.
- **Auth**: Bearer Token required (Enforces user ownership)

#### Response (200 OK)
```json
{
  "id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "status": "completed",
  "started_at": "2026-09-15T18:00:00Z",
  "ended_at": "2026-09-15T18:32:45Z",
  "total_duration_sec": 1965.0,
  "total_calories": 142.5,
  "overall_form_score": 89.4,
  "notes": "Leg day focused on squat depth"
}
```

---

### `POST /api/v1/workouts/{id}/sessions`
Appends a completed exercise set to an active workout session.
- **Auth**: Bearer Token required (Enforces user ownership)

#### Request Body
```json
{
  "exercise_name": "squat",
  "session_order": 1,
  "target_reps": 10,
  "completed_reps": 10,
  "valid_reps": 9,
  "invalid_reps": 1,
  "average_form_score": 91.5,
  "average_tempo_sec": 2.4
}
```

---

### `GET /api/v1/workouts/{id}`
Retrieves a detailed workout session including all child sets, repetition results, and fine-grained form issues.
- **Auth**: Bearer Token required (Enforces user ownership)

#### Response (200 OK)
Returns complete workout object with nested `exercise_sessions`, `results`, `form_issues`, and `feedback`.

---

### `GET /api/v1/workouts/history`
Returns paginated workout history for the authenticated user, optionally filtered by exercise name.
- **Auth**: Bearer Token required
- **Query Params**:
  - `page` *(default 1)*: Page number
  - `page_size` *(default 10, max 50)*: Items per page
  - `exercise` *(optional)*: Filter workouts containing specific exercise

---

## 4. Analytics & Performance (`/api/v1/analytics`)

### `GET /api/v1/analytics/summary`
Calculates lifetime aggregate metrics across all completed workouts for the authenticated user.
- **Auth**: Bearer Token required

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
    }
  }
}
```

---

### `GET /api/v1/analytics/exercises/{exercise}`
Returns deep-dive performance statistics for a specific exercise.
- **Auth**: Bearer Token required
- **Path Params**: `exercise` (e.g. `squat`, `pushup`, `bicep_curl`, `lunge`, `shoulder_press`)

---

### `GET /api/v1/analytics/trends`
Provides chronological time-series data points for charting performance trends across recent sessions.
- **Auth**: Bearer Token required
- **Query Params**:
  - `exercise` *(optional)*: Filter to exercise
  - `days` *(default 30, min 1, max 365)*: Lookback window
  - `limit` *(default 50, min 1, max 200)*: Max points

---

## 5. AI Coach & Post-Workout Insights (`/api/v1/coach`)

### `POST /api/v1/coach/session/{session_id}`
Generates AI coaching evaluation, strengths, areas to improve, and recovery advice for a workout session.
- **Auth**: Bearer Token required (Enforces user ownership)
- **Rate Limit**: 10 requests / minute per IP
- **Query Params**: `target_focus` *(optional, default "form_improvement")*

#### Response (200 OK)
```json
{
  "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea",
  "llm_model": "llama3.2",
  "summary": "Great session! Squat depth was consistent across all 10 reps, maintaining an average form score of 91.5%.",
  "strengths": [
    "Excellent concentric and eccentric cadence",
    "Solid thoracic positioning on the descent"
  ],
  "areas_to_improve": [
    "Slight knee valgus on reps 8 and 9 as fatigue set in"
  ],
  "recovery_advice": "Next Session Focus: Drive knees outward against band tension | Safety: Avoid collapsing knees during inflection",
  "created_at": "2026-09-15T18:35:00Z"
}
```

*Note: If Ollama is offline or times out, the service returns deterministic rule-based coaching feedback with `llm_model: "llama3.2 (offline-fallback)"`.*

---

### `GET /api/v1/coach/session/{session_id}`
Retrieves existing coaching feedback for an owned workout session. If no feedback has been generated yet, it generates and persists it automatically.
- **Auth**: Bearer Token required (Enforces user ownership)

---

## 6. Exercises Catalog (`/api/v1/exercises`)

### `GET /api/v1/exercises`
Returns catalog of supported exercises registered in the computer vision analysis engine.
- **Auth**: Public

#### Response (200 OK)
```json
{
  "exercises": [
    {
      "name": "squat",
      "display_name": "Squat",
      "category": "lower_body",
      "description": "Barbell / Bodyweight squat tracking knee and hip flexion."
    },
    {
      "name": "pushup",
      "display_name": "Push-up",
      "category": "upper_body",
      "description": "Standard push-up tracking elbow flexion and spinal neutrality."
    },
    {
      "name": "bicep_curl",
      "display_name": "Bicep Curl",
      "category": "arms",
      "description": "Dumbbell bicep curl tracking elbow flexion and torso stability."
    },
    {
      "name": "lunge",
      "display_name": "Lunge",
      "category": "lower_body",
      "description": "Forward lunge tracking lead knee flexion and vertical torso."
    },
    {
      "name": "shoulder_press",
      "display_name": "Shoulder Press",
      "category": "shoulders",
      "description": "Overhead press tracking elbow extension and lumbar neutrality."
    }
  ]
}
```

---

## 7. System Health & Diagnostics (`/health`, `/api/v1/health`)

### `GET /health` or `GET /api/v1/health`
Public endpoint checking backend uptime, database connectivity (via `SELECT 1`), and AI engine readiness.
- **Auth**: Public

#### Response (200 OK)
```json
{
  "status": "healthy",
  "database": "connected",
  "ai_engine": "ready",
  "version": "1.0.0"
}
```

---

## 8. Real-Time WebSocket Streaming (`/api/v1/ws/stream`)

### Handshake & Connection
- **Endpoint**: `ws://localhost:8000/api/v1/ws/stream?token=<access_token>`
- **Rate Limit**: 30 connections / minute per IP
- **Security Check**: The token query parameter is decoded and validated immediately upon connection. If invalid, expired, or missing, the handshake is rejected with code `1008` (Policy Violation).

### Client Message Types

#### 1. `start_session`
Initializes state machine for a specific exercise set.
```json
{
  "type": "start_session",
  "exercise": "squat",
  "workout_id": "fe18e620-6e62-4fa4-9bce-3849a76aceea"
}
```

#### 2. `pose_frame`
Streams MediaPipe 33-point landmark coordinates at ~30 FPS.
```json
{
  "type": "pose_frame",
  "timestamp_ms": 1725964800123,
  "landmarks": [
    {"x": 0.51, "y": 0.22, "z": -0.15, "visibility": 0.99},
    ... (33 items)
  ]
}
```

#### 3. `stop_session`
Concludes the exercise set, aggregates reps and faults, and persists to the database if `workout_id` was provided.
```json
{
  "type": "stop_session"
}
```

#### 4. `ping`
Heartbeat check. Server responds with `pong`.
```json
{
  "type": "ping"
}
```

### Server Message Types

#### 1. `connected`
Acknowledges successful authentication and connection.
```json
{
  "type": "connected",
  "user_id": "usr_948f2190-3c12-4c54-9fa2-8bca120934ef",
  "message": "Connected to AI Gym Trainer streaming service."
}
```

#### 2. `analysis_result`
Dispatched in response to every valid `pose_frame` (<15ms latency).
```json
{
  "type": "analysis_result",
  "timestamp_ms": 1725964800123,
  "exercise": "squat",
  "rep_count": 5,
  "valid_reps": 5,
  "invalid_reps": 0,
  "current_stage": "descending",
  "form_score": 94.0,
  "primary_angle": 88.5,
  "latency_ms": 0.42,
  "feedback": [
    "Good depth! Keep knees aligned over toes."
  ],
  "faults": []
}
```

#### 3. `session_summary`
Dispatched upon receiving `stop_session`.
```json
{
  "type": "session_summary",
  "exercise": "squat",
  "total_reps": 10,
  "valid_reps": 9,
  "invalid_reps": 1,
  "average_form_score": 91.5,
  "total_duration_sec": 38.2,
  "form_issues_summary": [
    {"issue": "KNEE_VALGUS", "count": 1}
  ]
}
```

#### 4. `pong`
```json
{
  "type": "pong",
  "timestamp": 1725964800.123
}
```

#### 5. `error`
```json
{
  "type": "error",
  "code": "INVALID_JSON",
  "message": "Malformed JSON payload. Please provide valid JSON."
}
```
