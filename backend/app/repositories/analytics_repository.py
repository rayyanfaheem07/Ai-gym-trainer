import logging
from datetime import datetime, timedelta
from typing import Any, Sequence

from backend.app.models.base import get_utc_now
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    Workout,
    WorkoutStatus,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_lifetime_summary(self, user_id: str) -> dict[str, Any]:
        """Compute aggregated lifetime workout and repetition metrics for a user."""
        # 1. Total workouts and duration
        w_stmt = (
            select(
                func.count(Workout.id).label("total_workouts"),
                func.coalesce(func.sum(Workout.total_duration_sec), 0.0).label("total_duration_sec"),
                func.coalesce(func.avg(Workout.overall_form_score), 0.0).label("avg_workout_form_score"),
            )
            .where(Workout.user_id == user_id)
        )
        w_res = await self.session.execute(w_stmt)
        w_row = w_res.one()

        total_workouts = int(w_row.total_workouts or 0)
        total_duration_sec = float(w_row.total_duration_sec or 0.0)

        # 2. Total reps, valid reps, invalid reps from exercise sessions
        s_stmt = (
            select(
                func.count(ExerciseSession.id).label("total_sessions"),
                func.coalesce(func.sum(ExerciseSession.completed_reps), 0).label("total_reps"),
                func.coalesce(func.sum(ExerciseSession.valid_reps), 0).label("total_valid_reps"),
                func.coalesce(func.sum(ExerciseSession.invalid_reps), 0).label("total_invalid_reps"),
                func.coalesce(func.avg(ExerciseSession.average_form_score), 0.0).label("avg_form_score"),
            )
            .select_from(ExerciseSession)
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id)
        )
        s_res = await self.session.execute(s_stmt)
        s_row = s_res.one()

        total_reps = int(s_row.total_reps or 0)
        total_valid_reps = int(s_row.total_valid_reps or 0)
        total_invalid_reps = int(s_row.total_invalid_reps or 0)
        avg_form = float(s_row.avg_form_score or 0.0)
        if avg_form == 0.0 and w_row.avg_workout_form_score:
            avg_form = float(w_row.avg_workout_form_score)

        valid_rep_percentage = (
            round((total_valid_reps / total_reps) * 100.0, 1) if total_reps > 0 else 100.0
        )

        # 3. Recent workouts count (last 30 days)
        thirty_days_ago = get_utc_now() - timedelta(days=30)
        recent_stmt = (
            select(func.count(Workout.id))
            .where(Workout.user_id == user_id, Workout.created_at >= thirty_days_ago)
        )
        recent_res = await self.session.execute(recent_stmt)
        recent_count = int(recent_res.scalar() or 0)

        # 4. Most practiced exercise
        most_stmt = (
            select(ExerciseSession.exercise_name, func.count(ExerciseSession.id).label("cnt"))
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id)
            .group_by(ExerciseSession.exercise_name)
            .order_by(desc("cnt"))
            .limit(1)
        )
        most_res = await self.session.execute(most_stmt)
        most_row = most_res.first()
        most_practiced = most_row[0] if most_row else None

        # 5. Exercise breakdown
        breakdown_stmt = (
            select(
                ExerciseSession.exercise_name,
                func.count(ExerciseSession.id).label("total_sessions"),
                func.coalesce(func.sum(ExerciseSession.completed_reps), 0).label("total_reps"),
                func.coalesce(func.sum(ExerciseSession.valid_reps), 0).label("valid_reps"),
                func.coalesce(func.sum(ExerciseSession.invalid_reps), 0).label("invalid_reps"),
                func.coalesce(func.avg(ExerciseSession.average_form_score), 0.0).label("avg_score"),
                func.coalesce(func.max(ExerciseSession.average_form_score), 0.0).label("best_score"),
            )
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id)
            .group_by(ExerciseSession.exercise_name)
            .order_by(desc("total_sessions"))
        )
        breakdown_res = await self.session.execute(breakdown_stmt)
        breakdown_rows = breakdown_res.all()

        exercise_breakdown = []
        for r in breakdown_rows:
            r_reps = int(r.total_reps or 0)
            r_valid = int(r.valid_reps or 0)
            r_acc = round((r_valid / r_reps) * 100.0, 1) if r_reps > 0 else 100.0
            exercise_breakdown.append({
                "exercise_name": r.exercise_name,
                "total_sessions": int(r.total_sessions or 0),
                "total_reps": r_reps,
                "valid_reps": r_valid,
                "invalid_reps": int(r.invalid_reps or 0),
                "accuracy_percentage": r_acc,
                "average_form_score": round(float(r.avg_score or 0.0), 1),
                "best_form_score": round(float(r.best_score or 0.0), 1),
                "total_duration_sec": 0.0,
            })

        return {
            "total_workouts": total_workouts,
            "total_reps": total_reps,
            "total_valid_reps": total_valid_reps,
            "total_invalid_reps": total_invalid_reps,
            "valid_rep_percentage": valid_rep_percentage,
            "average_form_score": round(avg_form, 1),
            "total_duration_sec": round(total_duration_sec, 1),
            "most_practiced_exercise": most_practiced,
            "recent_workout_count": recent_count,
            "exercise_breakdown": exercise_breakdown,
        }

    async def get_exercise_analytics(self, user_id: str, exercise_name: str) -> dict[str, Any]:
        """Detailed metrics, common faults, and history for a specific exercise."""
        # 1. Aggregate stats
        stmt = (
            select(
                func.count(ExerciseSession.id).label("total_sessions"),
                func.coalesce(func.sum(ExerciseSession.completed_reps), 0).label("total_reps"),
                func.coalesce(func.sum(ExerciseSession.valid_reps), 0).label("valid_reps"),
                func.coalesce(func.sum(ExerciseSession.invalid_reps), 0).label("invalid_reps"),
                func.coalesce(func.avg(ExerciseSession.average_form_score), 0.0).label("avg_score"),
                func.coalesce(func.max(ExerciseSession.average_form_score), 0.0).label("best_score"),
                func.coalesce(func.avg(ExerciseSession.average_tempo_sec), 0.0).label("avg_tempo"),
            )
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id, ExerciseSession.exercise_name == exercise_name)
        )
        res = await self.session.execute(stmt)
        row = res.one()

        total_sessions = int(row.total_sessions or 0)
        total_reps = int(row.total_reps or 0)
        valid_reps = int(row.valid_reps or 0)
        invalid_reps = int(row.invalid_reps or 0)
        valid_percentage = round((valid_reps / total_reps) * 100.0, 1) if total_reps > 0 else 100.0
        avg_score = round(float(row.avg_score or 0.0), 1)
        best_score = round(float(row.best_score or 0.0), 1)

        # 2. Common faults from FormIssue
        faults_stmt = (
            select(FormIssue.issue_code, FormIssue.feedback_text, func.count(FormIssue.id).label("count"))
            .join(ExerciseResult, FormIssue.exercise_result_id == ExerciseResult.id)
            .join(ExerciseSession, ExerciseResult.exercise_session_id == ExerciseSession.id)
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id, ExerciseSession.exercise_name == exercise_name)
            .group_by(FormIssue.issue_code, FormIssue.feedback_text)
            .order_by(desc("count"))
            .limit(5)
        )
        faults_res = await self.session.execute(faults_stmt)
        faults = [
            {"issue_code": f.issue_code, "feedback_text": f.feedback_text, "occurrences": int(f.count)}
            for f in faults_res.all()
        ]

        # 3. Recent workouts with this exercise
        recent_workouts_stmt = (
            select(Workout)
            .join(ExerciseSession, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id, ExerciseSession.exercise_name == exercise_name)
            .order_by(Workout.created_at.desc())
            .limit(10)
            .options(
                selectinload(Workout.exercise_sessions).selectinload(ExerciseSession.results),
                selectinload(Workout.feedback),
            )
        )
        recent_workouts_res = await self.session.execute(recent_workouts_stmt)
        recent_sessions = list(recent_workouts_res.scalars().unique())

        return {
            "exercise_name": exercise_name,
            "total_sessions": total_sessions,
            "total_reps": total_reps,
            "valid_reps": valid_reps,
            "invalid_reps": invalid_reps,
            "valid_rep_percentage": valid_percentage,
            "average_form_score": avg_score,
            "best_form_score": best_score,
            "average_duration_sec": 0.0,
            "common_faults": faults,
            "recent_sessions": recent_sessions,
        }

    async def get_trends(
        self,
        user_id: str,
        exercise_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve chronological workout points for time-series trend charting."""
        stmt = (
            select(Workout)
            .where(Workout.user_id == user_id)
            .order_by(Workout.started_at.asc())
            .options(
                selectinload(Workout.exercise_sessions).selectinload(ExerciseSession.results),
            )
        )
        if start_date:
            stmt = stmt.where(Workout.started_at >= start_date)
        if end_date:
            stmt = stmt.where(Workout.started_at <= end_date)

        res = await self.session.execute(stmt)
        workouts = res.scalars().unique().all()

        points = []
        for w in workouts:
            # If exercise filter specified, check matching sessions
            sessions = w.exercise_sessions or []
            if exercise_name:
                matched_sessions = [s for s in sessions if s.exercise_name == exercise_name]
                if not matched_sessions:
                    continue
                sess = matched_sessions[0]
                reps = sess.completed_reps
                valid_reps = sess.valid_reps
                score = sess.average_form_score
                ex_name = sess.exercise_name
            else:
                reps = sum(s.completed_reps for s in sessions)
                valid_reps = sum(s.valid_reps for s in sessions)
                score = w.overall_form_score or (sum(s.average_form_score for s in sessions) / len(sessions) if sessions else 0.0)
                ex_name = sessions[0].exercise_name if sessions else None

            valid_pct = round((valid_reps / reps) * 100.0, 1) if reps > 0 else 100.0
            dt = w.started_at
            points.append({
                "date": dt.strftime("%Y-%m-%d"),
                "timestamp": dt.timestamp() if dt else 0.0,
                "workout_id": w.id,
                "exercise_name": ex_name,
                "form_score": round(float(score), 1),
                "total_reps": reps,
                "valid_reps": valid_reps,
                "valid_rep_percentage": valid_pct,
                "duration_sec": round(float(w.total_duration_sec or 0.0), 1),
            })

        return points[-limit:]

    async def list_paginated_workouts(
        self,
        user_id: str,
        exercise_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: WorkoutStatus | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[Sequence[Workout], int]:
        """Fetch paginated, filtered user workout history with total count."""
        # Base filter condition
        conditions = [Workout.user_id == user_id]
        if status:
            conditions.append(Workout.status == status)
        if start_date:
            conditions.append(Workout.started_at >= start_date)
        if end_date:
            conditions.append(Workout.started_at <= end_date)

        # Count query
        count_stmt = select(func.count(func.distinct(Workout.id))).where(*conditions)
        if exercise_name:
            count_stmt = count_stmt.join(ExerciseSession, ExerciseSession.workout_id == Workout.id).where(
                ExerciseSession.exercise_name == exercise_name
            )
        count_res = await self.session.execute(count_stmt)
        total_count = int(count_res.scalar() or 0)

        # Items query
        items_stmt = select(Workout).where(*conditions)
        if exercise_name:
            items_stmt = items_stmt.join(ExerciseSession, ExerciseSession.workout_id == Workout.id).where(
                ExerciseSession.exercise_name == exercise_name
            )

        offset = max(0, (page - 1) * page_size)
        items_stmt = (
            items_stmt.distinct()
            .order_by(Workout.started_at.desc())
            .limit(page_size)
            .offset(offset)
            .options(
                selectinload(Workout.exercise_sessions)
                .selectinload(ExerciseSession.results)
                .selectinload(ExerciseResult.form_issues),
                selectinload(Workout.feedback),
            )
        )
        items_res = await self.session.execute(items_stmt)
        items = items_res.scalars().unique().all()

        return items, total_count

