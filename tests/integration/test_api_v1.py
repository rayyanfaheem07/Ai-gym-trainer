import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_and_v1_health_endpoints(async_client: AsyncClient):
    # 1. Root /health
    res_root = await async_client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["status"] in ["ok", "degraded"]
    assert "version" in data_root
    assert "database_connected" in data_root

    # 2. /api/v1/health
    res_v1 = await async_client.get("/api/v1/health")
    assert res_v1.status_code == 200
    data_v1 = res_v1.json()
    assert data_v1["status"] in ["ok", "degraded"]


@pytest.mark.asyncio
async def test_exercises_endpoint(async_client: AsyncClient):
    res = await async_client.get("/api/v1/exercises")
    assert res.status_code == 200
    data = res.json()
    assert "exercises" in data
    assert data["count"] >= 5
    names = [e["name"] for e in data["exercises"]]
    assert "squat" in names
    assert "pushup" in names
    assert "bicep_curl" in names


@pytest.mark.asyncio
async def test_workouts_full_lifecycle_api(
    authenticated_async_client: AsyncClient,
    async_client: AsyncClient,
    second_auth_headers: dict[str, str],
):
    # 1. Start a workout
    start_payload = {
        "notes": "Legs and Core workout",
    }
    create_res = await authenticated_async_client.post("/api/v1/workouts/start", json=start_payload)
    assert create_res.status_code == 201
    workout_data = create_res.json()
    workout_id = workout_data["id"]
    assert workout_data["status"] == "in_progress"
    assert workout_data["user_id"] is not None

    # 2. Get workout details
    get_res = await authenticated_async_client.get(f"/api/v1/workouts/{workout_id}")
    assert get_res.status_code == 200
    details = get_res.json()
    assert details["id"] == workout_id
    assert details["status"] == "in_progress"

    # 3. List user workouts
    list_res = await authenticated_async_client.get("/api/v1/workouts")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data) >= 1
    assert any(w["id"] == workout_id for w in list_data)

    # 4. Finish the workout
    finish_payload = {
        "notes": "Session finished strong",
        "total_calories": 250.0,
        "overall_form_score": 91.5,
    }
    finish_res = await authenticated_async_client.post(
        f"/api/v1/workouts/{workout_id}/finish",
        json=finish_payload,
    )
    assert finish_res.status_code == 200
    finished_data = finish_res.json()
    assert finished_data["status"] == "completed"
    assert finished_data["total_calories"] == 250.0
    assert finished_data["overall_form_score"] == 91.5
    assert finished_data["ended_at"] is not None

    # 5. Duplicate finish should return 400 Bad Request
    dup_res = await authenticated_async_client.post(
        f"/api/v1/workouts/{workout_id}/finish",
        json=finish_payload,
    )
    assert dup_res.status_code == 400

    # 6. Non-existent workout finish should return 404
    nonexist_res = await authenticated_async_client.post(
        "/api/v1/workouts/invalid-nonexistent-id-0000/finish",
        json=finish_payload,
    )
    assert nonexist_res.status_code == 404

    # 7. Non-existent workout get should return 404
    nonexist_get = await authenticated_async_client.get("/api/v1/workouts/invalid-nonexistent-id-0000")
    assert nonexist_get.status_code == 404

    # 8. User boundary access control check: second user cannot access first user's workout
    unauthorized_res = await async_client.get(
        f"/api/v1/workouts/{workout_id}",
        headers=second_auth_headers,
    )
    assert unauthorized_res.status_code == 403


@pytest.mark.asyncio
async def test_analysis_endpoint(authenticated_async_client: AsyncClient):
    # 33 valid landmark points
    sample_landmarks = [
        {"x": 0.5, "y": 0.5 + i * 0.01, "z": 0.0, "visibility": 0.9}
        for i in range(33)
    ]

    payload = {
        "landmarks": sample_landmarks,
        "exercise_hint": "squat",
        "timestamp_ms": 500.0,
    }

    res = await authenticated_async_client.post("/api/v1/analysis", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "detected_exercise" in data
    assert "confidence" in data
    assert "stage" in data
    assert "form_score" in data
    assert "form_issues" in data
    assert 0.0 <= data["form_score"] <= 100.0

    # Invalid input (empty landmarks)
    bad_payload = {"landmarks": []}
    bad_res = await authenticated_async_client.post("/api/v1/analysis", json=bad_payload)
    assert bad_res.status_code in [400, 422, 500]

