# Security Architecture & Hardening Guide

## 1. Authentication & JWT Security

- **Algorithm & Signature Enforcement**: JSON Web Tokens (JWT) are signed strictly using HMAC-SHA256 (`HS256`). Algorithm confusion attacks (such as the `none` algorithm) are blocked by explicitly restricting decoding algorithms to `[settings.JWT_ALGORITHM]`.
- **Secret Key Handling**: `JWT_SECRET_KEY` must be configured via environment variables. The application will fail safely at startup if set to a default development secret or if the secret is shorter than 32 characters in `production` mode.
- **Token Claims**: Authenticated requests must carry a valid Bearer token containing the standard `sub` (user UUID), `email`, `iat`, `exp`, and `iss` claims.
- **Expiration**: Default expiration is 60 minutes (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`). Expired tokens are rejected with HTTP 401 Unauthorized.
- **Credential Storage**: Passwords are never stored in plaintext. They are hashed using bcrypt with salt over 12 computation rounds. Password hashes are excluded from all response schemas (`UserResponse`).

## 2. Authorization & Multi-Tenant Isolation

- **Server-Side Enforcement**: Direct ID access to workouts (`/api/v1/workouts/{id}`), coaching insights (`/api/v1/coach/...`), user profiles (`/api/v1/profile`), and analytics is validated against the authenticated user's ID (`current_user.id`).
- **IDOR Protection**: Attempts by User A to read, modify, finish, or attach exercise sets to User B's workout return HTTP 403 Forbidden without leaking resource details.
- **Analytics & History**: Workout history and aggregate metrics queries are scoped strictly to `user_id == current_user.id`.

## 3. WebSocket Security & Real-Time Telemetry

- **Handshake Authentication**: The WebSocket endpoint `/api/v1/ws/stream` requires a valid JWT supplied in the connection query string (`?token=<JWT>`). Missing, invalid, expired, or deactivated accounts are rejected during handshake with WebSocket close code `1008 (Policy Violation)`.
- **Handshake Rate Limiting**: WebSocket connection attempts are rate-limited (default: 30 connects/minute per IP) to mitigate connection exhaustion floods.
- **In-Memory Frame Processing**: Real-time pose frames are processed entirely in memory (~30 FPS). No database writes occur during active frame streaming.
- **Payload Size Guards**: Incoming WebSocket messages are capped at 1 MB (`WEBSOCKET_MAX_MESSAGE_SIZE = 1_048_576`). Oversized payloads are dropped with an error response without crashing the server.
- **Malformed Message Resilience**: Invalid JSON, non-object JSON payloads, and unknown message types are caught gracefully and return structured error packets.
- **Cross-User Session Protection**: When finishing a workout streaming session (`stop_session`), persistence is validated against the authenticated user's ownership of the targeted workout.

## 4. Input Validation & Database Security

- **Pydantic v2 Schema Bounds**: Strict field constraints enforce valid bounds on all inputs:
  - Repetition counts: `1 <= rep_number <= 10000`
  - Biomechanical form scores: `0.0 <= form_score <= 100.0`
  - Durations: bounded within 24 hours (`le=86400.0`)
  - String inputs: max string lengths on codes (64 chars), notes (2000 chars), and feedback texts (1000 chars).
- **SQL Injection Prevention**: All database queries are executed via SQLAlchemy Core and ORM parameterized expressions (`select().where()`). No user input is concatenated into raw SQL strings.
- **Malformed IDs**: Malformed UUIDs or path traversal strings return HTTP 404 or 422 cleanly without exposing database internals or tracebacks.

## 5. HTTP Security & CORS Policy

- **CORS Configuration**: CORS origins are restricted to configured hosts (`CORS_ORIGINS`). Unlisted origins do not receive `Access-Control-Allow-Origin` headers. HTTP methods are restricted to `GET, POST, PUT, PATCH, DELETE, OPTIONS`.
- **Security Headers Middleware**:
  - `X-Content-Type-Options: nosniff`: Prevents MIME-sniffing.
  - `X-Frame-Options: DENY`: Prevents framing and clickjacking.
  - `Referrer-Policy: strict-origin-when-cross-origin`: Restricts referrer disclosure across origins.
  - `Permissions-Policy: camera=(self)`: Permits camera access strictly for the AI pose detection client while disallowing third-party embeds.
  - `Strict-Transport-Security`: Enforced when requests are served over HTTPS.

## 6. Rate Limiting & Abuse Protection

- **Sliding-Window Limiter**: Thread-safe in-memory sliding-window limiter applied to sensitive REST endpoints:
  - User Registration: 5 requests / min
  - User Login: 10 requests / min
  - AI Coach Generation: 10 requests / min
  - WebSocket Handshake: 30 connections / min
- Exceeding the rate limit returns HTTP 429 Too Many Requests with a standard `Retry-After` response header.

## 7. Container & Infrastructure Security

- **Non-Root Execution**:
  - Backend container runs as unprivileged user `appuser` (UID 1000).
  - Frontend container runs as unprivileged user `nextjs` (UID 1001).
- **Security Options**: Container definitions in `docker-compose.yml` set `security_opt: [no-new-privileges:true]` to block privilege escalation.
- **Network Isolation**: PostgreSQL (`5432`) and Ollama (`11434`) ports are bound to `127.0.0.1` on the host, preventing external access.

## 8. Automated Security Quality Gates (CI/CD)

- **Static Security Analysis**: `bandit -r backend/ ai/ -ll` executes in CI on every push and pull request.
- **Secret Hygiene**: Scans for untracked environment files (`.env`, `.env.local`) and private key signatures (`BEGIN PRIVATE KEY`).
- **Dependency Auditing**: `pip-audit` checks Python dependencies; `npm audit` validates Node packages.

## 9. Known Limitations & Architecture Notes

- **Distributed Rate Limiting**: The current sliding-window rate limiter is an in-memory implementation intended for single-instance or containerized deployments. For multi-replica horizontally scaled clusters, a centralized cache store (e.g. Redis) should be integrated.
- **WebSocket Browser Auth**: Standard browser WebSocket APIs (`new WebSocket(...)`) do not support custom request headers; JWTs are therefore transmitted in query parameters during connection establishment over TLS (WSS).
