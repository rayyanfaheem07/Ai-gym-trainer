import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from backend.app.core.config import settings
from backend.app.schemas.coach import (
    CoachContext,
    CoachStructuredOutput,
)
from backend.app.schemas.profile import PersonalTrendDirection

logger = logging.getLogger(__name__)


class CoachProviderError(Exception):
    """Base exception for AI Coach provider failures."""
    pass


class CoachProviderUnavailableError(CoachProviderError):
    """Raised when the LLM service cannot be reached (e.g. connection refused)."""
    pass


class CoachProviderTimeoutError(CoachProviderError):
    """Raised when the LLM provider call exceeds the configured timeout."""
    pass


class CoachProviderValidationError(CoachProviderError):
    """Raised when the LLM output cannot be parsed into the expected structured format."""
    pass


class BaseCoachProvider(ABC):
    """Abstract interface defining the AI Coach provider contract."""

    @abstractmethod
    async def generate_coaching(self, context: CoachContext) -> CoachStructuredOutput:
        """
        Takes verified workout context facts and returns validated structured coaching output.
        """
        raise NotImplementedError


class OllamaCoachProvider(BaseCoachProvider):
    """
    Ollama LLM provider implementing secure, personalized, and constrained workout coaching.
    """

    SYSTEM_PROMPT = (
        "You are an expert fitness biomechanics coaching assistant for the Real-Time AI Gym Trainer.\n"
        "RULES & CONSTRAINTS:\n"
        "1. Use ONLY the supplied workout facts and personal history provided in the context.\n"
        "2. Never invent or hallucinate workout statistics, rep counts, form scores, trends, or dates.\n"
        "3. Never alter any numerical values provided in the telemetry.\n"
        "4. Do NOT diagnose medical conditions or give medical treatment advice.\n"
        "5. Give practical exercise-form cues based strictly on recorded biomechanical faults and recurring issues.\n"
        "6. Adapt pedagogical depth and tone to the athlete's Experience Level (beginner = simple & encouraging, advanced = technical biomechanics) and Coaching Style (concise, supportive, detailed, technical).\n"
        "7. Distinguish observed workout facts from actionable technique suggestions.\n"
        "8. Keep responses professional, clear, and grounded.\n"
        "9. Output MUST be valid JSON adhering strictly to the required schema keys:\n"
        '   - "summary": string (1-3 sentences)\n'
        '   - "strengths": list of strings (1-3 items)\n'
        '   - "areas_to_improve": list of strings (1-3 items)\n'
        '   - "next_session_focus": string\n'
        '   - "safety_note": string\n'
    )

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout_seconds = timeout_seconds or getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 30.0)

    def _build_prompt_payload(self, context: CoachContext) -> str:
        """Formats factual telemetry context and user personalization profile safely into prompt payload."""
        exercises_desc = []
        for ex in context.exercises:
            issues_desc = [
                f"{iss.issue_type} (count: {iss.count}, severity: {iss.severity})"
                for iss in ex.form_issues
            ]
            issues_str = ", ".join(issues_desc) if issues_desc else "None detected"
            exercises_desc.append(
                f"- Exercise: {ex.exercise_name}\n"
                f"  Total Reps: {ex.total_reps} (Valid: {ex.valid_reps}, Invalid: {ex.invalid_reps})\n"
                f"  Average Form Score: {ex.average_form_score:.1f}%\n"
                f"  Average Tempo: {ex.average_tempo_sec:.1f}s\n"
                f"  Biomechanical Faults: {issues_str}"
            )

        top_issues_desc = [
            f"- {iss.issue_type}: {iss.count} occurrences ({iss.severity} severity)"
            for iss in context.top_form_issues
        ]
        top_issues_str = "\n".join(top_issues_desc) if top_issues_desc else "None"

        # Personal profile section
        profile_lines = []
        if context.profile:
            profile_lines.append(f"Fitness Goal: {context.profile.fitness_goal}")
            profile_lines.append(f"Experience Level: {context.profile.experience_level}")
            profile_lines.append(f"Preferred Focus: {context.profile.preferred_focus}")
            profile_lines.append(f"Coaching Style: {context.profile.coaching_style}")
        profile_str = "\n".join(profile_lines) if profile_lines else "Standard athlete preferences"

        # Personal history & trends section
        history_lines = []
        if context.personal_history:
            history_lines.append(f"Lifetime Workouts Completed: {context.personal_history.workouts_completed}")
            history_lines.append(f"Recent Workouts (30 Days): {context.personal_history.recent_workout_count}")
            if context.personal_history.recurring_form_issues:
                history_lines.append(
                    f"Recurring Biomechanical Faults: {', '.join(context.personal_history.recurring_form_issues)}"
                )
            if context.personal_history.most_practiced_exercise:
                history_lines.append(f"Most Practiced Exercise: {context.personal_history.most_practiced_exercise}")

        if context.personal_trends:
            trend_descs = [f"- {t.metric}: {t.direction.value} ({t.message or 'N/A'})" for t in context.personal_trends]
            history_lines.append("Verified Deterministic Trends:\n" + "\n".join(trend_descs))

        history_str = "\n".join(history_lines) if history_lines else "No previous longitudinal history available"

        facts_text = (
            f"=== VERIFIED CURRENT WORKOUT FACTS ===\n"
            f"Session ID: {context.workout_id}\n"
            f"Duration: {context.total_duration_sec:.1f} seconds\n"
            f"Overall Form Score: {context.overall_form_score:.1f}%\n"
            f"Total Repetitions: {context.total_reps} ({context.valid_reps} valid, {context.invalid_reps} invalid)\n"
            f"Session Target Focus: {context.target_focus}\n\n"
            f"Exercise Sets Breakdown:\n"
            f"{chr(10).join(exercises_desc) if exercises_desc else 'No sets recorded'}\n\n"
            f"Session Form Issues:\n"
            f"{top_issues_str}\n\n"
            f"=== ATHLETE FITNESS PROFILE & PREFERENCES ===\n"
            f"{profile_str}\n\n"
            f"=== VERIFIED PERSONAL HISTORY & TRENDS ===\n"
            f"{history_str}\n"
            f"========================================\n"
            f"Provide your personalized coaching assessment as a valid JSON object matching the required schema."
        )
        return facts_text

    async def generate_coaching(self, context: CoachContext) -> CoachStructuredOutput:
        user_prompt = self._build_prompt_payload(context)
        endpoint = f"{self.base_url}/api/generate"

        payload: dict[str, Any] = {
            "model": self.model,
            "system": self.SYSTEM_PROMPT,
            "prompt": user_prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)
        except httpx.ConnectError as err:
            logger.warning(f"Ollama connection refused at {self.base_url}: {err}")
            raise CoachProviderUnavailableError(f"Ollama server is unreachable at {self.base_url}") from err
        except httpx.TimeoutException as err:
            logger.warning(f"Ollama request timed out after {self.timeout_seconds}s: {err}")
            raise CoachProviderTimeoutError(f"Ollama request timed out after {self.timeout_seconds} seconds") from err
        except httpx.HTTPError as err:
            logger.warning(f"Ollama HTTP communication error: {err}")
            raise CoachProviderError(f"Ollama HTTP error: {err}") from err
        except Exception as err:
            logger.error(f"Unexpected error communicating with Ollama: {err}", exc_info=True)
            raise CoachProviderError(f"Unexpected provider error: {err}") from err

        if response.status_code != 200:
            logger.warning(f"Ollama returned non-200 status {response.status_code}: {response.text}")
            raise CoachProviderError(f"Ollama returned HTTP status {response.status_code}")

        try:
            resp_json = response.json()
            raw_text = resp_json.get("response", "")
            if not raw_text:
                raise CoachProviderValidationError("Ollama returned empty response payload")

            parsed_data = json.loads(raw_text)
            return CoachStructuredOutput.model_validate(parsed_data)
        except (json.JSONDecodeError, ValueError) as err:
            logger.warning(f"Failed to parse or validate Ollama structured response: {err}")
            raise CoachProviderValidationError(f"Invalid structured JSON from Ollama: {err}") from err


class DeterministicFallbackCoachProvider(BaseCoachProvider):
    """
    Deterministic rule-based personalized coach provider.
    Used when local Ollama is offline or unavailable.
    Provides mathematically accurate coaching derived strictly from persisted telemetry and profile preferences.
    """

    ISSUE_REMEDIATION_MAP = {
        "shallow_depth": "Focus on squat depth by lowering your hips until the crease passes below the top of your knees.",
        "knee_valgus": "Actively push your knees outward in line with your middle toes to prevent inward knee valgus.",
        "incomplete_lockout": "Ensure complete joint lockout and full extension at the top of each repetition.",
        "forward_lean": "Keep your chest tall and maintain a neutral, upright torso throughout the lift.",
        "asymmetric_hips": "Distribute your bodyweight evenly through both feet to prevent asymmetric hip shift.",
        "excessive_lumbar_extension": "Brace your core and avoid arching your lower back during overhead presses.",
        "elbow_flare": "Tuck your elbows to approximately a 45-degree angle relative to your torso to prevent elbow flare.",
        "uneven_shoulders": "Ensure bilateral shoulder retraction and balanced pressing height.",
        "fast_eccentric": "Control the lowering (eccentric) tempo over 2-3 seconds to maximize muscular tension.",
    }

    async def generate_coaching(self, context: CoachContext) -> CoachStructuredOutput:
        """Generates deterministic, fact-grounded personalized feedback."""
        exercise_names = [e.exercise_name.replace("_", " ").title() for e in context.exercises]
        exercises_str = ", ".join(exercise_names) if exercise_names else "Workout Session"

        # Coaching style and experience modifiers
        coaching_style = getattr(context.profile, "coaching_style", "supportive") or "supportive"
        experience_level = getattr(context.profile, "experience_level", "beginner") or "beginner"

        # 1. Summary computation
        if context.total_reps == 0:
            summary = f"Recorded a {context.total_duration_sec:.0f}s {exercises_str} session without completed repetitions."
        else:
            acc_rate = (context.valid_reps / context.total_reps) * 100 if context.total_reps > 0 else 100
            if coaching_style == "concise":
                summary = (
                    f"{exercises_str}: {context.total_reps} total repetitions, {context.valid_reps} valid "
                    f"({acc_rate:.0f}% validity, {context.overall_form_score:.0f}% form score)."
                )
            elif coaching_style == "technical":
                summary = (
                    f"Completed {context.total_reps} total repetitions across {len(context.exercises)} set(s). "
                    f"Biomechanical validity index: {acc_rate:.1f}%; composite form integrity score: {context.overall_form_score:.1f}%."
                )
            else:
                summary = (
                    f"Completed {context.total_reps} total repetitions across {len(context.exercises)} set(s) "
                    f"with a {acc_rate:.0f}% validity rate and {context.overall_form_score:.0f}% form score."
                )

        # 2. Strengths computation (integrates personal trend insights)
        strengths: list[str] = []
        if context.overall_form_score >= 85:
            strengths.append(f"High overall form integrity score of {context.overall_form_score:.0f}%.")
        if context.valid_reps >= 10:
            strengths.append(f"Strong repetition volume with {context.valid_reps} valid reps executed.")
        elif context.valid_reps > 0:
            strengths.append("Consistent exercise engagement and good baseline movement mechanics.")

        # Check for improving longitudinal trends
        for trend in context.personal_trends:
            if trend.direction == PersonalTrendDirection.IMPROVING and trend.metric == "overall_form_score":
                strengths.append(f"Positive progression: Form score improved by {trend.change:+.1f}% over previous baseline.")
            elif trend.direction == PersonalTrendDirection.IMPROVING and trend.metric == "valid_rep_percentage":
                strengths.append(f"Repetition accuracy increased by {trend.change:+.1f}% compared to earlier sessions.")

        if not strengths:
            strengths.append("Successfully initiated workout session and captured biomechanical telemetry.")

        # 3. Areas to improve computation (integrates recurring issues & faults)
        areas_to_improve: list[str] = []
        for issue in context.top_form_issues:
            code = issue.issue_type.lower()
            remediation = self.ISSUE_REMEDIATION_MAP.get(
                code,
                f"Address detected biomechanical fault '{issue.issue_type.replace('_', ' ')}' ({issue.count} occurrences).",
            )
            # Check if this issue is recurring in user's history
            if context.personal_history and issue.issue_type in context.personal_history.recurring_form_issues:
                remediation += " (Note: This is a recurring pattern observed across multiple workouts)."
            areas_to_improve.append(remediation)

        # Check for declining trends
        for trend in context.personal_trends:
            if trend.direction == PersonalTrendDirection.DECLINING and trend.metric == "overall_form_score":
                areas_to_improve.append(
                    f"Re-establish form consistency: recent average is {trend.change:.1f}% below your previous baseline."
                )

        if not areas_to_improve:
            if context.invalid_reps > 0:
                areas_to_improve.append("Focus on smooth cadence and controlled pacing on each rep.")
            else:
                areas_to_improve.append("Maintain progressive overload while preserving your current clean form.")

        # 4. Next session focus
        if context.personal_history and context.personal_history.recurring_form_issues:
            primary_rec = context.personal_history.recurring_form_issues[0].replace("_", " ")
            next_focus = f"Focus on eliminating recurring fault '{primary_rec}' during your warm-up and working sets."
        elif context.top_form_issues:
            primary_fault = context.top_form_issues[0].issue_type.replace("_", " ")
            next_focus = f"Prioritize correct movement mechanics for {primary_fault} on your next workout."
        else:
            next_focus = f"Maintain form precision and gradually increase repetition volume for {exercises_str}."

        # Safety note adjusted for experience
        if experience_level == "advanced":
            safety_note = "Maintain core intra-abdominal pressure and joint alignment under peak kinetic load."
        else:
            safety_note = (
                "Remember to warm up properly before sets and halt any movement if experiencing joint discomfort."
            )

        return CoachStructuredOutput(
            summary=summary,
            strengths=strengths[:3],
            areas_to_improve=areas_to_improve[:3],
            next_session_focus=next_focus,
            safety_note=safety_note,
        )
