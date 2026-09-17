from typing import Sequence

from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    Workout,
)
from backend.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class WorkoutRepository(BaseRepository[Workout]):
    def __init__(self, session: AsyncSession):
        super().__init__(Workout, session)

    async def get_workout_detailed(self, workout_id: str) -> Workout | None:
        """Fetch workout with full hierarchical eager loading."""
        stmt = (
            select(Workout)
            .where(Workout.id == workout_id)
            .options(
                selectinload(Workout.exercise_sessions)
                .selectinload(ExerciseSession.results)
                .selectinload(ExerciseResult.form_issues),
                selectinload(Workout.feedback),
                selectinload(Workout.user),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Workout]:
        """Fetch user workout history ordered by most recent."""
        stmt = (
            select(Workout)
            .order_by(Workout.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(Workout.exercise_sessions)
                .selectinload(ExerciseSession.results)
                .selectinload(ExerciseResult.form_issues),
                selectinload(Workout.feedback),
            )
        )
        if user_id is not None:
            stmt = stmt.where(Workout.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_workout(self, workout: Workout) -> Workout:
        self.session.add(workout)
        await self.session.flush()
        return workout

    async def add_exercise_session(
        self, exercise_session: ExerciseSession
    ) -> ExerciseSession:
        self.session.add(exercise_session)
        await self.session.flush()
        return exercise_session

    async def add_exercise_result(
        self, exercise_result: ExerciseResult
    ) -> ExerciseResult:
        self.session.add(exercise_result)
        await self.session.flush()
        return exercise_result

    async def add_form_issue(self, form_issue: FormIssue) -> FormIssue:
        self.session.add(form_issue)
        await self.session.flush()
        return form_issue
