# Backend Architecture Diagram

The FastAPI backend is structured as a strict 4-tier layered architecture (API Layer $\rightarrow$ Service Layer $\rightarrow$ AI/CV Movement Engine $\rightarrow$ Repository / Database Layer) to guarantee separation of concerns, testability, and multi-tenant security.

```mermaid
graph TD
    subgraph Tier1["1. API Layer (backend/app/api/v1/)"]
        AuthRouter["auth.py<br/>/register, /login, /me"]
        WorkoutRouter["workouts.py<br/>/start, /{id}/finish, /history, /{id}"]
        CoachRouter["coach.py<br/>/evaluate, /session/{id}"]
        AnalyticsRouter["analytics.py<br/>/summary, /exercises/{ex}, /trends"]
        ProfileRouter["profile.py<br/>GET /profile, PUT /profile"]
        WSRouter["websocket.py<br/>/ws/stream"]
        HealthRouter["health.py<br/>/health"]
    end

    subgraph MiddlewareLayer["Middleware & Ingress Pipeline"]
        SecHeaders["SecurityHeadersMiddleware<br/>nosniff, DENY, camera=(self)"]
        CORSMid["CORSMiddleware<br/>Origins, Methods, Headers"]
        RateLimiter["SlidingWindowRateLimiter<br/>IP-based sliding window"]
        AuthDep["get_current_user Dependency<br/>JWT Decode & sub Verification"]
    end

    subgraph Tier2["2. Service Layer (backend/app/services/)"]
        AuthService["AuthService<br/>User registration, bcrypt verification"]
        WorkoutService["WorkoutService<br/>Workout lifecycle & ownership rules"]
        CoachService["CoachService<br/>Fact extraction & LLM orchestration"]
        AnalyticsService["AnalyticsService<br/>Aggregate calculations & trend math"]
        PersonalizationService["PersonalizationService<br/>Profile & trend context"]
        WebSocketService["WebSocketService<br/>Session tracker & packet dispatch"]
    end

    subgraph Tier3["3. AI / CV Movement Layer (ai/)"]
        Registry["ExerciseRegistry<br/>Dynamic exercise factory"]
        SquatAnalyzer["SquatDetector"]
        PushupAnalyzer["PushupExercise"]
        BicepAnalyzer["BicepCurlExercise"]
        LungeAnalyzer["LungeExercise"]
        ShoulderAnalyzer["ShoulderPressExercise"]
        Angles["ai.geometry.angles<br/>Vector cosine angle math"]
        Rules["ai.form_analysis.rules<br/>Biomechanical penalty rules"]
        MLClassifier["ai.classifier<br/>Temporal LSTM & Scikit-Learn Classifiers"]
    end

    subgraph Tier4["4. Repository / Database Layer (backend/app/repositories/)"]
        UserRepo["UserRepository"]
        WorkoutRepo["WorkoutRepository"]
        ProfileRepo["ProfileRepository"]
        AnalyticsRepo["AnalyticsRepository"]
        AsyncSession["SQLAlchemy 2.0 AsyncSession"]
        Models["SQLAlchemy ORM Models<br/>User, Workout, ExerciseSession, FormIssue"]
    end

    Tier1 --> MiddlewareLayer
    MiddlewareLayer --> Tier2
    AuthDep -.->|injected into| Tier1

    WorkoutService --> Tier3
    WebSocketService --> Tier3
    Tier3 --> Registry
    Registry --> SquatAnalyzer & PushupAnalyzer & BicepAnalyzer & LungeAnalyzer & ShoulderAnalyzer
    SquatAnalyzer & PushupAnalyzer & BicepAnalyzer & LungeAnalyzer & ShoulderAnalyzer --> Angles & Rules & MLClassifier

    AuthService --> UserRepo
    WorkoutService --> WorkoutRepo
    CoachService --> WorkoutRepo & ProfileRepo
    AnalyticsService --> AnalyticsRepo
    PersonalizationService --> ProfileRepo & AnalyticsRepo

    UserRepo & WorkoutRepo & ProfileRepo & AnalyticsRepo --> AsyncSession
    AsyncSession --> Models
```

### Layer Responsibilities
- **API Layer**: Route definitions, HTTP status codes, request/response serialization via Pydantic v2 schemas, and dependency injection (`get_current_user`, `get_db`, `rate_limit`).
- **Service Layer**: Business logic, cross-user authorization enforcement, factual context assembly for the AI Coach, and workout lifecycle orchestration.
- **AI / CV Movement Layer**: Biomechanical angle math, Finite State Machines (FSM) for rep detection, and heuristic form evaluation rules.
- **Repository Layer**: Encapsulates all database queries using SQLAlchemy Core/ORM parameterized expressions with eager loading (`selectinload`).
