# Authentication & Authorization Flow Diagram

This diagram illustrates user registration, credential verification, JWT token issuance, endpoint protection via FastAPI dependencies, and WebSocket handshake validation.

```mermaid
sequenceDiagram
    autonumber
    actor Client as User / Browser
    participant API as FastAPI Ingress
    participant RateLimit as SlidingWindowRateLimiter
    participant AuthSvc as AuthService
    participant Bcrypt as Bcrypt Engine
    participant DB as PostgreSQL Database
    participant JWT as JWT Engine (PyJWT)

    %% Registration Flow
    rect rgb(240, 245, 255)
        Note over Client,DB: User Registration Flow
        Client->>API: POST /api/v1/auth/register (email, password, full_name)
        API->>RateLimit: Check limit (5 req/min)
        RateLimit-->>API: Permitted
        API->>AuthSvc: register(UserRegister schema)
        AuthSvc->>Bcrypt: hashpw(password, gensalt(rounds=12))
        Bcrypt-->>AuthSvc: $2b$12$... hashed string
        AuthSvc->>DB: INSERT INTO users (email, password_hash, ...)
        DB-->>AuthSvc: Created User entity
        AuthSvc-->>API: UserResponse (password excluded)
        API-->>Client: 201 Created (User details, no secrets)
    end

    %% Login Flow
    rect rgb(245, 255, 245)
        Note over Client,DB: User Login Flow
        Client->>API: POST /api/v1/auth/login (email, password)
        API->>RateLimit: Check limit (10 req/min)
        RateLimit-->>API: Permitted
        API->>AuthSvc: authenticate(UserLogin schema)
        AuthSvc->>DB: SELECT * FROM users WHERE email = :email
        DB-->>AuthSvc: User record
        AuthSvc->>Bcrypt: checkpw(password, password_hash)
        alt Password Match
            Bcrypt-->>AuthSvc: True
            AuthSvc->>JWT: create_access_token(sub=user.id, email=user.email)
            JWT-->>AuthSvc: Signed HS256 Token string
            AuthSvc-->>API: (token, user)
            API-->>Client: 200 OK (access_token, token_type="bearer", user)
        else Password Mismatch or Non-Existent User
            Bcrypt-->>AuthSvc: False
            AuthSvc-->>API: raise AuthenticationError("Invalid email or password.")
            API-->>Client: 401 Unauthorized
        end
    end

    %% Protected API Access
    rect rgb(255, 250, 240)
        Note over Client,DB: Protected API Access Flow
        Client->>API: GET /api/v1/workouts/{id} (Authorization: Bearer <JWT>)
        API->>API: get_current_user dependency
        API->>JWT: decode(token, algorithms=["HS256"], issuer="...")
        alt Token Valid
            JWT-->>API: Claims (sub="usr_123", exp, iat)
            API->>DB: SELECT * FROM users WHERE id = "usr_123"
            DB-->>API: User entity (is_active=True)
            API->>DB: SELECT * FROM workouts WHERE id = :id
            DB-->>API: Workout record
            alt Workout user_id == current_user.id
                API-->>Client: 200 OK (WorkoutDetailResponse)
            else Workout user_id != current_user.id
                API-->>Client: 403 Forbidden ("You do not have permission to view this workout.")
            end
        else Token Expired or Tampered
            JWT-->>API: ExpiredSignatureError / InvalidTokenError
            API-->>Client: 401 Unauthorized
        end
    end

    %% WebSocket Handshake
    rect rgb(255, 240, 255)
        Note over Client,DB: Real-Time WebSocket Handshake
        Client->>API: WS /api/v1/ws/stream?token=<JWT>
        API->>RateLimit: Check handshake limit (30/min per IP)
        API->>JWT: decode(token)
        alt Valid JWT & Active User
            JWT-->>API: Valid claims (sub="usr_123")
            API-->>Client: WebSocket Accept + connected packet
        else Invalid / Missing / Expired Token
            API-->>Client: WebSocket Close (Code 1008 Policy Violation)
        end
    end
```

### Security Guarantees
- **Bcrypt Cost Factor**: 12 rounds ensures resistance to brute-force attacks while remaining efficient for single logins.
- **Algorithm Pinning**: Tokens must match `HS256`; tokens specifying `none` or asymmetric variants are rejected.
- **Multi-Tenant Scoping**: All database queries for user resources explicitly filter by `user_id == current_user.id`.
