import logging
from collections import defaultdict
from datetime import timedelta

from backend.app.models.base import get_utc_now
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    Workout,
)
from backend.app.repositories.analytics_repository import AnalyticsRepository
from backend.app.repositories.profile_repository import ProfileRepository
from backend.app.schemas.profile import (
    PersonalHistoryContext,
    PersonalizationContext,
    PersonalTrend,
    PersonalTrendDirection,
    UserProfileResponse,
    UserProfileUpdate,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class PersonalizationService:
    @staticmethod
    async def get_profile(db: AsyncSession, user_id: str) -> UserProfileResponse:
        """Retrieve user profile or create default profile if none exists."""
        repo = ProfileRepository(db)
        profile = await repo.get_or_create(user_id)
        return UserProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            fitness_goal=profile.fitness_goal.value if hasattr(profile.fitness_goal, "value") else str(profile.fitness_goal),
            experience_level=profile.experience_level.value if hasattr(profile.experience_level, "value") else str(profile.experience_level),
            preferred_focus=profile.preferred_focus.value if hasattr(profile.preferred_focus, "value") else str(profile.preferred_focus),
            coaching_style=profile.coaching_style.value if hasattr(profile.coaching_style, "value") else str(profile.coaching_style),
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user_id: str,
        update_data: UserProfileUpdate,
    ) -> UserProfileResponse:
        """Update authenticated user's personalization profile."""
        repo = ProfileRepository(db)
        profile = await repo.update_profile(user_id, update_data)
        await db.commit()
        await db.refresh(profile)
        return UserProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            fitness_goal=profile.fitness_goal.value if hasattr(profile.fitness_goal, "value") else str(profile.fitness_goal),
            experience_level=profile.experience_level.value if hasattr(profile.experience_level, "value") else str(profile.experience_level),
            preferred_focus=profile.preferred_focus.value if hasattr(profile.preferred_focus, "value") else str(profile.preferred_focus),
            coaching_style=profile.coaching_style.value if hasattr(profile.coaching_style, "value") else str(profile.coaching_style),
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    @classmethod
    async def calculate_personal_trends(
        cls,
        db: AsyncSession,
        user_id: str,
        current_workout_id: str | None = None,
    ) -> tuple[PersonalHistoryContext, list[PersonalTrend]]:
        """
        Calculate deterministic personal trends and longitudinal history.
        Grounded exclusively in verified database records.
        """
        # 1. Fetch user's workout history chronologically (sessions loaded for rep rates)
        stmt = (
            select(Workout)
            .where(Workout.user_id == user_id)
            .order_by(Workout.started_at.asc())
            .options(
                selectinload(Workout.exercise_sessions),
            )
        )
        res = await db.execute(stmt)
        all_workouts = list(res.scalars().unique())

        # Exclude current workout if specified
        past_workouts = [w for w in all_workouts if current_workout_id is None or w.id != current_workout_id]
        total_past_workouts = len(past_workouts)

        # 2. Query analytics aggregate lifetime stats
        analytics_repo = AnalyticsRepository(db)
        lifetime_summary = await analytics_repo.get_lifetime_summary(user_id)

        most_practiced = lifetime_summary.get("most_practiced_exercise")
        lifetime_valid_pct = lifetime_summary.get("valid_rep_percentage")

        # 3. Handle insufficient history cases
        if total_past_workouts == 0:
            history = PersonalHistoryContext(
                workouts_completed=0,
                recent_workout_count=0,
                recent_form_score=None,
                previous_form_score=None,
                recurring_form_issues=[],
                most_practiced_exercise=most_practiced,
                valid_rep_percentage=lifetime_valid_pct,
                has_previous_workouts=False,
                comparison_available=False,
            )
            trends = [
                PersonalTrend(
                    metric="overall_form_score",
                    exercise=None,
                    current_value=None,
                    previous_value=None,
                    change=None,
                    direction=PersonalTrendDirection.INSUFFICIENT_DATA,
                    sufficient_data=False,
                    message="Insufficient historical workout data for trend analysis.",
                )
            ]
            return history, trends

        # Count workouts in the last 30 days
        thirty_days_ago = get_utc_now() - timedelta(days=30)
        recent_count = sum(1 for w in past_workouts if w.created_at and w.created_at >= thirty_days_ago)

        # 4. Extract recurring form issues across distinct past workout sessions via targeted indexed queries
        issue_session_occurrences: dict[str, set[str]] = defaultdict(set)

        # 4a. Query structured FormIssue codes
        issue_stmt = (
            select(FormIssue.issue_code, Workout.id)
            .join(ExerciseResult, FormIssue.exercise_result_id == ExerciseResult.id)
            .join(ExerciseSession, ExerciseResult.exercise_session_id == ExerciseSession.id)
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id)
        )
        if current_workout_id:
            issue_stmt = issue_stmt.where(Workout.id != current_workout_id)
        issue_res = await db.execute(issue_stmt)
        for issue_code, workout_id in issue_res.all():
            if issue_code:
                issue_session_occurrences[issue_code].add(workout_id)

        # 4b. Query faults_detected array on ExerciseResult if present
        fault_stmt = (
            select(ExerciseResult.faults_detected, Workout.id)
            .join(ExerciseSession, ExerciseResult.exercise_session_id == ExerciseSession.id)
            .join(Workout, ExerciseSession.workout_id == Workout.id)
            .where(Workout.user_id == user_id)
        )
        if current_workout_id:
            fault_stmt = fault_stmt.where(Workout.id != current_workout_id)
        fault_res = await db.execute(fault_stmt)
        for faults, workout_id in fault_res.all():
            if faults and isinstance(faults, list):
                for f in faults:
                    if f:
                        issue_session_occurrences[str(f)].add(workout_id)

        recurring_issues = [
            code for code, sessions in issue_session_occurrences.items()
            if len(sessions) >= 2
        ]

        if total_past_workouts == 1:
            single_workout = past_workouts[0]
            single_score = round(float(single_workout.overall_form_score or 0.0), 1)
            history = PersonalHistoryContext(
                workouts_completed=1,
                recent_workout_count=recent_count,
                recent_form_score=single_score,
                previous_form_score=None,
                recurring_form_issues=recurring_issues,
                most_practiced_exercise=most_practiced,
                valid_rep_percentage=lifetime_valid_pct,
                has_previous_workouts=True,
                comparison_available=False,
            )
            trends = [
                PersonalTrend(
                    metric="overall_form_score",
                    exercise=None,
                    current_value=single_score,
                    previous_value=None,
                    change=None,
                    direction=PersonalTrendDirection.INSUFFICIENT_DATA,
                    sufficient_data=False,
                    message="Single baseline workout recorded; trend calculation requires subsequent sessions.",
                )
            ]
            return history, trends

        # 5. Multi-workout trend calculations (total_past_workouts >= 2)
        # Partition into baseline (older workouts) vs recent (last 1-3 workouts depending on history size)
        if total_past_workouts <= 3:
            baseline_slice = past_workouts[:1]
            recent_slice = past_workouts[1:]
        else:
            mid = total_past_workouts // 2
            baseline_slice = past_workouts[:mid]
            recent_slice = past_workouts[mid:]

        # Form score calculations
        prev_scores = [float(w.overall_form_score or 0.0) for w in baseline_slice if w.overall_form_score]
        recent_scores = [float(w.overall_form_score or 0.0) for w in recent_slice if w.overall_form_score]

        prev_avg_score = round(sum(prev_scores) / len(prev_scores), 1) if prev_scores else 0.0
        recent_avg_score = round(sum(recent_scores) / len(recent_scores), 1) if recent_scores else 0.0

        form_delta = round(recent_avg_score - prev_avg_score, 1)
        if form_delta >= 2.0:
            form_dir = PersonalTrendDirection.IMPROVING
            form_msg = f"Form score improved by {form_delta:+.1f}% compared to prior baseline."
        elif form_delta <= -2.0:
            form_dir = PersonalTrendDirection.DECLINING
            form_msg = f"Form score declined by {abs(form_delta):.1f}% compared to prior baseline."
        else:
            form_dir = PersonalTrendDirection.STABLE
            form_msg = f"Form score remains stable around {recent_avg_score:.1f}%."

        trends: list[PersonalTrend] = [
            PersonalTrend(
                metric="overall_form_score",
                exercise=None,
                current_value=recent_avg_score,
                previous_value=prev_avg_score,
                change=form_delta,
                direction=form_dir,
                sufficient_data=True,
                message=form_msg,
            )
        ]

        # Valid-rep rate calculation
        def get_rep_rate(workouts: list[Workout]) -> float | None:
            tot = 0
            val = 0
            for w in workouts:
                for s in (w.exercise_sessions or []):
                    tot += s.completed_reps
                    val += s.valid_reps
            return round((val / tot) * 100.0, 1) if tot > 0 else None

        prev_rate = get_rep_rate(baseline_slice)
        recent_rate = get_rep_rate(recent_slice)

        if prev_rate is not None and recent_rate is not None:
            rate_delta = round(recent_rate - prev_rate, 1)
            if rate_delta >= 3.0:
                rate_dir = PersonalTrendDirection.IMPROVING
                rate_msg = f"Valid rep rate improved by {rate_delta:+.1f}% across recent workouts."
            elif rate_delta <= -3.0:
                rate_dir = PersonalTrendDirection.DECLINING
                rate_msg = f"Valid rep rate decreased by {abs(rate_delta):.1f}% compared to baseline."
            else:
                rate_dir = PersonalTrendDirection.STABLE
                rate_msg = f"Rep validity rate remains consistent at {recent_rate:.1f}%."

            trends.append(
                PersonalTrend(
                    metric="valid_rep_percentage",
                    exercise=None,
                    current_value=recent_rate,
                    previous_value=prev_rate,
                    change=rate_delta,
                    direction=rate_dir,
                    sufficient_data=True,
                    message=rate_msg,
                )
            )

        # 6. Exercise-specific trends
        exercise_sessions_map: dict[str, list[ExerciseSession]] = defaultdict(list)
        for w in past_workouts:
            for s in (w.exercise_sessions or []):
                exercise_sessions_map[s.exercise_name].append(s)

        for ex_name, s_list in exercise_sessions_map.items():
            if len(s_list) >= 2:
                ex_mid = len(s_list) // 2
                ex_base = s_list[:ex_mid]
                ex_rec = s_list[ex_mid:]

                ex_prev_avg = sum(float(s.average_form_score or 0.0) for s in ex_base) / len(ex_base)
                ex_rec_avg = sum(float(s.average_form_score or 0.0) for s in ex_rec) / len(ex_rec)
                ex_delta = round(ex_rec_avg - ex_prev_avg, 1)

                if ex_delta >= 2.0:
                    ex_dir = PersonalTrendDirection.IMPROVING
                    ex_msg = f"{ex_name.replace('_', ' ').title()} form score improved by {ex_delta:+.1f}%."
                elif ex_delta <= -2.0:
                    ex_dir = PersonalTrendDirection.DECLINING
                    ex_msg = f"{ex_name.replace('_', ' ').title()} form score declined by {abs(ex_delta):.1f}%."
                else:
                    ex_dir = PersonalTrendDirection.STABLE
                    ex_msg = f"{ex_name.replace('_', ' ').title()} form score remains steady at {round(ex_rec_avg, 1)}%."

                trends.append(
                    PersonalTrend(
                        metric=f"{ex_name}_form_score",
                        exercise=ex_name,
                        current_value=round(ex_rec_avg, 1),
                        previous_value=round(ex_prev_avg, 1),
                        change=ex_delta,
                        direction=ex_dir,
                        sufficient_data=True,
                        message=ex_msg,
                    )
                )

        history = PersonalHistoryContext(
            workouts_completed=total_past_workouts,
            recent_workout_count=recent_count,
            recent_form_score=recent_avg_score,
            previous_form_score=prev_avg_score,
            recurring_form_issues=recurring_issues,
            most_practiced_exercise=most_practiced,
            valid_rep_percentage=lifetime_valid_pct,
            has_previous_workouts=True,
            comparison_available=True,
        )

        return history, trends

    @classmethod
    async def build_personalization_context(
        cls,
        db: AsyncSession,
        user_id: str,
        current_workout_id: str | None = None,
    ) -> PersonalizationContext:
        """Constructs full PersonalizationContext container for the AI Coach."""
        profile = await cls.get_profile(db, user_id)
        history, trends = await cls.calculate_personal_trends(
            db, user_id=user_id, current_workout_id=current_workout_id
        )
        return PersonalizationContext(
            profile=profile,
            history=history,
            trends=trends,
        )
