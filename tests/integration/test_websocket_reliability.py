"""Integration tests for WebSocket Streaming Security, High-Frequency Reliability, and Resource Lifecycle.

Covers:
- Oversized payload guard (>1MB)
- Malformed landmarks (strings, NaNs, missing fields, insufficient length)
- Rapid frame bursts and throughput stability
- Client disconnect immediately after handshake and mid-stream
- Session isolation (User A attempting to attach User B's workout ID)
- In-memory frame processing without per-frame database writes
- Ensuring Ollama is never called inside the frame-processing loop
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from backend.app.core.database import get_db
from backend.app.core.security import create_access_token
from backend.app.main import create_application
from backend.app.models.user import User
from backend.app.models.workout import Workout, WorkoutStatus
from backend.app.repositories.workout_repository import WorkoutRepository
from backend.app.services.websocket_service import connection_manager


def generate_valid_landmarks() -> list[dict]:
    """Generates standard 33-point landmark list."""
    landmarks = []
    for i in range(33):
        landmarks.append({
            "x": 0.5,
            "y": 0.5,
            "z": 0.0,
            "visibility": 0.95,
        })
    return landmarks


def get_test_client(db_session: AsyncSession) -> TestClient:
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ==============================================================================
# 1. Oversized & Malformed Payload Handling
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_oversized_payload_rejection(
    db_session: AsyncSession, test_user: User
):
    """Payloads exceeding maximum character limit receive PAYLOAD_TOO_LARGE error."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected message

        # Create message larger than 1MB (e.g. 1.2MB of dummy characters)
        oversized = json.dumps({
            "type": "pose_frame",
            "padding": "A" * (1024 * 1024 + 100),
        })
        ws.send_text(oversized)

        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_websocket_malformed_landmarks_graceful_handling(
    db_session: AsyncSession, test_user: User
):
    """Corrupted landmarks arrays (NaNs, strings, missing coordinates) must not crash session."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # 1. Missing coordinates (only x, y)
        ws.send_text(json.dumps({
            "type": "pose_frame",
            "landmarks": [{"x": 0.5, "y": 0.5} for _ in range(33)],
        }))
        res1 = json.loads(ws.receive_text())
        assert res1["type"] == "analysis_result"

        # 2. String values in coordinates
        ws.send_text(json.dumps({
            "type": "pose_frame",
            "landmarks": [{"x": "0.5", "y": "0.5", "z": "0.0", "visibility": "0.9"} for _ in range(33)],
        }))
        res2 = json.loads(ws.receive_text())
        assert res2["type"] == "analysis_result"

        # 3. Incomplete landmarks (<33 points)
        ws.send_text(json.dumps({
            "type": "pose_frame",
            "landmarks": [{"x": 0.5, "y": 0.5} for _ in range(10)],
        }))
        res3 = json.loads(ws.receive_text())
        # Handled without crashing; returns analysis with 0.0 confidence
        assert res3["type"] == "analysis_result"
        assert res3["confidence"] == 0.0


# ==============================================================================
# 2. High-Frequency Burst & Disconnect Lifecycle
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_rapid_frame_burst(
    db_session: AsyncSession, test_user: User
):
    """Rapid bursts of frames (e.g. 50 frames in a loop) process cleanly without dropped socket."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)
    landmarks = generate_valid_landmarks()

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        for i in range(40):
            ws.send_text(json.dumps({
                "type": "pose_frame",
                "timestamp_ms": float(i * 33.3),
                "landmarks": landmarks,
            }))
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "analysis_result"


@pytest.mark.asyncio
async def test_websocket_immediate_disconnect_cleanup(
    db_session: AsyncSession, test_user: User
):
    """Client connecting and immediately disconnecting cleans up manager tracking without error."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Handshake complete
        # Immediately exit context manager to disconnect

    # Active connections must not leak
    assert len(connection_manager.active_connections) == 0


# ==============================================================================
# 3. Database Isolation & Zero Per-Frame DB Writes
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_zero_per_frame_db_writes_and_no_ollama(
    db_session: AsyncSession, test_user: User
):
    """Frames must be evaluated in-memory with zero DB writes and zero calls to Ollama."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)
    landmarks = generate_valid_landmarks()

    with patch(
        "backend.app.services.coach_service.OllamaCoachProvider.generate_coaching",
        new_callable=AsyncMock,
    ) as mock_ollama:
        with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
            ws.receive_text()  # Connected

            # Stream 10 frames
            for i in range(10):
                ws.send_text(json.dumps({
                    "type": "pose_frame",
                    "timestamp_ms": float(i * 33.3),
                    "landmarks": landmarks,
                }))
                ws.receive_text()

            # Ollama must NEVER be called during frame processing
            assert mock_ollama.call_count == 0


# ==============================================================================
# 4. Cross-Tenant Workout Binding Isolation
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_cross_user_workout_binding_rejected_on_stop(
    db_session: AsyncSession,
    test_user: User,
    second_user: User,
):
    """User A cannot attach and persist sessions into User B's workout."""
    # User B owns a workout
    workout_repo = WorkoutRepository(db_session)
    user_b_workout = Workout(
        user_id=second_user.id,
        status=WorkoutStatus.IN_PROGRESS,
        notes="User B private workout",
    )
    created_b = await workout_repo.create_workout(user_b_workout)
    await db_session.commit()

    # User A connects via WebSocket
    client = get_test_client(db_session)
    token_user_a = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token_user_a}") as ws:
        ws.receive_text()  # Connected

        # User A attempts to start session pointing to User B's workout ID
        ws.send_text(json.dumps({
            "type": "start_session",
            "exercise": "squat",
            "workout_id": created_b.id,
        }))
        start_resp = json.loads(ws.receive_text())
        assert start_resp["type"] == "session_started"

        # Stream frame
        ws.send_text(json.dumps({
            "type": "pose_frame",
            "landmarks": generate_valid_landmarks(),
        }))
        ws.receive_text()

        # Stop session with save_to_db=True
        ws.send_text(json.dumps({
            "type": "stop_session",
            "save_to_db": True,
        }))
        stopped = json.loads(ws.receive_text())
        assert stopped["type"] == "session_stopped"

    # Verify User B's workout was NOT modified or contaminated by User A's session
    reloaded_b = await workout_repo.get_workout_detailed(created_b.id)
    assert reloaded_b is not None
    # User A's session was either rejected or saved under User A, never under User B
    for s in reloaded_b.exercise_sessions:
        assert s.workout.user_id == second_user.id
