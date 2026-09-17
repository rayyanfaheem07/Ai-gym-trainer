import json
from unittest.mock import AsyncMock

import numpy as np
import pytest

from backend.app.services.websocket_service import (
    MAX_WS_MESSAGE_SIZE,
    WebSocketConnectionManager,
    WebSocketService,
    WebSocketSessionTracker,
    normalize_exercise_name,
    parse_landmarks_to_numpy,
)


def test_normalize_exercise_name():
    assert normalize_exercise_name("squat") == "squat"
    assert normalize_exercise_name("SQUATS") == "squat"
    assert normalize_exercise_name("push-up") == "pushup"
    assert normalize_exercise_name("push_up") == "pushup"
    assert normalize_exercise_name("bicep curl") == "bicep_curl"
    assert normalize_exercise_name("bicep_curl") == "bicep_curl"
    assert normalize_exercise_name("shoulder press") == "shoulder_press"
    assert normalize_exercise_name("shoulder_press") == "shoulder_press"
    assert normalize_exercise_name("overhead_press") == "shoulder_press"
    assert normalize_exercise_name("lunges") == "lunge"
    assert normalize_exercise_name(None) == "squat"


def test_parse_landmarks_to_numpy_valid():
    raw_list = [
        {"x": 0.1 * i, "y": 0.2 * i, "z": 0.0, "visibility": 0.9}
        for i in range(33)
    ]
    arr = parse_landmarks_to_numpy(raw_list)
    assert arr is not None
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (33, 4)
    assert np.isclose(arr[0, 0], 0.0)
    assert np.isclose(arr[1, 0], 0.1)


def test_parse_landmarks_to_numpy_invalid():
    assert parse_landmarks_to_numpy(None) is None
    assert parse_landmarks_to_numpy("not-a-list") is None
    assert parse_landmarks_to_numpy([{"x": 1.0, "y": 1.0}]) is None  # < 33 points


def test_session_tracker_exercise_switching():
    tracker = WebSocketSessionTracker(user_id="user-123", default_exercise="squat")
    assert tracker.exercise_name == "squat"
    assert tracker.user_id == "user-123"

    # Switch exercise
    switched = tracker.set_exercise("bicep_curl")
    assert switched is True
    assert tracker.exercise_name == "bicep_curl"

    # Unsupported exercise
    switched_invalid = tracker.set_exercise("non_existent_exercise")
    assert switched_invalid is False
    assert tracker.exercise_name == "bicep_curl"


def test_session_tracker_in_memory_frame_processing():
    tracker = WebSocketSessionTracker(user_id="user-123", default_exercise="squat")
    tracker.start_session(exercise_name="squat")

    landmarks_np = np.zeros((33, 4), dtype=np.float32)
    landmarks_np[:, 3] = 0.95

    # Process frame
    res = tracker.process_frame(landmarks_np, timestamp_ms=100.0)
    assert res.exercise == "squat"
    assert res.rep_count == 0
    assert tracker.frame_count == 1
    assert 0 <= res.form_score <= 100


@pytest.mark.asyncio
async def test_websocket_service_handles_ping():
    manager = WebSocketConnectionManager()
    service = WebSocketService(manager)
    tracker = WebSocketSessionTracker(user_id="user-123")

    mock_ws = AsyncMock()
    await service.handle_incoming_message(mock_ws, tracker, json.dumps({"type": "ping"}))

    mock_ws.send_text.assert_called_once()
    sent_text = mock_ws.send_text.call_args[0][0]
    data = json.loads(sent_text)
    assert data["type"] == "pong"


@pytest.mark.asyncio
async def test_websocket_service_handles_payload_too_large():
    manager = WebSocketConnectionManager()
    service = WebSocketService(manager)
    tracker = WebSocketSessionTracker(user_id="user-123")

    mock_ws = AsyncMock()
    huge = "x" * (MAX_WS_MESSAGE_SIZE + 10)
    await service.handle_incoming_message(mock_ws, tracker, huge)

    mock_ws.send_text.assert_called_once()
    data = json.loads(mock_ws.send_text.call_args[0][0])
    assert data["type"] == "error"
    assert data["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_websocket_service_handles_malformed_json():
    manager = WebSocketConnectionManager()
    service = WebSocketService(manager)
    tracker = WebSocketSessionTracker(user_id="user-123")

    mock_ws = AsyncMock()
    await service.handle_incoming_message(mock_ws, tracker, "{invalid json content")

    mock_ws.send_text.assert_called_once()
    data = json.loads(mock_ws.send_text.call_args[0][0])
    assert data["type"] == "error"
    assert data["code"] == "INVALID_JSON"
