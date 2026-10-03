"""Add performance composite indexes for workouts, sessions, results, and issues

Revision ID: 004_add_performance_indexes
Revises: 003_add_user_profile_table
Create Date: 2026-09-18 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_performance_indexes"
down_revision: Union[str, None] = "003_add_user_profile_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite index on workouts (user_id, started_at) for user workout timeline & history queries
    op.create_index(
        "ix_workouts_user_started",
        "workouts",
        ["user_id", "started_at"],
        unique=False,
    )

    # 2. Composite index on exercise_sessions (workout_id, session_order) for ordered session loading
    op.create_index(
        "ix_exercise_sessions_workout_order",
        "exercise_sessions",
        ["workout_id", "session_order"],
        unique=False,
    )

    # 3. Composite index on exercise_results (exercise_session_id, rep_number) for rep telemetry ordering
    op.create_index(
        "ix_exercise_results_session_rep",
        "exercise_results",
        ["exercise_session_id", "rep_number"],
        unique=False,
    )

    # 4. Composite index on form_issues (exercise_result_id, issue_code) for recurring fault lookups
    op.create_index(
        "ix_form_issues_result_code",
        "form_issues",
        ["exercise_result_id", "issue_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_form_issues_result_code", table_name="form_issues")
    op.drop_index("ix_exercise_results_session_rep", table_name="exercise_results")
    op.drop_index("ix_exercise_sessions_workout_order", table_name="exercise_sessions")
    op.drop_index("ix_workouts_user_started", table_name="workouts")
