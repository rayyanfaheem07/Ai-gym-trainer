import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.workout import ExerciseSession, Workout, WorkoutStatus


@pytest.mark.asyncio
async def test_history_unauthenticated(async_client: AsyncClient):
    """Verify unauthenticated access to history returns 401."""
    res = await async_client.get("/api/v1/workouts/history")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_history_pagination_and_filtering(
    authenticated_async_client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
):
    """Verify paginated history returns correct page items, total count, and filters by exercise."""
    # Create 3 workouts for test_user: 2 squats, 1 pushup
    for i, ex in enumerate(["squat", "pushup", "squat"]):
        w = Workout(
            user_id=test_user.id,
            status=WorkoutStatus.COMPLETED,
            notes=f"Workout {i+1}",
            overall_form_score=90.0 + i,
        )
        db_session.add(w)
        await db_session.flush()

        s = ExerciseSession(
            workout_id=w.id,
            exercise_name=ex,
            completed_reps=5 + i,
            valid_reps=5 + i,
            average_form_score=90.0 + i,
        )
        db_session.add(s)
    await db_session.commit()

    # 1. Test pagination: page 1 of 2
    res_p1 = await authenticated_async_client.get("/api/v1/workouts/history?page=1&page_size=2")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert data_p1["total"] == 3
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 2
    assert data_p1["total_pages"] == 2
    assert len(data_p1["items"]) == 2

    # 2. Test pagination: page 2
    res_p2 = await authenticated_async_client.get("/api/v1/workouts/history?page=2&page_size=2")
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2["items"]) == 1

    # 3. Test filtering by exercise=squat
    res_squat = await authenticated_async_client.get("/api/v1/workouts/history?exercise=squat")
    assert res_squat.status_code == 200
    data_squat = res_squat.json()
    assert data_squat["total"] == 2
    assert len(data_squat["items"]) == 2

    # 4. Test filtering by exercise=pushup
    res_pushup = await authenticated_async_client.get("/api/v1/workouts/history?exercise=pushup")
    assert res_pushup.status_code == 200
    data_pushup = res_pushup.json()
    assert data_pushup["total"] == 1
    assert len(data_pushup["items"]) == 1
