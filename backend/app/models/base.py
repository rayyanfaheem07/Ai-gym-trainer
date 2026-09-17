import uuid
from datetime import UTC, datetime

from backend.app.core.database import Base
from sqlalchemy import Column, DateTime, String

__all__ = ["Base", "TimestampMixin"]



def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )
