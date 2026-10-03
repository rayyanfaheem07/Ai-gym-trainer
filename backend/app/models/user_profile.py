import enum

from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship


class FitnessGoal(str, enum.Enum):
    STRENGTH = "strength"
    MUSCLE_GAIN = "muscle_gain"
    FAT_LOSS = "fat_loss"
    GENERAL_FITNESS = "general_fitness"
    ENDURANCE = "endurance"


class ExperienceLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class PreferredFocus(str, enum.Enum):
    FORM = "form"
    STRENGTH = "strength"
    CONSISTENCY = "consistency"
    ENDURANCE = "endurance"
    BALANCED = "balanced"


class CoachingStyle(str, enum.Enum):
    CONCISE = "concise"
    SUPPORTIVE = "supportive"
    DETAILED = "detailed"
    TECHNICAL = "technical"


class UserProfile(Base, TimestampMixin):
    """
    User fitness profile storing personalization preferences,
    experience level, fitness goals, and coaching style.
    """
    __tablename__ = "user_profiles"

    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    fitness_goal = Column(
        SQLEnum(FitnessGoal),
        default=FitnessGoal.GENERAL_FITNESS,
        nullable=False,
    )
    experience_level = Column(
        SQLEnum(ExperienceLevel),
        default=ExperienceLevel.BEGINNER,
        nullable=False,
    )
    preferred_focus = Column(
        SQLEnum(PreferredFocus),
        default=PreferredFocus.FORM,
        nullable=False,
    )
    coaching_style = Column(
        SQLEnum(CoachingStyle),
        default=CoachingStyle.SUPPORTIVE,
        nullable=False,
    )

    # Relationship to user
    user = relationship("User", back_populates="profile")
