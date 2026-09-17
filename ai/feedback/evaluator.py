from typing import Any, Dict

from ai.exercises.base import ExerciseState


class FeedbackEvaluator:
    """
    Synthesizes and prioritizes form warnings, computes rolling form scores, and debounces audio alerts.
    """

    def __init__(self, audio_debounce_ms: float = 3000.0):
        self.audio_debounce_ms = audio_debounce_ms
        self.last_audio_cue_time: float = 0.0
        self.last_cue_text: str | None = None

    def process_feedback(
        self, state: ExerciseState, timestamp_ms: float
    ) -> Dict[str, Any]:
        """
        Formats real-time feedback and filters repetitive audio cues.
        """
        cue_to_play = None
        if state.audio_cue:
            if (
                state.audio_cue != self.last_cue_text
                or (timestamp_ms - self.last_audio_cue_time) > self.audio_debounce_ms
            ):
                cue_to_play = state.audio_cue
                self.last_cue_text = state.audio_cue
                self.last_audio_cue_time = timestamp_ms

        return {
            "stage": state.stage,
            "rep_count": state.rep_count,
            "valid_reps": state.valid_reps,
            "invalid_reps": state.invalid_reps,
            "form_score": state.current_form_score,
            "primary_angle": state.primary_angle,
            "current_angles": state.current_angles,
            "warnings": state.active_warnings,
            "audio_cue": cue_to_play,
        }
