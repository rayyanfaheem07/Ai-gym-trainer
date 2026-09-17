import logging
from datetime import datetime, timedelta

from backend.app.models.base import get_utc_now
from backend.app.models.workout import WorkoutStatus
from backend.app.repositories.analytics_repository import AnalyticsRepository
from backend.app.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnalyticsTrendsResponse,
    ExerciseAnalyticsResponse,
    PaginatedWorkoutResponse,
    TrendPoint,
)
from backend.app.schemas.workout import WorkoutResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AnalyticsService:
    @staticmethod
    async def get_summary(db: AsyncSession, user_id: str) -> AnalyticsSummaryResponse:
        """Calculate aggregate performance summary for an athlete."""
        repo = AnalyticsRepository(db)
        data = await repo.get_lifetime_summary(user_id)
        logger.info(f"Generated analytics summary for user={user_id}: total_workouts={data['total_workouts']}")
        return AnalyticsSummaryResponse.model_validate(data)

    @staticmethod
    async def get_exercise_analytics(
        db: AsyncSession, user_id: str, exercise_name: str
    ) -> ExerciseAnalyticsResponse:
        """Calculate deep-dive metrics, fault frequencies, and history for a specific exercise."""
        repo = AnalyticsRepository(db)
        data = await repo.get_exercise_analytics(user_id, exercise_name)
        logger.info(f"Generated exercise analytics for user={user_id}, exercise={exercise_name}")
        return ExerciseAnalyticsResponse.model_validate(data)

    @staticmethod
    async def get_trends(
        db: AsyncSession,
        user_id: str,
        period: str = "all",
        exercise_name: str | None = None,
    ) -> AnalyticsTrendsResponse:
        """Generate chronological performance trend points over a selectable period."""
        repo = AnalyticsRepository(db)
        start_date: datetime | None = None
        now = get_utc_now()

        if period == "7d":
            start_date = now - timedelta(days=7)
        elif period == "30d":
            start_date = now - timedelta(days=30)
        elif period == "90d":
            start_date = now - timedelta(days=90)

        points_raw = await repo.get_trends(
            user_id=user_id,
            exercise_name=exercise_name,
            start_date=start_date,
            end_date=None,
        )
        points = [TrendPoint.model_validate(p) for p in points_raw]

        return AnalyticsTrendsResponse(
            period=period,
            exercise=exercise_name,
            total_points=len(points),
            points=points,
        )

    @staticmethod
    async def list_paginated_history(
        db: AsyncSession,
        user_id: str,
        exercise_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: WorkoutStatus | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> PaginatedWorkoutResponse:
        """Retrieve paginated, filtered workout history with pagination metadata."""
        repo = AnalyticsRepository(db)
        items, total = await repo.list_paginated_workouts(
            user_id=user_id,
            exercise_name=exercise_name,
            start_date=start_date,
            end_date=end_date,
            status=status,
            page=page,
            page_size=page_size,
        )

        total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
        workout_items = [WorkoutResponse.model_validate(w) for w in items]

        return PaginatedWorkoutResponse(
            items=workout_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
