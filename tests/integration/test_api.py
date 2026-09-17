import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_workout_session(authenticated_async_client: AsyncClient):
    # 1. Create session
    payload = {"status": "in_progress"}
    res = await authenticated_async_client.post("/api/v1/workouts/", json=payload)
    assert res.status_code == 201
    session_data = res.json()
    session_id = session_data["id"]
    assert session_data["status"] == "in_progress"

    # 2. Add an exercise set
    set_payload = {
        "exercise_type": "squat",
        "set_number": 1,
        "completed_reps": 10,
        "valid_reps": 9,
        "invalid_reps": 1,
        "average_form_score": 92.5,
        "average_tempo_sec": 2.4,
        "reps": [
            {
                "rep_number": 1,
                "is_valid": 1,
                "form_score": 95.0,
                "duration_sec": 2.3,
                "faults_detected": [],
            }
        ],
    }
    set_res = await authenticated_async_client.post(
        f"/api/v1/workouts/{session_id}/sets", json=set_payload
    )
    assert set_res.status_code == 201

    # 3. Retrieve session details
    get_res = await authenticated_async_client.get(f"/api/v1/workouts/{session_id}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert len(retrieved["sets"]) == 1
    assert retrieved["sets"][0]["completed_reps"] == 10

