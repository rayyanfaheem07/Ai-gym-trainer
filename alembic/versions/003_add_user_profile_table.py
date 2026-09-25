"""Add user_profiles table for Phase 14 Personalization

Revision ID: 003_add_user_profile_table
Revises: 002_add_user_password_hash
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_user_profile_table"
down_revision: Union[str, None] = "002_add_user_password_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "fitness_goal",
            sa.Enum(
                "STRENGTH",
                "MUSCLE_GAIN",
                "FAT_LOSS",
                "GENERAL_FITNESS",
                "ENDURANCE",
                name="fitnessgoal",
            ),
            nullable=False,
            server_default="GENERAL_FITNESS",
        ),
        sa.Column(
            "experience_level",
            sa.Enum(
                "BEGINNER",
                "INTERMEDIATE",
                "ADVANCED",
                name="experiencelevel",
            ),
            nullable=False,
            server_default="BEGINNER",
        ),
        sa.Column(
            "preferred_focus",
            sa.Enum(
                "FORM",
                "STRENGTH",
                "CONSISTENCY",
                "ENDURANCE",
                "BALANCED",
                name="preferredfocus",
            ),
            nullable=False,
            server_default="FORM",
        ),
        sa.Column(
            "coaching_style",
            sa.Enum(
                "CONCISE",
                "SUPPORTIVE",
                "DETAILED",
                "TECHNICAL",
                name="coachingstyle",
            ),
            nullable=False,
            server_default="SUPPORTIVE",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_user_profiles_id"), "user_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_user_profiles_user_id"), "user_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_profiles_user_id"), table_name="user_profiles")
    op.drop_index(op.f("ix_user_profiles_id"), table_name="user_profiles")
    op.drop_table("user_profiles")
