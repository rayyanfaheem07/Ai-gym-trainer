# System Architecture Diagram

This diagram depicts the high-level components and communication pathways across the Real-Time AI Gym Trainer application, separating browser-side telemetry from backend processing, storage, and local LLM inference.

```mermaid
graph TB
    subgraph Client["Frontend Client (Next.js 15 / Browser)"]
        UI[HUD & React Dashboard UI]
        Cam[Webcam Video Stream]
        Pose[MediaPipe Pose Detector<br/>33 3D Keypoints]
        WSC[WebSocket Client]
        HTTPC[REST API Client / Fetch]
        Cam --> Pose
        Pose --> WSC
        UI --> HTTPC
    end

    subgraph Edge["Network Boundary & Ingress"]
        CORS[CORS Policy & Security Headers]
        RateLimit[Sliding Window Rate Limiter]
    end

    subgraph Backend["FastAPI Backend (Python 3.11+)"]
        AuthRoute[Auth API /api/v1/auth]
        WorkoutRoute[Workout API /api/v1/workouts]
        CoachRoute[Coach API /api/v1/coach]
        AnalyticsRoute[Analytics API /api/v1/analytics]
        ProfileRoute[Profile API /api/v1/profile]
        WSRoute[WebSocket Stream /api/v1/ws/stream]

        subgraph CoreAI["Real-Time Movement Engine (In-Memory)"]
            FSM[Exercise State Machines<br/>Rep Counters]
            Geom[3D Angle Math & Biomechanics]
            Rules[Form Violation Engine]
            ML[PyTorch Temporal & Scikit-Learn Classifiers]
        end

        subgraph Services["Domain Services"]
            AuthSvc[AuthService]
            WorkoutSvc[WorkoutService]
            CoachSvc[CoachService]
            AnalyticsSvc[AnalyticsService]
            PersonalSvc[PersonalizationService]
        end
    end

    subgraph Data["Persistence Layer"]
        PG[(PostgreSQL 15 / SQLite DB)]
        Alembic[Alembic Migrations]
    end

    subgraph AI["Offline AI Inference"]
        Ollama[Local Ollama Service<br/>llama3.2]
        Fallback[Deterministic Fallback Engine]
    end

    HTTPC --> CORS --> RateLimit
    RateLimit --> AuthRoute & WorkoutRoute & CoachRoute & AnalyticsRoute & ProfileRoute

    WSC -->|ws:// stream with JWT| WSRoute
    WSRoute --> CoreAI
    CoreAI --> FSM & Geom & Rules & ML

    AuthRoute --> AuthSvc
    WorkoutRoute --> WorkoutSvc
    CoachRoute --> CoachSvc
    AnalyticsRoute --> AnalyticsSvc
    ProfileRoute --> PersonalSvc

    AuthSvc & WorkoutSvc & AnalyticsSvc & PersonalSvc --> PG
    CoachSvc --> Ollama
    CoachSvc -.->|on timeout or error| Fallback
    Alembic -.->|schema management| PG
```

### Component Breakdown
- **Browser Client**: Captures video frames locally using HTML5 `<video>`, extracts 33 body keypoints via MediaPipe Pose, and streams normalized coordinates over WebSocket.
- **FastAPI Layer**: Validates incoming JWT Bearer tokens and applies sliding-window rate limits and security headers (`nosniff`, `DENY`, `camera=(self)`).
- **Real-Time Movement Engine**: Evaluates joint angles, state machine transitions, and safety rule violations in memory at ~30 FPS without database writes per frame.
- **Domain Services & Repositories**: Orchestrates atomic database writes upon workout completion via SQLAlchemy async sessions.
- **Local AI Coach**: Queries authoritative workout telemetry from the database and prompts local Ollama (`llama3.2`) for structured coaching insights with deterministic rule-based fallback.
