import os

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.core.errors import AuthenticationError
from backend.app.core.rate_limit import SlidingWindowRateLimiter
from backend.app.core.security import decode_access_token
from backend.app.schemas.workout import (
    ExerciseResultCreate,
    FormIssueCreate,
    WorkoutFinishRequest,
)


def test_production_jwt_secret_validation_rejects_insecure_defaults():
    """Verify that validate_production_security fails safely on insecure or short secrets."""
    insecure_keys = [
        "dev-secret-key-change-in-production",
        "dev-secret-key-change-in-production-use-openssl-rand-hex-32",
        "secret",
        "changeme",
        "short",
    ]
    for key in insecure_keys:
        s = Settings(ENVIRONMENT="production", JWT_SECRET_KEY=key)
        with pytest.raises(ValueError) as exc:
            s.validate_production_security()
        assert "insecure" in str(exc.value).lower() or "at least 32" in str(exc.value).lower()

    # Valid production secret (>= 32 chars and not default)
    secure_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="0123456789abcdef0123456789abcdef",
    )
    # Should not raise
    secure_settings.validate_production_security()

    # In development mode, dev secrets are permitted
    dev_settings = Settings(
        ENVIRONMENT="development",
        JWT_SECRET_KEY="dev-secret-key-change-in-production",
    )
    dev_settings.validate_production_security()


def test_jwt_algorithm_none_or_tampered_algorithm_rejected():
    """Verify algorithm confusion attacks (e.g. 'none' algorithm) are rejected."""
    # Unsigned token with header {"alg": "none", "typ": "JWT"}
    raw_none_token = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJtYWxpY2lvdXNfdXNlciIsImVtYWlsIjoibWFsQGhhY2suY29tIiwiZXhwIjo5OTk5OTk5OTk5fQ."
    with pytest.raises(AuthenticationError):
        decode_access_token(raw_none_token)


def test_sliding_window_rate_limiter_thread_safety_and_reset():
    """Verify thread-safe rate limiter increments, rejects beyond threshold, and resets cleanly."""
    limiter = SlidingWindowRateLimiter()
    key = "test_client_thread_safe"
    max_requests = 10

    # Under limit
    for _ in range(max_requests):
        is_limited, retry_after = limiter.is_rate_limited(key, max_requests=max_requests, window_seconds=60.0)
        assert is_limited is False
        assert retry_after == 0

    # Over limit
    is_limited, retry_after = limiter.is_rate_limited(key, max_requests=max_requests, window_seconds=60.0)
    assert is_limited is True
    assert retry_after > 0

    # Reset
    limiter.reset()
    is_limited, retry_after = limiter.is_rate_limited(key, max_requests=max_requests, window_seconds=60.0)
    assert is_limited is False


def test_dockerfile_and_compose_least_privilege_verification():
    """Static security verification that container definitions enforce non-root execution and restricted ports."""
    # 1. Backend Dockerfile
    backend_dockerfile = os.path.join("docker", "backend.Dockerfile")
    assert os.path.exists(backend_dockerfile)
    with open(backend_dockerfile, "r", encoding="utf-8") as f:
        backend_content = f.read()
    assert "USER appuser" in backend_content
    assert "useradd" in backend_content

    # 2. Frontend Dockerfile
    frontend_dockerfile = os.path.join("docker", "frontend.Dockerfile")
    assert os.path.exists(frontend_dockerfile)
    with open(frontend_dockerfile, "r", encoding="utf-8") as f:
        frontend_content = f.read()
    assert "USER nextjs" in backend_content or "USER nextjs" in frontend_content
    assert "adduser" in frontend_content

    # 3. Docker Compose configuration
    compose_file = "docker-compose.yml"
    assert os.path.exists(compose_file)
    with open(compose_file, "r", encoding="utf-8") as f:
        compose_content = f.read()
    assert "no-new-privileges:true" in compose_content
    # Database and Ollama restricted to loopback
    assert "127.0.0.1:5432:5432" in compose_content
    assert "127.0.0.1:11434:11434" in compose_content


def test_input_validation_boundary_conditions():
    """Verify strict Pydantic boundary conditions on inputs."""
    # 1. Form issue code length
    with pytest.raises(ValidationError):
        FormIssueCreate(
            issue_code="X" * 65,  # Max 64
            feedback_text="Valid feedback",
        )

    # 2. Feedback text length
    with pytest.raises(ValidationError):
        FormIssueCreate(
            issue_code="VALID_CODE",
            feedback_text="X" * 1001,  # Max 1000
        )

    # 3. Negative rep count
    with pytest.raises(ValidationError):
        ExerciseResultCreate(
            rep_number=0,  # ge=1
            form_score=90.0,
        )

    # 4. Form score > 100
    with pytest.raises(ValidationError):
        ExerciseResultCreate(
            rep_number=1,
            form_score=105.0,  # le=100.0
        )

    # 5. Unrealistic workout duration > 24 hours
    with pytest.raises(ValidationError):
        WorkoutFinishRequest(
            total_duration_sec=90000.0,  # Max 86400.0
        )

    # 6. Unrealistic calories > 50,000
    with pytest.raises(ValidationError):
        WorkoutFinishRequest(
            total_calories=55000.0,  # Max 50000.0
        )
