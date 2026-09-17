import logging
from datetime import UTC
from typing import Sequence

from backend.app.core.errors import (
    EntityNotFoundError,
    ForbiddenAccessError,
    InvalidStateTransitionError,
)
from backend.app.models.base import get_utc_now
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    Workout,
    WorkoutStatus,
)
from backend.app.repositories.workout_repository import WorkoutRepository
from backend.app.schemas.workout import (
    ExerciseSessionCreate,
    ExerciseSetCreate,
    WorkoutFinishRequest,
    WorkoutSessionCreate,
    WorkoutSessionUpdate,
    WorkoutStartRequest,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class WorkoutService:
    @staticmethod
    async def start_workout(
        db: AsyncSession,
        request: WorkoutStartRequest,
        user_id: str | None = None,
    ) -> Workout:
        """
        Creates and starts a new workout session.
        Uses authenticated user_id if provided.
        """
        repo = WorkoutRepository(db)
        effective_user_id = user_id or request.user_id
        workout = Workout(
            user_id=effective_user_id,
            status=WorkoutStatus.IN_PROGRESS,
            started_at=get_utc_now(),
            notes=request.notes,
        )
        created = await repo.create_workout(workout)
        await db.commit()
        logger.info(f"Started new workout session: id={created.id}, user_id={created.user_id}")
        return await repo.get_workout_detailed(created.id)  # type: ignore


    @staticmethod
    async def finish_workout(
        db: AsyncSession,
        workout_id: str,
        request: WorkoutFinishRequest,
        user_id: str | None = None,
    ) -> Workout:
        """
        Finishes an active workout with strict state validation and ownership checking.
        """
        repo = WorkoutRepository(db)
        workout = await repo.get_workout_detailed(workout_id)

        if not workout:
            logger.warning(f"Finish workout failed: workout {workout_id} not found.")
            raise EntityNotFoundError("Workout", workout_id)

        # Enforce user boundary if user_id is provided
        if user_id is not None and workout.user_id is not None and workout.user_id != user_id:
            logger.warning(f"Unauthorized attempt by user {user_id} to finish workout {workout_id}")
            raise ForbiddenAccessError("You do not have permission to modify this workout.")

        # State transition validation
        if workout.status == WorkoutStatus.COMPLETED:
            logger.warning(f"Workout {workout_id} is already completed.")
            raise InvalidStateTransitionError("Workout is already completed.")
        if workout.status == WorkoutStatus.CANCELLED:
            logger.warning(f"Workout {workout_id} is cancelled and cannot be finished.")
            raise InvalidStateTransitionError("Cannot finish a cancelled workout.")

        # Update workout state and compute metrics
        now = get_utc_now()
        workout.status = WorkoutStatus.COMPLETED
        workout.ended_at = now

        if request.total_duration_sec is not None:
            workout.total_duration_sec = request.total_duration_sec
        elif workout.started_at:
            started_at = workout.started_at
            if started_at.tzinfo is None and now.tzinfo is not None:
                now_val = now.replace(tzinfo=None)
            elif started_at.tzinfo is not None and now.tzinfo is None:
                now_val = now.replace(tzinfo=UTC)
            else:
                now_val = now
            delta = (now_val - started_at).total_seconds()
            workout.total_duration_sec = max(0.0, float(delta))

        if request.total_calories is not None:
            workout.total_calories = request.total_calories

        if request.overall_form_score is not None:
            workout.overall_form_score = request.overall_form_score
        elif workout.exercise_sessions:
            scores = [
                s.average_form_score
                for s in workout.exercise_sessions
                if s.average_form_score > 0
            ]
            workout.overall_form_score = sum(scores) / len(scores) if scores else 0.0

        if request.notes:
            workout.notes = request.notes

        await db.commit()
        logger.info(
            f"Successfully finished workout {workout_id}: duration={workout.total_duration_sec}s, "
            f"form_score={workout.overall_form_score}"
        )
        return await repo.get_workout_detailed(workout_id)  # type: ignore

    @staticmethod
    async def get_workout(
        db: AsyncSession,
        workout_id: str,
        user_id: str | None = None,
    ) -> Workout:
        """
        Retrieves detailed workout by ID with strict ownership boundaries.
        """
        repo = WorkoutRepository(db)
        workout = await repo.get_workout_detailed(workout_id)

        if not workout:
            logger.warning(f"Workout {workout_id} not found.")
            raise EntityNotFoundError("Workout", workout_id)

        if user_id is not None and workout.user_id is not None and workout.user_id != user_id:
            logger.warning(f"Access denied: User {user_id} attempted to view workout {workout_id}")
            raise ForbiddenAccessError("You do not have permission to view this workout.")

        return workout

    @staticmethod
    async def list_workouts(
        db: AsyncSession,
        user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Workout]:
        """
        Retrieves workout history for a user.
        """
        repo = WorkoutRepository(db)
        return await repo.list_by_user(user_id=user_id, limit=limit, offset=offset)

    @staticmethod
    async def add_exercise_session(
        db: AsyncSession,
        workout_id: str,
        data: ExerciseSessionCreate,
    ) -> ExerciseSession:
        """
        Records an exercise session and its results to a workout.
        """
        repo = WorkoutRepository(db)
        workout = await repo.get_by_id(workout_id)
        if not workout:
            raise EntityNotFoundError("Workout", workout_id)

        exercise_name = data.get_effective_exercise_name()
        session_order = data.session_order or data.set_number or 1
        session_obj = ExerciseSession(
            workout_id=workout_id,
            exercise_name=exercise_name,
            session_order=session_order,
            target_reps=data.target_reps,
            completed_reps=data.completed_reps,
            valid_reps=data.valid_reps,
            invalid_reps=data.invalid_reps,
            average_form_score=data.average_form_score,
            average_tempo_sec=data.average_tempo_sec,
        )
        await repo.add_exercise_session(session_obj)

        results_list = data.get_effective_results()
        for rep in results_list:
            result_obj = ExerciseResult(
                exercise_session_id=session_obj.id,
                rep_number=rep.rep_number,
                is_valid=rep.is_valid,
                form_score=rep.form_score,
                duration_sec=rep.duration_sec,
                eccentric_duration_sec=rep.eccentric_duration_sec,
                concentric_duration_sec=rep.concentric_duration_sec,
                min_joint_angle=rep.min_joint_angle,
                max_joint_angle=rep.max_joint_angle,
                faults_detected=rep.faults_detected,
            )
            await repo.add_exercise_result(result_obj)

            for issue in rep.form_issues:
                issue_obj = FormIssue(
                    exercise_result_id=result_obj.id,
                    issue_code=issue.issue_code,
                    severity=issue.severity,
                    feedback_text=issue.feedback_text,
                    timestamp_ms=issue.timestamp_ms,
                )
                await repo.add_form_issue(issue_obj)

        await db.commit()

        # Eager load created session with results and form issues
        stmt = (
            select(ExerciseSession)
            .where(ExerciseSession.id == session_obj.id)
            .options(
                selectinload(ExerciseSession.results).selectinload(ExerciseResult.form_issues)
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    # --- Backward compatibility aliases ---
    @staticmethod
    async def create_session(db: AsyncSession, data: WorkoutSessionCreate) -> Workout:
        return await WorkoutService.start_workout(db, data)

    @staticmethod
    async def get_session(db: AsyncSession, session_id: str) -> Workout | None:
        try:
            return await WorkoutService.get_workout(db, session_id)
        except EntityNotFoundError:
            return None

    @staticmethod
    async def list_sessions(
        db: AsyncSession, user_id: str | None = None, limit: int = 20
    ) -> Sequence[Workout]:
        return await WorkoutService.list_workouts(db, user_id=user_id, limit=limit)

    @staticmethod
    async def update_session(
        db: AsyncSession, session_id: str, data: WorkoutSessionUpdate
    ) -> Workout | None:
        try:
            return await WorkoutService.finish_workout(db, session_id, data)
        except (EntityNotFoundError, InvalidStateTransitionError):
            return None

    @staticmethod
    async def add_set(
        db: AsyncSession, session_id: str, set_data: ExerciseSetCreate
    ) -> ExerciseSession:
        return await WorkoutService.add_exercise_session(db, session_id, set_data)
