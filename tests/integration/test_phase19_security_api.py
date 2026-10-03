import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.rate_limit import limiter
from backend.app.core.security import create_access_token
from backend.app.models.user import User
from tests.integration.test_websocket import get_test_client

# ==============================================================================
# 1. HTTP Security Headers & CORS Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_http_security_headers_present_on_all_responses(async_client: AsyncClient):
    """Verifies that security headers are automatically added to HTTP responses."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200

    # Strict MIME sniffing prevention
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    # Clickjacking protection
    assert resp.headers.get("X-Frame-Options") == "DENY"

    # Referrer privacy policy
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # Permissions policy allowing camera only for self
    assert "camera=(self)" in resp.headers.get("Permissions-Policy", "")


@pytest.mark.asyncio
async def test_cors_behavior_with_allowed_and_untrusted_origins(async_client: AsyncClient):
    """Verifies that allowed origins receive CORS headers and untrusted origins do not."""
    # 1. Allowed origin (localhost:3000)
    allowed_resp = await async_client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert allowed_resp.status_code == 200
    assert allowed_resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # 2. Untrusted origin
    untrusted_resp = await async_client.get(
        "/health",
        headers={"Origin": "http://evil-malicious-site.com"},
    )
    assert untrusted_resp.status_code == 200
    assert untrusted_resp.headers.get("access-control-allow-origin") != "http://evil-malicious-site.com"


# ==============================================================================
# 2. Invalid Authorization Headers & Token Variations
# ==============================================================================


@pytest.mark.asyncio
async def test_invalid_authorization_header_schemes(async_client: AsyncClient):
    """Verifies non-Bearer or malformed authorization headers fail safely with 401."""
    invalid_headers = [
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer   "},
        {"Authorization": "Token 12345"},
        {"Authorization": "Bearer not.a.valid.jwt"},
    ]
    for h in invalid_headers:
        res = await async_client.get("/api/v1/profile", headers=h)
        assert res.status_code == 401, f"Failed for header {h}: {res.status_code}"
        data = res.json()
        assert "detail" in data
        assert res.headers.get("WWW-Authenticate") == "Bearer"


# ==============================================================================
# 3. SQL Injection Resistance & Malformed Path Parameters
# ==============================================================================


@pytest.mark.asyncio
async def test_sql_injection_payloads_in_query_parameters(
    authenticated_async_client: AsyncClient,
):
    """Verifies that SQL injection attempts in query parameters fail safely without database errors."""
    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE workouts; --",
        "1 UNION SELECT 1, 'admin', 'hash' --",
        "' OR 1=1 --",
    ]
    for injection in sql_payloads:
        # History filter injection
        resp = await authenticated_async_client.get(
            f"/api/v1/workouts/history?exercise={injection}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "error" not in resp.text.lower() or "syntax error" not in resp.text.lower()

        # Trends period injection
        trend_resp = await authenticated_async_client.get(
            f"/api/v1/analytics/trends?period={injection}"
        )
        assert trend_resp.status_code == 200


@pytest.mark.asyncio
async def test_malformed_ids_in_path_parameters(
    authenticated_async_client: AsyncClient,
):
    """Verifies that non-existent or malformed UUID strings in path parameters return clean 404s without tracebacks."""
    malformed_ids = [
        "not-a-valid-uuid",
        "../../etc/passwd",
        "<script>alert(1)</script>",
        "00000000-0000-0000-0000-000000000000",
    ]
    for test_id in malformed_ids:
        resp = await authenticated_async_client.get(f"/api/v1/workouts/{test_id}")
        assert resp.status_code in (404, 422), f"Expected 404/422 for ID '{test_id}', got {resp.status_code}"
        assert "Traceback" not in resp.text


# ==============================================================================
# 4. Secrets & Health Endpoint Information Exposure
# ==============================================================================


@pytest.mark.asyncio
async def test_health_endpoint_never_exposes_secrets_or_credentials(
    async_client: AsyncClient,
):
    """Verifies that health and public endpoints never leak passwords, DB URLs, or JWT secrets."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    text = resp.text.lower()

    # Sensitive patterns
    assert "password" not in text
    assert "secret" not in text
    assert "postgres:" not in text
    assert "sqlite" not in text
    assert settings.JWT_SECRET_KEY.lower() not in text


# ==============================================================================
# 5. Rate Limiting Protection on Sensitive Endpoints
# ==============================================================================


@pytest.mark.asyncio
async def test_rate_limiting_on_login_endpoint(async_client: AsyncClient):
    """Verifies rate limiting blocks excessive requests to /api/v1/auth/login and sets Retry-After header."""
    limiter.reset()
    login_data = {"email": "rate_limit_test@example.com", "password": "WrongPassword123!"}

    limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
    for _ in range(limit):
        r = await async_client.post("/api/v1/auth/login", json=login_data)
        # Authentication failure (401), but not rate limited yet
        assert r.status_code in (401, 404, 422)

    # (limit + 1)th request must be rejected with 429 Too Many Requests
    blocked_resp = await async_client.post("/api/v1/auth/login", json=login_data)
    assert blocked_resp.status_code == 429
    assert blocked_resp.headers.get("Retry-After") is not None
    data = blocked_resp.json()
    assert data.get("error_code") == "RATE_LIMIT_EXCEEDED"
    limiter.reset()


# ==============================================================================
# 6. WebSocket Robustness & Security
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_rejects_malformed_json_without_crashing(
    db_session: AsyncSession, test_user: User
):
    """Verifies that malformed JSON on WebSocket receives safe error packet without crashing server."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Send invalid JSON
        ws.send_text("THIS IS NOT JSON {{{")
        err_packet = json.loads(ws.receive_text())
        assert err_packet["type"] == "error"
        assert err_packet["code"] == "INVALID_JSON"

        # Subsequent valid message still functions
        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"
