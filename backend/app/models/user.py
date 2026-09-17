from typing import Any

from backend.app.core.database import Base
from backend.app.models.base import TimestampMixin
from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship


class User(Base, TimestampMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False, default="")
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    workouts = relationship(
        "Workout",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Workout.created_at)",
    )

    # Backward compatibility property
    @property
    def sessions(self) -> list[Any]:
        return self.workouts
