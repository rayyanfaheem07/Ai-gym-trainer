import enum
from typing import Any

from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin, get_utc_now
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship


class WorkoutStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Backward compatibility alias
SessionStatus = WorkoutStatus


class ExerciseType(str, enum.Enum):
    SQUAT = "squat"
    PUSHUP = "pushup"
    BICEP_CURL = "bicep_curl"
    SHOULDER_PRESS = "shoulder_press"
    LUNGE = "lunge"
    PLANK = "plank"
    OTHER = "other"


class IssueSeverity(str, enum.Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class Workout(Base, TimestampMixin):
    """
    Primary workout model representing an entire user workout session.
    """
    __tablename__ = "workouts"
    __table_args__ = (
        Index("ix_workouts_user_started", "user_id", "started_at"),
    )

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status = Column(
        SQLEnum(WorkoutStatus),
        default=WorkoutStatus.IN_PROGRESS,
        nullable=False,
        index=True,
    )
    started_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    ended_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_duration_sec = Column(Float, default=0.0, nullable=False)
    total_calories = Column(Float, default=0.0, nullable=False)
    overall_form_score = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="workouts")
    exercise_sessions = relationship(
        "ExerciseSession",
        back_populates="workout",
        cascade="all, delete-orphan",
        order_by="ExerciseSession.session_order",
    )
    feedback = relationship(
        "CoachingFeedback",
        back_populates="workout",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Compatibility property
    @property
    def sets(self) -> list[Any]:
        return self.exercise_sessions


class ExerciseSession(Base, TimestampMixin):
    """
    Represents a specific exercise performance (or set) within a workout.
    """
    __tablename__ = "exercise_sessions"
    __table_args__ = (
        Index("ix_exercise_sessions_workout_order", "workout_id", "session_order"),
    )

    workout_id = Column(
        String(36),
        ForeignKey("workouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_name = Column(String(50), nullable=False, index=True)
    session_order = Column(Integer, default=1, nullable=False)
    status = Column(
        SQLEnum(WorkoutStatus),
        default=WorkoutStatus.IN_PROGRESS,
        nullable=False,
    )
    target_reps = Column(Integer, nullable=True)
    completed_reps = Column(Integer, default=0, nullable=False)
    valid_reps = Column(Integer, default=0, nullable=False)
    invalid_reps = Column(Integer, default=0, nullable=False)
    average_form_score = Column(Float, default=0.0, nullable=False)
    average_tempo_sec = Column(Float, default=0.0, nullable=False)

    # Relationships
    workout = relationship("Workout", back_populates="exercise_sessions")
    results = relationship(
        "ExerciseResult",
        back_populates="exercise_session",
        cascade="all, delete-orphan",
        order_by="ExerciseResult.rep_number",
    )

    # Compatibility properties
    @property
    def reps(self) -> list[Any]:
        return self.results

    @property
    def set_number(self) -> int:
        return self.session_order

    @property
    def exercise_type(self) -> str:
        return self.exercise_name


class ExerciseResult(Base, TimestampMixin):
    """
    Represents an individual rep execution result with biomechanical data.
    """
    __tablename__ = "exercise_results"
    __table_args__ = (
        Index("ix_exercise_results_session_rep", "exercise_session_id", "rep_number"),
    )

    exercise_session_id = Column(
        String(36),
        ForeignKey("exercise_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rep_number = Column(Integer, nullable=False)
    is_valid = Column(Integer, default=1, nullable=False)  # 1 = valid, 0 = invalid
    form_score = Column(Float, default=100.0, nullable=False)
    duration_sec = Column(Float, default=0.0, nullable=False)
    eccentric_duration_sec = Column(Float, default=0.0, nullable=False)
    concentric_duration_sec = Column(Float, default=0.0, nullable=False)
    min_joint_angle = Column(Float, nullable=True)
    max_joint_angle = Column(Float, nullable=True)
    faults_detected = Column(JSON, default=list, nullable=False)

    # Relationships
    exercise_session = relationship("ExerciseSession", back_populates="results")
    form_issues = relationship(
        "FormIssue",
        back_populates="exercise_result",
        cascade="all, delete-orphan",
    )


class FormIssue(Base, TimestampMixin):
    """
    Fine-grained form error or biomechanical deviation detected during a rep.
    """
    __tablename__ = "form_issues"
    __table_args__ = (
        Index("ix_form_issues_result_code", "exercise_result_id", "issue_code"),
    )

    exercise_result_id = Column(
        String(36),
        ForeignKey("exercise_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_code = Column(String(100), nullable=False, index=True)
    severity = Column(
        SQLEnum(IssueSeverity),
        default=IssueSeverity.MODERATE,
        nullable=False,
    )
    feedback_text = Column(Text, nullable=False)
    timestamp_ms = Column(Float, default=0.0, nullable=False)

    # Relationships
    exercise_result = relationship("ExerciseResult", back_populates="form_issues")


class CoachingFeedback(Base, TimestampMixin):
    """
    LLM post-workout coaching evaluation and recovery advice.
    """
    __tablename__ = "coaching_feedbacks"

    workout_id = Column(
        String(36),
        ForeignKey("workouts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    llm_model = Column(String(100), default="llama3.2")
    summary = Column(Text, nullable=False)
    strengths = Column(JSON, default=list, nullable=False)
    areas_to_improve = Column(JSON, default=list, nullable=False)
    recovery_advice = Column(Text, nullable=True)

    # Relationships
    workout = relationship("Workout", back_populates="feedback")


# Backward compatibility aliases
WorkoutSession = Workout
ExerciseSet = ExerciseSession
RepRecord = ExerciseResult
