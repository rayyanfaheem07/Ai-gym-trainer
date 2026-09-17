from datetime import datetime

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.workout import WorkoutStatus
from backend.app.schemas.analytics import PaginatedWorkoutResponse
from backend.app.schemas.workout import (
    ExerciseSessionCreate,
    ExerciseSessionResponse,
    WorkoutDetailResponse,
    WorkoutFinishRequest,
    WorkoutResponse,
    WorkoutSessionCreate,
    WorkoutSessionResponse,
    WorkoutSessionUpdate,
    WorkoutStartRequest,
)
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.workout_service import WorkoutService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# --- Standard Phase 8 & 9 REST Endpoints ---


@router.post(
    "/start",
    response_model=WorkoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and start a new workout session",
    description="Initializes a new workout session for tracking exercise performance.",
)
async def start_workout(
    data: WorkoutStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutResponse:
    """Start a new workout session associated with the authenticated user."""
    return await WorkoutService.start_workout(db, data, user_id=current_user.id)


@router.post(
    "/{id}/finish",
    response_model=WorkoutResponse,
    summary="Finish an active workout session",
    description="Completes an in-progress workout session, validates state transitions, and finalizes duration.",
)
async def finish_workout(
    id: str,
    data: WorkoutFinishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutResponse:
    """Finish an active workout session owned by the authenticated user."""
    return await WorkoutService.finish_workout(db, workout_id=id, request=data, user_id=current_user.id)


@router.get(
    "/history",
    response_model=PaginatedWorkoutResponse,
    summary="Get paginated workout history with filtering",
    description="Retrieves a paginated list of workouts with optional filters for exercise, date range, and status.",
)
async def get_workout_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    exercise: str | None = Query(None, description="Filter by exercise name"),
    start_date: datetime | None = Query(None, description="Filter workouts starting on or after this ISO datetime"),
    end_date: datetime | None = Query(None, description="Filter workouts starting on or before this ISO datetime"),
    status: WorkoutStatus | None = Query(None, description="Filter by workout status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedWorkoutResponse:
    """Retrieve paginated and filtered workout history for the authenticated user."""
    return await AnalyticsService.list_paginated_history(
        db=db,
        user_id=current_user.id,
        exercise_name=exercise,
        start_date=start_date,
        end_date=end_date,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get(
    "",
    response_model=list[WorkoutResponse],
    summary="List workout history",
    description="Retrieves a list of workouts for the authenticated user, ordered by most recent.",
)
async def list_workouts(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    exercise: str | None = Query(None, description="Optional exercise filter"),
    start_date: datetime | None = Query(None, description="Optional start datetime filter"),
    end_date: datetime | None = Query(None, description="Optional end datetime filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkoutResponse]:
    """Retrieve workout sessions history for the authenticated user."""
    workouts = await WorkoutService.list_workouts(
        db,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return list(workouts)



@router.get(
    "/{id}",
    response_model=WorkoutDetailResponse,
    summary="Get workout session details",
    description="Returns full hierarchical details of a workout session, including all exercise sets and reps.",
)
async def get_workout(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutDetailResponse:
    """Retrieve detailed workout session metrics, exercise sets, and reps."""
    return await WorkoutService.get_workout(db, workout_id=id, user_id=current_user.id)


# --- Backward Compatibility Endpoints ---


@router.post(
    "/",
    response_model=WorkoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_workout_session_legacy(
    data: WorkoutSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy endpoint for starting workout session."""
    return await WorkoutService.start_workout(db, data, user_id=current_user.id)


@router.patch(
    "/{session_id}",
    response_model=WorkoutSessionResponse,
    include_in_schema=False,
)
async def update_workout_session_legacy(
    session_id: str,
    data: WorkoutSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy endpoint for updating workout session."""
    return await WorkoutService.finish_workout(db, workout_id=session_id, request=data, user_id=current_user.id)


@router.post(
    "/{session_id}/sets",
    response_model=ExerciseSessionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def add_exercise_set_legacy(
    session_id: str,
    data: ExerciseSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy endpoint for recording an exercise set."""
    # Verify ownership before adding set
    await WorkoutService.get_workout(db, workout_id=session_id, user_id=current_user.id)
    return await WorkoutService.add_exercise_session(db, workout_id=session_id, data=data)

