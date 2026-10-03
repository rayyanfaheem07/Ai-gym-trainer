import logging
from collections import defaultdict

from backend.app.core.config import settings
from backend.app.models.workout import CoachingFeedback, Workout
from backend.app.schemas.coach import (
    CoachContext,
    CoachFeedbackResponse,
    CoachStructuredOutput,
    ExerciseSessionContext,
    FormIssueSummary,
)
from backend.app.schemas.profile import PersonalizationContext
from backend.app.services.coach_provider import (
    BaseCoachProvider,
    CoachProviderError,
    DeterministicFallbackCoachProvider,
    OllamaCoachProvider,
)
from backend.app.services.personalization_service import PersonalizationService
from backend.app.services.workout_service import WorkoutService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CoachService:
    @staticmethod
    def build_coach_context(
        workout: Workout,
        target_focus: str = "form_improvement",
        personalization: PersonalizationContext | None = None,
    ) -> CoachContext:
        """
        Extracts verified, fact-checked workout telemetry from the database.
        Guarantees that only authorized and clean metrics are exposed to the coach.
        Optionally incorporates structured user fitness profile and longitudinal trends.
        """
        exercise_contexts: list[ExerciseSessionContext] = []
        global_fault_counts: dict[str, int] = defaultdict(int)
        global_fault_severities: dict[str, str] = {}
        global_fault_samples: dict[str, list[str]] = defaultdict(list)

        total_reps = 0
        total_valid_reps = 0
        total_invalid_reps = 0

        # Process each exercise session (set) in the workout
        sessions = workout.exercise_sessions or []
        for sess in sessions:
            sess_fault_counts: dict[str, int] = defaultdict(int)
            sess_fault_severities: dict[str, str] = {}
            sess_fault_samples: dict[str, list[str]] = defaultdict(list)

            results = sess.results or sess.reps or []
            for rep in results:
                # Collect distinct issues for this specific repetition
                rep_issues: dict[str, tuple[str, str]] = {}

                # First ingest fine-grained form issues
                for issue in getattr(rep, "form_issues", []):
                    code = str(issue.issue_code).strip()
                    sev = str(getattr(issue.severity, "value", issue.severity) or "moderate")
                    text = str(issue.feedback_text or "").strip()
                    rep_issues[code] = (sev, text)

                # Next ingest string faults if not already captured by form_issues
                for fault in (rep.faults_detected or []):
                    fault_name = str(fault).strip()
                    if fault_name and fault_name not in rep_issues:
                        rep_issues[fault_name] = ("moderate", "")

                # Increment counts per distinct issue on this rep
                for code, (sev, text) in rep_issues.items():
                    sess_fault_counts[code] += 1
                    sess_fault_severities[code] = sev
                    global_fault_counts[code] += 1
                    global_fault_severities[code] = sev
                    if text and len(sess_fault_samples[code]) < 2:
                        sess_fault_samples[code].append(text)
                    if text and len(global_fault_samples[code]) < 3:
                        global_fault_samples[code].append(text)

            sess_summaries = [
                FormIssueSummary(
                    issue_type=code,
                    count=cnt,
                    severity=sess_fault_severities.get(code, "moderate"),
                    feedback_samples=sess_fault_samples.get(code, []),
                )
                for code, cnt in sess_fault_counts.items()
            ]

            ex_context = ExerciseSessionContext(
                exercise_name=sess.exercise_name,
                session_order=sess.session_order or 1,
                total_reps=sess.completed_reps,
                valid_reps=sess.valid_reps,
                invalid_reps=sess.invalid_reps,
                average_form_score=float(sess.average_form_score or 0.0),
                average_tempo_sec=float(sess.average_tempo_sec or 0.0),
                form_issues=sess_summaries,
            )
            exercise_contexts.append(ex_context)

            total_reps += sess.completed_reps
            total_valid_reps += sess.valid_reps
            total_invalid_reps += sess.invalid_reps

        # Top global form issues sorted by frequency
        top_issues = [
            FormIssueSummary(
                issue_type=code,
                count=cnt,
                severity=global_fault_severities.get(code, "moderate"),
                feedback_samples=global_fault_samples.get(code, []),
            )
            for code, cnt in sorted(global_fault_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Extract personalization attributes if present
        profile_dto = personalization.profile if personalization else None
        history_dto = personalization.history if personalization else None
        trends_dto = personalization.trends if personalization else []

        return CoachContext(
            workout_id=workout.id,
            session_date=workout.started_at,
            total_duration_sec=float(workout.total_duration_sec or 0.0),
            overall_form_score=float(workout.overall_form_score or 0.0),
            total_reps=total_reps,
            valid_reps=total_valid_reps,
            invalid_reps=total_invalid_reps,
            exercises=exercise_contexts,
            top_form_issues=top_issues,
            target_focus=target_focus,
            historical_notes=workout.notes,
            profile=profile_dto,
            personal_history=history_dto,
            personal_trends=trends_dto,
        )

    @classmethod
    async def generate_feedback(
        cls,
        db: AsyncSession,
        session_id: str,
        target_focus: str = "form_improvement",
        user_id: str | None = None,
        provider: BaseCoachProvider | None = None,
    ) -> CoachingFeedback:
        """
        Generates personalized post-workout coaching feedback and persists it into the database.
        Enforces user ownership, integrates profile preferences & personal trends, and ensures graceful fallback.
        """
        # Fetch workout with full eager loading and ownership validation
        workout = await WorkoutService.get_workout(db, workout_id=session_id, user_id=user_id)

        # Build personalization context if user_id is known
        personalization: PersonalizationContext | None = None
        effective_user_id = user_id or workout.user_id
        if effective_user_id:
            try:
                personalization = await PersonalizationService.build_personalization_context(
                    db, user_id=effective_user_id, current_workout_id=session_id
                )
            except Exception as err:
                logger.warning(f"Could not build personalization context: {err}", exc_info=True)

        # If target_focus was default and user has preferred_focus, harmonize
        effective_focus = target_focus
        if target_focus == "form_improvement" and personalization and personalization.profile.preferred_focus:
            effective_focus = f"{personalization.profile.preferred_focus}_focus"

        # Build secure factual context
        context = cls.build_coach_context(
            workout,
            target_focus=effective_focus,
            personalization=personalization,
        )

        structured_output: CoachStructuredOutput
        is_fallback = False
        llm_model = settings.OLLAMA_MODEL

        if provider is not None:
            # Explicit provider supplied (e.g. for testing)
            try:
                structured_output = await provider.generate_coaching(context)
            except CoachProviderError as err:
                logger.warning(f"Supplied provider failed: {err}. Triggering deterministic fallback.")
                fallback_provider = DeterministicFallbackCoachProvider()
                structured_output = await fallback_provider.generate_coaching(context)
                is_fallback = True
                llm_model = "deterministic-fallback"
        else:
            # Default to Ollama with graceful fallback
            ollama_provider = OllamaCoachProvider()
            try:
                structured_output = await ollama_provider.generate_coaching(context)
            except CoachProviderError as err:
                logger.warning(
                    f"Ollama coach provider unavailable ({err}). "
                    "Engaging deterministic rule-based coaching fallback."
                )
                fallback_provider = DeterministicFallbackCoachProvider()
                structured_output = await fallback_provider.generate_coaching(context)
                is_fallback = True
                llm_model = f"{settings.OLLAMA_MODEL} (offline-fallback)"

        # Prepare recovery advice string merging focus and safety note if applicable
        recovery_parts = []
        if structured_output.next_session_focus:
            recovery_parts.append(f"Next Session Focus: {structured_output.next_session_focus}")
        if structured_output.safety_note:
            recovery_parts.append(f"Safety: {structured_output.safety_note}")
        recovery_text = " | ".join(recovery_parts) if recovery_parts else "Hydrate, rest, and stretch actively."

        # Fetch existing feedback or create new
        stmt = select(CoachingFeedback).where(CoachingFeedback.workout_id == session_id)
        res = await db.execute(stmt)
        feedback = res.scalar_one_or_none()

        if feedback is None:
            feedback = CoachingFeedback(
                workout_id=session_id,
                llm_model=llm_model,
                summary=structured_output.summary,
                strengths=structured_output.strengths,
                areas_to_improve=structured_output.areas_to_improve,
                recovery_advice=recovery_text,
            )
            db.add(feedback)
        else:
            feedback.llm_model = llm_model
            feedback.summary = structured_output.summary
            feedback.strengths = structured_output.strengths
            feedback.areas_to_improve = structured_output.areas_to_improve
            feedback.recovery_advice = recovery_text

        await db.commit()
        await db.refresh(feedback)

        # Attach transient metadata for serialization
        setattr(feedback, "_is_fallback", is_fallback)
        setattr(feedback, "_next_session_focus", structured_output.next_session_focus)
        setattr(feedback, "_safety_note", structured_output.safety_note)

        return feedback

    @classmethod
    def to_response_dto(cls, feedback: CoachingFeedback) -> CoachFeedbackResponse:
        """Converts CoachingFeedback ORM entity into typed Pydantic API response."""
        next_focus = getattr(feedback, "_next_session_focus", None)
        safety_note = getattr(feedback, "_safety_note", None)
        is_fallback = getattr(feedback, "_is_fallback", False)

        # If not transiently set, attempt parsing from recovery_advice
        if not next_focus and feedback.recovery_advice and "Next Session Focus: " in feedback.recovery_advice:
            parts = feedback.recovery_advice.split(" | ")
            for p in parts:
                if p.startswith("Next Session Focus: "):
                    next_focus = p.replace("Next Session Focus: ", "").strip()
                elif p.startswith("Safety: "):
                    safety_note = p.replace("Safety: ", "").strip()

        if "fallback" in (feedback.llm_model or "").lower():
            is_fallback = True

        return CoachFeedbackResponse(
            id=feedback.id,
            session_id=feedback.workout_id,
            llm_model=feedback.llm_model,
            summary=feedback.summary,
            strengths=feedback.strengths or [],
            areas_to_improve=feedback.areas_to_improve or [],
            recovery_advice=feedback.recovery_advice,
            next_session_focus=next_focus,
            safety_note=safety_note,
            is_fallback=is_fallback,
            created_at=feedback.created_at,
        )
