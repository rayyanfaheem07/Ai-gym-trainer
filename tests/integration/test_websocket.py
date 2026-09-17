import json
from datetime import timedelta

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from ai.pose.landmarks import LandmarkIndex
from backend.app.core.database import get_db
from backend.app.core.security import create_access_token
from backend.app.main import create_application
from backend.app.models.user import User
from backend.app.models.workout import Workout, WorkoutStatus
from backend.app.repositories.workout_repository import WorkoutRepository


def generate_mock_landmarks(
    knee_angle_deg: float = 175.0,
    hip_angle_deg: float = 170.0,
    visibility: float = 0.95,
):
    """
    Generates a 33-point landmark list with geometry matching the requested knee and hip angles.
    """
    landmarks_np = np.zeros((33, 4), dtype=np.float32)
    landmarks_np[:, 3] = visibility

    # Torso / Shoulder
    torso_rad = np.radians(180.0 - hip_angle_deg)
    landmarks_np[LandmarkIndex.LEFT_SHOULDER] = [
        0.45 - 0.3 * np.sin(torso_rad),
        0.5 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]
    landmarks_np[LandmarkIndex.RIGHT_SHOULDER] = [
        0.55 - 0.3 * np.sin(torso_rad),
        0.5 - 0.3 * np.cos(torso_rad),
        0.0,
        visibility,
    ]

    # Hips
    landmarks_np[LandmarkIndex.LEFT_HIP] = [0.45, 0.5, 0.0, visibility]
    landmarks_np[LandmarkIndex.RIGHT_HIP] = [0.55, 0.5, 0.0, visibility]

    # Knees
    landmarks_np[LandmarkIndex.LEFT_KNEE] = [0.45, 0.8, 0.0, visibility]
    landmarks_np[LandmarkIndex.RIGHT_KNEE] = [0.55, 0.8, 0.0, visibility]

    # Ankles based on knee angle
    flexion_rad = np.radians(180.0 - knee_angle_deg)
    shin_len = 0.3
    ankle_x = 0.45 + shin_len * np.sin(flexion_rad)
    ankle_y = 0.8 + shin_len * np.cos(flexion_rad)

    landmarks_np[LandmarkIndex.LEFT_ANKLE] = [ankle_x, ankle_y, 0.0, visibility]
    landmarks_np[LandmarkIndex.RIGHT_ANKLE] = [ankle_x + 0.1, ankle_y, 0.0, visibility]

    # Arms (Elbows, Wrists)
    landmarks_np[LandmarkIndex.LEFT_ELBOW] = [0.4, 0.4, 0.0, visibility]
    landmarks_np[LandmarkIndex.RIGHT_ELBOW] = [0.6, 0.4, 0.0, visibility]
    landmarks_np[LandmarkIndex.LEFT_WRIST] = [0.4, 0.25, 0.0, visibility]
    landmarks_np[LandmarkIndex.RIGHT_WRIST] = [0.6, 0.25, 0.0, visibility]

    return [
        {"x": float(lm[0]), "y": float(lm[1]), "z": float(lm[2]), "visibility": float(lm[3])}
        for lm in landmarks_np
    ]


def get_test_client(db_session: AsyncSession) -> TestClient:
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ==============================================================================
# 1. Authentication Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_rejects_missing_token(db_session: AsyncSession):
    client = get_test_client(db_session)
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/stream") as ws:
            ws.receive_text()


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(db_session: AsyncSession):
    client = get_test_client(db_session)
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/stream?token=invalid.jwt.token") as ws:
            ws.receive_text()


@pytest.mark.asyncio
async def test_websocket_rejects_expired_token(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    expired_token = create_access_token(
        subject=test_user.id,
        email=test_user.email,
        expires_delta=timedelta(minutes=-30),
    )
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/ws/stream?token={expired_token}") as ws:
            ws.receive_text()


@pytest.mark.asyncio
async def test_websocket_accepts_valid_token_and_sends_connected(
    db_session: AsyncSession, test_user: User
):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        connected_raw = ws.receive_text()
        connected = json.loads(connected_raw)
        assert connected["type"] == "connected"
        assert connected["status"] == "authenticated"
        assert connected["user_id"] == test_user.id
        assert "session_id" in connected


# ==============================================================================
# 2. Heartbeat & Basic Messaging Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_ping_pong(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected message

        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"
        assert "timestamp" in pong


# ==============================================================================
# 3. Session Lifecycle & Exercise Streaming Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_start_and_stop_session(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Start session
        ws.send_text(json.dumps({"type": "start_session", "exercise": "squat"}))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"
        assert started["exercise"] == "squat"
        assert "session_id" in started

        # Stream a pose frame
        ws.send_text(
            json.dumps({
                "type": "pose_frame",
                "timestamp_ms": 100.0,
                "landmarks": generate_mock_landmarks(knee_angle_deg=175.0),
            })
        )
        analysis = json.loads(ws.receive_text())
        assert analysis["type"] == "analysis_result"
        assert analysis["exercise"] == "squat"
        assert analysis["stage"] == "standing"

        # Stop session
        ws.send_text(json.dumps({"type": "stop_session", "save_to_db": False}))
        stopped = json.loads(ws.receive_text())
        assert stopped["type"] == "session_stopped"
        assert "summary" in stopped
        assert stopped["summary"]["user_id"] == test_user.id
        assert stopped["summary"]["frames_processed"] == 1


@pytest.mark.asyncio
async def test_websocket_all_five_exercises(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    exercises = ["squat", "pushup", "bicep_curl", "lunge", "shoulder_press"]

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        for ex in exercises:
            payload = {
                "type": "pose_frame",
                "timestamp_ms": 500.0,
                "exercise_override": ex,
                "landmarks": generate_mock_landmarks(),
            }
            ws.send_text(json.dumps(payload))
            resp = json.loads(ws.receive_text())
            assert resp["detected_exercise"] == ex
            assert 0 <= resp["form_score"] <= 100
            assert "stage" in resp


@pytest.mark.asyncio
async def test_websocket_squat_rep_progression(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Sequence: Standing (175) -> Descending (130) -> Bottom (85) -> Ascending (130) -> Lockout (168)
        timestamps = [0.0, 300.0, 700.0, 1100.0, 1500.0]
        angles = [175.0, 130.0, 85.0, 130.0, 168.0]

        responses = []
        for ts, angle in zip(timestamps, angles):
            payload = {
                "type": "pose_frame",
                "timestamp_ms": ts,
                "exercise_override": "squat",
                "landmarks": generate_mock_landmarks(knee_angle_deg=angle, hip_angle_deg=160.0),
            }
            ws.send_text(json.dumps(payload))
            resp = json.loads(ws.receive_text())
            responses.append(resp)

        phases = [r["stage"] for r in responses]
        assert "standing" in phases
        assert "descending" in phases
        assert "bottom" in phases
        assert "ascending" in phases
        assert responses[-1]["stage"] == "completed_rep"
        assert responses[-1]["rep_count"] == 1
        assert responses[-1]["valid_reps"] == 1


# ==============================================================================
# 4. Error Handling & Guard Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_error_handling_malformed_json(
    db_session: AsyncSession, test_user: User
):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Send non-JSON text
        ws.send_text("NOT_JSON_AT_ALL{{{")
        err_resp = json.loads(ws.receive_text())
        assert err_resp["type"] == "error"
        assert err_resp["code"] == "INVALID_JSON"


@pytest.mark.asyncio
async def test_websocket_unknown_message_type(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        ws.send_text(json.dumps({"type": "unsupported_custom_action"}))
        err_resp = json.loads(ws.receive_text())
        assert err_resp["type"] == "error"
        assert err_resp["code"] == "UNKNOWN_MESSAGE_TYPE"


@pytest.mark.asyncio
async def test_websocket_empty_and_invalid_landmarks(
    db_session: AsyncSession, test_user: User
):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Send empty landmarks list
        ws.send_text(json.dumps({"type": "pose_frame", "timestamp_ms": 1000.0, "landmarks": []}))
        empty_resp = json.loads(ws.receive_text())
        assert empty_resp["confidence"] == 0.0
        assert len(empty_resp["feedback"]) > 0


@pytest.mark.asyncio
async def test_websocket_payload_size_guard(db_session: AsyncSession, test_user: User):
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        huge_payload = "A" * (1_048_576 + 50)
        ws.send_text(huge_payload)
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "PAYLOAD_TOO_LARGE"


# ==============================================================================
# 5. Security & User Isolation Test
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_security_cannot_impersonate_user(
    db_session: AsyncSession, test_user: User, second_user: User
):
    """
    CRITICAL SECURITY TEST:
    Ensures that when User A connects with a valid JWT, any attempt to inject
    'user_id': User B into incoming payloads does NOT change the authenticated session identity.
    """
    client = get_test_client(db_session)
    token_user_a = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token_user_a}") as ws:
        conn = json.loads(ws.receive_text())
        assert conn["user_id"] == test_user.id

        # Attempt to spoof identity in start_session payload
        spoof_payload = {
            "type": "start_session",
            "exercise": "squat",
            "user_id": second_user.id,  # User B
        }
        ws.send_text(json.dumps(spoof_payload))
        started = json.loads(ws.receive_text())
        assert started["type"] == "session_started"

        # Stop session and inspect summary owner
        ws.send_text(json.dumps({"type": "stop_session", "save_to_db": False}))
        stopped = json.loads(ws.receive_text())
        # Server MUST keep User A as owner
        assert stopped["summary"]["user_id"] == test_user.id
        assert stopped["summary"]["user_id"] != second_user.id


# ==============================================================================
# 6. Database Persistence on Stop Session
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_persists_workout_session_on_stop(
    db_session: AsyncSession, test_user: User
):
    """
    Verifies that frames are processed in-memory, but when a workout_id is provided,
    calling stop_session persists the aggregated session to the database.
    """
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    # 1. Create active workout for user in DB
    workout_repo = WorkoutRepository(db_session)
    workout = Workout(
        user_id=test_user.id,
        status=WorkoutStatus.IN_PROGRESS,
        notes="Realtime WebSocket test workout",
    )
    created_workout = await workout_repo.create_workout(workout)
    await db_session.commit()

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Start session linked to workout
        ws.send_text(
            json.dumps({
                "type": "start_session",
                "exercise": "squat",
                "workout_id": created_workout.id,
            })
        )
        ws.receive_text()  # session_started

        # Stream rep progression
        timestamps = [0.0, 300.0, 700.0, 1100.0, 1500.0]
        angles = [175.0, 130.0, 85.0, 130.0, 168.0]
        for ts, angle in zip(timestamps, angles):
            ws.send_text(
                json.dumps({
                    "type": "pose_frame",
                    "timestamp_ms": ts,
                    "exercise": "squat",
                    "landmarks": generate_mock_landmarks(knee_angle_deg=angle),
                })
            )
            ws.receive_text()

        # Stop session with save_to_db=True
        ws.send_text(json.dumps({"type": "stop_session", "save_to_db": True}))
        stopped = json.loads(ws.receive_text())
        assert stopped["summary"]["persisted_to_db"] is True
        assert stopped["summary"]["total_reps"] == 1

    # Verify workout now has the exercise session in DB
    reloaded_workout = await workout_repo.get_workout_detailed(created_workout.id)
    assert reloaded_workout is not None
    assert len(reloaded_workout.exercise_sessions) == 1
    assert reloaded_workout.exercise_sessions[0].exercise_name == "squat"
    assert reloaded_workout.exercise_sessions[0].completed_reps == 1


# ==============================================================================
# 7. Additional Edge Case & Lifecycle Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_websocket_rejects_inactive_user(db_session: AsyncSession, test_user: User):
    """Verifies that an inactive user account is rejected even with a valid signature."""
    test_user.is_active = False
    await db_session.commit()

    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
            ws.receive_text()

    # Restore active state for safety
    test_user.is_active = True
    await db_session.commit()


@pytest.mark.asyncio
async def test_websocket_set_exercise_and_reset(db_session: AsyncSession, test_user: User):
    """Verifies set_exercise and reset client actions."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Set exercise to pushup
        ws.send_text(json.dumps({"type": "set_exercise", "exercise": "pushup"}))
        resp = json.loads(ws.receive_text())
        assert resp["status"] == "exercise_updated"
        assert resp["current_exercise"] == "pushup"

        # Reset exercise counters
        ws.send_text(json.dumps({"type": "reset"}))
        reset_resp = json.loads(ws.receive_text())
        assert reset_resp["status"] == "reset_completed"


@pytest.mark.asyncio
async def test_websocket_non_object_json_payload(db_session: AsyncSession, test_user: User):
    """Verifies that valid JSON non-objects (e.g. JSON array or int) are safely rejected."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected

        # Send JSON array
        ws.send_text(json.dumps([1, 2, 3]))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "error"
        assert resp["code"] == "INVALID_MESSAGE"


@pytest.mark.asyncio
async def test_websocket_clean_client_disconnect(db_session: AsyncSession, test_user: User):
    """Verifies that client disconnect is cleanly handled without server crashes."""
    client = get_test_client(db_session)
    token = create_access_token(subject=test_user.id, email=test_user.email)

    with client.websocket_connect(f"/api/v1/ws/stream?token={token}") as ws:
        ws.receive_text()  # Connected
        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"
        # Context manager exiting performs clean disconnect

