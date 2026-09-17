import logging
from typing import Any

import numpy as np
from ai.exercises.registry import ExerciseRegistry
from backend.app.core.errors import AIInferenceError
from backend.app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    FormIssueItem,
)
from backend.app.services.ai_service import ai_inference_service

logger = logging.getLogger(__name__)


class AnalysisService:
    @staticmethod
    def process_analysis(request: AnalysisRequest) -> AnalysisResponse:
        """
        Orchestrates AI pose estimation, exercise recognition, and biomechanical form analysis.
        """
        try:
            landmarks_raw = request.landmarks
            if not landmarks_raw:
                raise ValueError("Landmarks list cannot be empty.")

            # Convert to numpy array
            landmarks_np = AnalysisService._convert_to_landmarks_numpy(landmarks_raw)

            # 1. Run AI Inference / Classification
            classification = ai_inference_service.predict_exercise(
                landmarks=landmarks_np,
                exercise_hint=request.exercise_hint,
            )
            detected_exercise = classification.get("exercise", "other")
            confidence = classification.get("confidence", 0.0)
            probabilities = classification.get("probabilities", {})
            is_stub = classification.get("is_stub", False)
            model_info = classification.get("model_info", "default")

            # 2. Extract Single Frame Landmark for Form Analyzer
            frame_landmarks = (
                landmarks_np[-1] if landmarks_np.ndim == 3 else landmarks_np
            )

            # 3. Form Analysis via Exercise Registry
            stage = "idle"
            rep_count = 0
            valid_reps = 0
            invalid_reps = 0
            form_score = 100.0
            form_issues: list[FormIssueItem] = []

            # Map canonical names (e.g., 'push_up' -> 'pushup')
            reg_name = detected_exercise.replace("_", "").lower()
            if reg_name == "pushup":
                reg_name = "pushup"
            elif reg_name == "bicepcurl":
                reg_name = "bicep_curl"
            elif reg_name == "shoulderpress":
                reg_name = "shoulder_press"

            analyzer = ExerciseRegistry.get_exercise(reg_name)
            if analyzer is not None and frame_landmarks.shape[0] >= 33:
                try:
                    result = analyzer.process_frame(
                        frame_landmarks, timestamp_ms=request.timestamp_ms
                    )
                    stage = getattr(result, "stage", "active")
                    rep_count = getattr(result, "reps_completed", 0)
                    valid_reps = getattr(result, "valid_reps", 0)
                    invalid_reps = getattr(result, "invalid_reps", 0)
                    form_score = getattr(result, "form_score", 100.0)

                    faults = getattr(result, "faults_detected", []) or getattr(
                        result, "warnings", []
                    )
                    for f in faults:
                        form_issues.append(
                            FormIssueItem(
                                code=str(f).lower().replace(" ", "_"),
                                severity="moderate",
                                message=str(f),
                                timestamp_ms=request.timestamp_ms,
                            )
                        )
                except Exception as ex:
                    logger.warning(f"Exercise analyzer warning for {reg_name}: {ex}")

            logger.info(
                f"Analysis completed: exercise={detected_exercise}, confidence={confidence:.2f}, "
                f"stage={stage}, form_score={form_score:.1f}"
            )

            return AnalysisResponse(
                detected_exercise=detected_exercise,
                confidence=round(float(confidence), 4),
                probabilities=probabilities,
                stage=stage,
                rep_count=rep_count,
                valid_reps=valid_reps,
                invalid_reps=invalid_reps,
                form_score=round(float(form_score), 1),
                form_issues=form_issues,
                is_stub=is_stub,
                model_info=model_info,
            )

        except ValueError as ve:
            raise AIInferenceError(f"Invalid input landmarks format: {ve}")
        except Exception as e:
            logger.error(f"Analysis service execution error: {e}", exc_info=True)
            raise AIInferenceError(f"AI analysis failed: {e}")

    @staticmethod
    def _convert_to_landmarks_numpy(landmarks_raw: Any) -> np.ndarray:
        """Parses various landmark formats into standardized (N, 33, 4) or (33, 4) array."""
        if isinstance(landmarks_raw, np.ndarray):
            return landmarks_raw

        # Handle list of dicts / LandmarkPoint objects
        if isinstance(landmarks_raw, list) and len(landmarks_raw) > 0:
            first = landmarks_raw[0]
            if isinstance(first, dict):
                pts = [
                    [d.get("x", 0.0), d.get("y", 0.0), d.get("z", 0.0), d.get("visibility", 1.0)]
                    for d in landmarks_raw
                ]
                return np.array(pts, dtype=np.float32)
            elif hasattr(first, "x") and hasattr(first, "y"):
                pts = [
                    [d.x, d.y, getattr(d, "z", 0.0), getattr(d, "visibility", 1.0)]
                    for d in landmarks_raw
                ]
                return np.array(pts, dtype=np.float32)
            elif isinstance(first, list):
                # Could be 2D sequence of frames or list of [x, y, z, v]
                arr = np.array(landmarks_raw, dtype=np.float32)
                return arr

        return np.array(landmarks_raw, dtype=np.float32)
