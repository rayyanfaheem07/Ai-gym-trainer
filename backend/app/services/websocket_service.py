import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.exercises.registry import ExerciseRegistry
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.errors import AuthenticationError
from backend.app.core.security import decode_access_token
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.websocket import (
    AnalysisResultResponse,
    ConnectedResponse,
    ErrorResponse,
    PongResponse,
    PoseFramePayload,
    SessionStartedResponse,
    SessionStoppedResponse,
    WSClientMessageType,
)
from backend.app.schemas.workout import (
    ExerciseResultCreate,
    ExerciseSessionCreate,
    FormIssueCreate,
)
from backend.app.services.workout_service import WorkoutService
from fastapi import WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Max incoming message payload size in characters (1 MB)
MAX_WS_MESSAGE_SIZE = 1_048_576


def normalize_exercise_name(exercise_name: str | None) -> str:
    """
    Normalizes human-entered exercise names to registry keys.
    """
    if not exercise_name:
        return "squat"
    norm = exercise_name.lower().strip().replace("-", "_").replace(" ", "_")
    if norm in ("pushup", "push_up"):
        return "pushup"
    if norm in ("bicep_curl", "bicepcurl", "curl"):
        return "bicep_curl"
    if norm in ("shoulder_press", "shoulderpress", "overhead_press"):
        return "shoulder_press"
    if norm in ("lunge", "lunges"):
        return "lunge"
    if norm in ("squat", "squats"):
        return "squat"
    return norm


def parse_landmarks_to_numpy(raw_landmarks: Any) -> np.ndarray | None:
    """
    Safely converts landmark lists / dicts to a standardized (33, 4) NumPy array.
    Returns None if payload is malformed or contains fewer than 33 landmarks.
    """
    if not raw_landmarks or not isinstance(raw_landmarks, list):
        return None
    if len(raw_landmarks) < 33:
        return None

    try:
        arr = []
        for lm in raw_landmarks[:33]:
            if isinstance(lm, dict):
                x = float(lm.get("x", 0.0))
                y = float(lm.get("y", 0.0))
                z = float(lm.get("z", 0.0))
                vis = float(lm.get("visibility", 1.0))
            elif isinstance(lm, (list, tuple)):
                x = float(lm[0]) if len(lm) > 0 else 0.0
                y = float(lm[1]) if len(lm) > 1 else 0.0
                z = float(lm[2]) if len(lm) > 2 else 0.0
                vis = float(lm[3]) if len(lm) > 3 else 1.0
            else:
                x = float(getattr(lm, "x", 0.0))
                y = float(getattr(lm, "y", 0.0))
                z = float(getattr(lm, "z", 0.0))
                vis = float(getattr(lm, "visibility", 1.0))
            arr.append([x, y, z, vis])
        return np.array(arr, dtype=np.float32)
    except Exception as e:
        logger.warning(f"Failed parsing landmarks to numpy: {e}")
        return None


class WebSocketSessionTracker:
    """
    Manages in-memory exercise state, rep tracking, and biomechanical telemetry
    for a single active WebSocket connection without incurring database writes per frame.
    """

    def __init__(self, user_id: str, default_exercise: str = "squat"):
        self.session_id: str = uuid.uuid4().hex
        self.user_id: str = user_id  # Bound strictly to validated JWT
        self.exercise_name: str = normalize_exercise_name(default_exercise)
        self.analyzer: BaseExerciseAnalyzer = (
            ExerciseRegistry.get_exercise(self.exercise_name) or ExerciseRegistry.get_exercise("squat")
        )
        self.workout_id: str | None = None
        self.is_session_active: bool = False
        self.started_at: datetime = datetime.now(UTC)
        self.frame_count: int = 0
        self.scores_history: list[float] = []
        self.last_rep_count: int = 0
        self.recorded_rep_results: list[dict[str, Any]] = []

    def set_exercise(self, exercise_name: str) -> bool:
        norm_name = normalize_exercise_name(exercise_name)
        if norm_name not in ExerciseRegistry.list_available():
            logger.warning(
                f"Requested unsupported exercise: '{exercise_name}'. Available: {ExerciseRegistry.list_available()}"
            )
            return False
        if norm_name != self.exercise_name or self.analyzer is None:
            new_analyzer = ExerciseRegistry.get_exercise(norm_name)
            if new_analyzer:
                self.exercise_name = norm_name
                self.analyzer = new_analyzer
                logger.info(f"Switched connection exercise to: {self.exercise_name}")
                return True
        return False

    def reset(self) -> None:
        if self.analyzer:
            self.analyzer.reset()
        self.frame_count = 0
        self.scores_history.clear()
        self.last_rep_count = 0
        self.recorded_rep_results.clear()

    def start_session(self, exercise_name: str | None = None, workout_id: str | None = None) -> str:
        self.session_id = uuid.uuid4().hex
        self.started_at = datetime.now(UTC)
        self.workout_id = workout_id
        self.is_session_active = True
        self.reset()
        if exercise_name:
            self.set_exercise(exercise_name)
        logger.info(
            f"Exercise session started: session_id={self.session_id}, user={self.user_id}, "
            f"exercise={self.exercise_name}, workout={self.workout_id}"
        )
        return self.session_id

    def process_frame(
        self,
        landmarks_np: np.ndarray | None,
        timestamp_ms: float,
    ) -> AnalysisResultResponse:
        """
        Processes a single frame entirely in memory using the exercise analyzer.
        Zero DB writes per frame.
        """
        self.frame_count += 1
        if self.analyzer is None:
            self.set_exercise(self.exercise_name)

        if landmarks_np is not None:
            result: ExerciseAnalysisResult = self.analyzer.analyze_frame(
                landmarks_np, timestamp_ms=timestamp_ms
            )
        else:
            # Fallback for no landmarks or invalid payload
            phase_val = (
                getattr(self.analyzer, "phase", "standing").value
                if hasattr(getattr(self.analyzer, "phase", None), "value")
                else str(getattr(self.analyzer, "phase", "ready"))
            )
            result = ExerciseAnalysisResult(
                exercise=self.exercise_name,
                phase=phase_val,
                rep_count=self.analyzer.rep_count if self.analyzer else 0,
                valid_reps=self.analyzer.valid_reps if self.analyzer else 0,
                invalid_reps=self.analyzer.invalid_reps if self.analyzer else 0,
                confidence=0.0,
                form_score=100,
                feedback=["No person or pose landmarks detected"],
            )

        # Track score history
        if result.confidence > 0.0:
            self.scores_history.append(float(result.form_score))

        # Check if a new repetition was completed to buffer summary
        if result.rep_count > self.last_rep_count:
            self.last_rep_count = result.rep_count
            self.recorded_rep_results.append({
                "rep_number": result.rep_count,
                "is_valid": result.is_valid_rep,
                "form_score": float(result.form_score),
                "duration_sec": result.rep_duration_sec,
                "eccentric_duration_sec": 0.0,
                "concentric_duration_sec": 0.0,
                "min_joint_angle": result.primary_angle,
                "max_joint_angle": result.primary_angle,
                "faults_detected": [
                    issue.get("details", issue.get("name", "Form fault"))
                    if isinstance(issue, dict)
                    else str(issue)
                    for issue in result.issues
                ],
                "form_issues": [
                    {
                        "issue_code": issue.get("name", "form_fault").lower().replace(" ", "_")
                        if isinstance(issue, dict)
                        else str(issue).lower().replace(" ", "_"),
                        "severity": issue.get("severity", "moderate")
                        if isinstance(issue, dict)
                        else "moderate",
                        "feedback_text": issue.get("details", str(issue))
                        if isinstance(issue, dict)
                        else str(issue),
                        "timestamp_ms": timestamp_ms,
                    }
                    for issue in result.issues
                ],
            })

        # Extract warnings and feedback
        warning_messages: list[str] = []
        if result.issues:
            for issue in result.issues:
                if isinstance(issue, dict):
                    warning_messages.append(issue.get("details", issue.get("name", "Form fault detected")))
                else:
                    warning_messages.append(str(issue))
        elif result.feedback and result.confidence > 0.0 and result.form_score < 80:
            warning_messages = result.feedback

        audio_cue = result.feedback[0] if result.feedback else None
        timestamp_sec = timestamp_ms / 1000.0 if timestamp_ms > 0 else time.time()

        return AnalysisResultResponse(
            timestamp=timestamp_sec,
            timestamp_ms=timestamp_ms,
            exercise=self.exercise_name,
            detected_exercise=self.exercise_name,
            stage=result.phase,
            rep_count=result.rep_count,
            valid_reps=result.valid_reps,
            invalid_reps=result.invalid_reps,
            is_valid_rep=result.is_valid_rep,
            confidence=float(result.confidence),
            current_angles=result.current_angles,
            primary_angle=result.primary_angle,
            form_score=float(result.form_score),
            warnings=warning_messages,
            feedback=result.feedback,
            issues=result.issues,
            audio_cue=audio_cue,
            rep_duration_sec=result.rep_duration_sec,
            metrics=result.metrics,
        )

    async def stop_session(
        self, db: AsyncSession | None = None, save_to_db: bool = True
    ) -> dict[str, Any]:
        """
        Stops the session and aggregates metrics.
        Persists to database only once at the end of the session if linked to a workout.
        """
        now = datetime.now(UTC)
        duration_sec = max(0.0, (now - self.started_at).total_seconds())
        rep_count = self.analyzer.rep_count if self.analyzer else 0
        valid_reps = self.analyzer.valid_reps if self.analyzer else 0
        invalid_reps = self.analyzer.invalid_reps if self.analyzer else 0
        avg_score = (
            sum(self.scores_history) / len(self.scores_history)
            if self.scores_history
            else 100.0
        )

        summary = {
            "session_id": self.session_id,
            "exercise": self.exercise_name,
            "user_id": self.user_id,
            "workout_id": self.workout_id,
            "total_reps": rep_count,
            "valid_reps": valid_reps,
            "invalid_reps": invalid_reps,
            "average_form_score": round(float(avg_score), 1),
            "duration_sec": round(duration_sec, 2),
            "frames_processed": self.frame_count,
            "persisted_to_db": False,
        }

        # Persist aggregated session if workout_id is set
        if save_to_db and self.workout_id:
            try:
                session_create_data = ExerciseSessionCreate(
                    exercise_name=self.exercise_name,
                    target_reps=rep_count,
                    completed_reps=rep_count,
                    valid_reps=valid_reps,
                    invalid_reps=invalid_reps,
                    average_form_score=round(float(avg_score), 1),
                    results=[
                        ExerciseResultCreate(
                            rep_number=r["rep_number"],
                            is_valid=r["is_valid"],
                            form_score=r["form_score"],
                            duration_sec=r["duration_sec"],
                            eccentric_duration_sec=r["eccentric_duration_sec"],
                            concentric_duration_sec=r["concentric_duration_sec"],
                            min_joint_angle=r["min_joint_angle"],
                            max_joint_angle=r["max_joint_angle"],
                            faults_detected=r["faults_detected"],
                            form_issues=[
                                FormIssueCreate(
                                    issue_code=fi["issue_code"],
                                    severity=fi["severity"],
                                    feedback_text=fi["feedback_text"],
                                    timestamp_ms=fi["timestamp_ms"],
                                )
                                for fi in r["form_issues"]
                            ],
                        )
                        for r in self.recorded_rep_results
                    ],
                )
                if db is not None:
                    await WorkoutService.add_exercise_session(
                        db=db,
                        workout_id=self.workout_id,
                        data=session_create_data,
                    )
                else:
                    async with AsyncSessionLocal() as session:
                        await WorkoutService.add_exercise_session(
                            db=session,
                            workout_id=self.workout_id,
                            data=session_create_data,
                        )
                summary["persisted_to_db"] = True
                logger.info(f"Persisted exercise session for workout {self.workout_id} successfully.")
            except Exception as e:
                logger.error(f"Failed to persist exercise session to DB on stop_session: {e}")
                summary["persistence_error"] = str(e)

        self.is_session_active = False
        return summary


class WebSocketConnectionManager:
    """
    Manages active WebSockets, authentication validation, and connection lifecycles.
    """

    def __init__(self):
        self.active_connections: dict[WebSocket, WebSocketSessionTracker] = {}

    async def authenticate_and_accept(
        self,
        websocket: WebSocket,
        token: str | None,
        db: AsyncSession | None = None,
    ) -> WebSocketSessionTracker | None:
        """
        Validates token, extracts sub claim, verifies user in DB, and accepts connection.
        Closes cleanly with code 1008 if authentication fails.
        """
        if not token:
            logger.warning("WebSocket rejected: Missing authentication token.")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Authentication token is required.",
            )
            return None

        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationError("Missing sub claim in token.")

            # Validate user existence and status in database
            if db is not None:
                user_repo = UserRepository(db)
                user: User | None = await user_repo.get_by_id(user_id)
            else:
                async with AsyncSessionLocal() as session:
                    user_repo = UserRepository(session)
                    user = await user_repo.get_by_id(user_id)

            if user is None:
                logger.warning(f"WebSocket rejected: User {user_id} not found.")
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User not found.",
                )
                return None
            if not user.is_active:
                logger.warning(f"WebSocket rejected: User {user_id} is inactive.")
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User account is inactive.",
                )
                return None

        except AuthenticationError as auth_err:
            logger.warning(f"WebSocket authentication failed: {auth_err}")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Authentication failed: {auth_err.message}",
            )
            return None
        except Exception as e:
            logger.warning(f"WebSocket unexpected authentication error: {e}")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid authentication token.",
            )
            return None

        # Accept connection and initialize session tracker
        await websocket.accept()
        tracker = WebSocketSessionTracker(user_id=user_id, default_exercise="squat")
        self.active_connections[websocket] = tracker

        # Send connected acknowledgement
        connected_msg = ConnectedResponse(
            status="authenticated",
            user_id=tracker.user_id,
            session_id=tracker.session_id,
            message="WebSocket connected and authenticated successfully.",
        )
        await websocket.send_text(connected_msg.model_dump_json())
        logger.info(f"WebSocket connection established for user {user_id}. Active: {len(self.active_connections)}")
        return tracker

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            tracker = self.active_connections.pop(websocket)
            logger.info(
                f"WebSocket disconnected: user={tracker.user_id}, session={tracker.session_id}. "
                f"Remaining: {len(self.active_connections)}"
            )

    def get_tracker(self, websocket: WebSocket) -> WebSocketSessionTracker | None:
        return self.active_connections.get(websocket)


class WebSocketService:
    """
    Core dispatcher handling client message processing and responses.
    """

    def __init__(self, manager: WebSocketConnectionManager):
        self.manager = manager

    async def handle_incoming_message(
        self,
        websocket: WebSocket,
        tracker: WebSocketSessionTracker,
        raw_text: str,
        db: AsyncSession | None = None,
    ) -> None:
        """
        Parses and routes incoming JSON message safely with rate/payload guards.
        """
        # 1. Payload size guard
        if len(raw_text) > MAX_WS_MESSAGE_SIZE:
            err = ErrorResponse(
                code="PAYLOAD_TOO_LARGE",
                message=f"Message size exceeds maximum limit of {MAX_WS_MESSAGE_SIZE} characters.",
            )
            await websocket.send_text(err.model_dump_json())
            return

        # 2. JSON decoding guard
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            err = ErrorResponse(
                code="INVALID_JSON",
                message="Malformed JSON payload. Please provide valid JSON.",
            )
            await websocket.send_text(err.model_dump_json())
            return

        if not isinstance(payload, dict):
            err = ErrorResponse(
                code="INVALID_MESSAGE",
                message="Message payload must be a JSON object.",
            )
            await websocket.send_text(err.model_dump_json())
            return

        # Extract message type
        msg_type = payload.get("type")

        # 3. Message Dispatching

        # Heartbeat / Ping
        if msg_type == WSClientMessageType.PING.value or msg_type == "ping":
            pong = PongResponse(timestamp=time.time())
            await websocket.send_text(pong.model_dump_json())
            return

        # Start Session
        if msg_type == WSClientMessageType.START_SESSION.value:
            requested_ex = payload.get("exercise", "squat")
            workout_id = payload.get("workout_id")
            session_id = tracker.start_session(exercise_name=requested_ex, workout_id=workout_id)
            started_resp = SessionStartedResponse(
                session_id=session_id,
                exercise=tracker.exercise_name,
                workout_id=workout_id,
                started_at=tracker.started_at.isoformat(),
            )
            await websocket.send_text(started_resp.model_dump_json())
            return

        # Stop Session
        if msg_type == WSClientMessageType.STOP_SESSION.value:
            save_to_db = payload.get("save_to_db", True)
            summary = await tracker.stop_session(db=db, save_to_db=save_to_db)
            stopped_resp = SessionStoppedResponse(
                session_id=tracker.session_id,
                summary=summary,
            )
            await websocket.send_text(stopped_resp.model_dump_json())
            return

        # Set Exercise
        if msg_type == WSClientMessageType.SET_EXERCISE.value or (
            "exercise" in payload and "landmarks" not in payload and msg_type is None
        ):
            requested_ex = payload.get("exercise") or payload.get("exercise_override")
            if requested_ex:
                tracker.set_exercise(requested_ex)
            await websocket.send_text(
                json.dumps({
                    "status": "exercise_updated",
                    "current_exercise": tracker.exercise_name,
                })
            )
            return

        # Reset
        if msg_type == WSClientMessageType.RESET.value or msg_type == "reset":
            tracker.reset()
            await websocket.send_text(json.dumps({"status": "reset_completed"}))
            return

        # Pose Frame / Real-time Telemetry (default if type is pose_frame or landmarks are provided)
        if msg_type == WSClientMessageType.POSE_FRAME.value or "landmarks" in payload or msg_type is None:
            # Exercise override if specified
            override_ex = payload.get("exercise_override") or payload.get("exercise")
            if override_ex and normalize_exercise_name(override_ex) != tracker.exercise_name:
                tracker.set_exercise(override_ex)

            # Extract timestamp
            pose_payload = PoseFramePayload(**payload) if "landmarks" in payload else None
            timestamp_ms = pose_payload.get_timestamp_ms() if pose_payload else float(payload.get("timestamp_ms", time.time() * 1000.0))

            raw_landmarks = payload.get("landmarks")
            landmarks_np = parse_landmarks_to_numpy(raw_landmarks)

            # Process frame through in-memory analyzer
            analysis_result = tracker.process_frame(landmarks_np, timestamp_ms=timestamp_ms)
            await websocket.send_text(analysis_result.model_dump_json())
            return

        # Unknown message type
        err = ErrorResponse(
            code="UNKNOWN_MESSAGE_TYPE",
            message=f"Unknown message type '{msg_type}'. Supported types: pose_frame, start_session, stop_session, ping, set_exercise, reset.",
        )
        await websocket.send_text(err.model_dump_json())


# Global singleton manager and service
connection_manager = WebSocketConnectionManager()
websocket_service = WebSocketService(connection_manager)
