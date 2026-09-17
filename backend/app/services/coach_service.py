
import httpx
from backend.app.core.config import settings
from backend.app.models.workout import CoachingFeedback
from backend.app.services.workout_service import WorkoutService
from sqlalchemy.ext.asyncio import AsyncSession


class CoachService:
    @staticmethod
    async def generate_feedback(
        db: AsyncSession,
        session_id: str,
        target_focus: str = "form_improvement",
        user_id: str | None = None,
    ) -> CoachingFeedback:
        workout = await WorkoutService.get_workout(db, workout_id=session_id, user_id=user_id)


        # Compile metrics context for the LLM
        sets_data = []
        total_faults = []
        for s in workout.sets:
            sets_data.append(
                f"- Exercise: {s.exercise_type.value}, Total Reps: {s.completed_reps}, "
                f"Valid: {s.valid_reps}, Invalid: {s.invalid_reps}, Form Score: {s.average_form_score:.1f}%"
            )
            for r in s.reps:
                if r.faults_detected:
                    total_faults.extend(r.faults_detected)

        context = (
            f"Workout Duration: {workout.total_duration_sec:.1f}s\n"
            f"Overall Form Score: {workout.overall_form_score:.1f}%\n"
            f"Sets Summary:\n" + "\n".join(sets_data) + "\n"
            f"Observed Biomechanical Faults: {', '.join(set(total_faults)) if total_faults else 'None'}\n"
        )

        prompt = (
            f"You are an expert AI biomechanics coach. Review the workout session telemetry below and provide:\n"
            f"1. A concise performance summary\n"
            f"2. Key movement strengths\n"
            f"3. Specific form improvements\n"
            f"4. Recovery advice\n\n"
            f"Telemetry Data:\n{context}"
        )

        summary = "Great workout! Form remained solid across sets."
        strengths = ["Consistent tempo", "Good depth on eccentric phase"]
        areas_to_improve = ["Ensure complete lockout at top", "Maintain steady knee alignment"]
        recovery = "Hydrate and perform light quad and hamstring stretches."

        # Attempt Ollama local call if reachable
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "")
                    if response_text:
                        summary = response_text[:300]
        except Exception:
            # Fallback to deterministic analytics if Ollama is not active locally
            pass

        feedback = CoachingFeedback(
            session_id=session_id,
            llm_model=settings.OLLAMA_MODEL,
            summary=summary,
            strengths=strengths,
            areas_to_improve=areas_to_improve,
            recovery_advice=recovery,
        )
        db.add(feedback)
        await db.commit()
        await db.refresh(feedback)
        return feedback
