from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnalyticsTrendsResponse,
    ExerciseAnalyticsResponse,
)
from backend.app.services.analytics_service import AnalyticsService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user lifetime and recent workout analytics summary",
    description="Calculates lifetime totals, volume, accuracy, average form scores, and per-exercise breakdown for the authenticated athlete.",
)
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryResponse:
    """Retrieve comprehensive workout summary metrics for the authenticated user."""
    return await AnalyticsService.get_summary(db=db, user_id=current_user.id)


@router.get(
    "/exercises/{exercise}",
    response_model=ExerciseAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get exercise-specific performance statistics and fault analysis",
    description="Retrieves aggregate volume, best form score, common biomechanical faults, and recent sets for a specific exercise.",
)
async def get_exercise_analytics(
    exercise: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExerciseAnalyticsResponse:
    """Retrieve exercise-specific analytics and common fault breakdown."""
    return await AnalyticsService.get_exercise_analytics(
        db=db, user_id=current_user.id, exercise_name=exercise
    )


@router.get(
    "/trends",
    response_model=AnalyticsTrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chronological performance trend data points",
    description="Returns time-series telemetry points for form scores, reps, valid repetition percentage, and workout duration.",
)
async def get_analytics_trends(
    period: str = Query("all", description="Time period filter (all, 7d, 30d, 90d)"),
    exercise: str | None = Query(None, description="Optional exercise name filter"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsTrendsResponse:
    """Retrieve chronological trend telemetry points for charting."""
    return await AnalyticsService.get_trends(
        db=db, user_id=current_user.id, period=period, exercise_name=exercise
    )
