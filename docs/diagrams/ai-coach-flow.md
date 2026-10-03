# AI Coach Architecture & Flow

This document details the architecture and execution sequence of the post-workout AI Coach service.

```mermaid
sequenceDiagram
    autonumber
    actor User as Client / Frontend
    participant API as FastAPI Coach Router (/api/v1/coach)
    participant CoachSvc as CoachService
    participant PersSvc as PersonalizationService
    participant DB as PostgreSQL Database
    participant Ollama as Ollama LLM Service (Local)
    participant Fallback as Deterministic Fallback Engine

    User->>API: POST /api/v1/coach/{session_id}/feedback
    Note over API: Sliding-window rate limit (10 req/min)<br/>JWT Bearer verified & subject extracted

    API->>CoachSvc: generate_feedback(db, session_id, target_focus, user_id)
    CoachSvc->>DB: Query Workout, ExerciseSessions, Results, FormIssues
    DB-->>CoachSvc: Authoritative telemetry records
    Note over CoachSvc: Verifies user ownership of workout session

    CoachSvc->>PersSvc: build_personalization_context(db, user_id, current_workout_id)
    PersSvc->>DB: Query UserProfile & historical workout trends
    DB-->>PersSvc: Profile settings & past 10 workout metrics
    PersSvc-->>CoachSvc: PersonalizationContext (Level, Style, Focus, Trends)

    CoachSvc->>CoachSvc: build_coach_context()
    Note over CoachSvc: Extracts strict factual metrics into CoachContext DTO.<br/>ZERO raw camera frames or images are sent to the LLM.

    alt Ollama Provider Available
        CoachSvc->>Ollama: POST /api/generate (prompt with strict system guardrails)
        Ollama-->>CoachSvc: JSON Response
        CoachSvc->>CoachSvc: Validate via CoachStructuredOutput Pydantic schema
    else Ollama Unavailable / Timeout / Invalid JSON
        CoachSvc->>Fallback: generate_coaching(CoachContext)
        Fallback-->>CoachSvc: Rule-based structured coaching based on telemetry & faults
        Note over CoachSvc: Model labeled as offline-fallback
    end

    CoachSvc->>DB: Upsert coaching_feedbacks record
    DB-->>CoachSvc: Stored coaching_feedback
    CoachSvc-->>API: CoachingFeedback ORM entity
    API-->>User: 200 OK (CoachFeedbackResponse DTO)
```

## Architectural Principles

1. **Fact Protection & Grounding**:
   - The LLM does **not** evaluate raw video or camera frames.
   - All input metrics (reps, valid reps, invalid reps, form scores, tempo, biomechanical faults) are calculated deterministically by the computer vision state machines and persisted before coach invocation.
   - The LLM's system prompt restricts it from inventing statistics or altering numerical metrics.

2. **Personalization Integration**:
   - Fitness profile settings (experience level, coaching style, preferred focus) and longitudinal trends across previous sessions are injected into the context without health-diagnosis claims.

3. **Resilience & Fallback**:
   - If Ollama is offline or times out, `DeterministicFallbackCoachProvider` guarantees that the user receives valid, structured advice derived directly from their recorded biomechanical fault codes.
