"""Initial schema creation for Phase 8

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-10 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. workouts table
    op.create_table(
        'workouts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.Enum('IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='workoutstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_duration_sec', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_calories', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('overall_form_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_workouts_id'), 'workouts', ['id'], unique=False)
    op.create_index(op.f('ix_workouts_user_id'), 'workouts', ['user_id'], unique=False)
    op.create_index(op.f('ix_workouts_status'), 'workouts', ['status'], unique=False)

    # 3. exercise_sessions table
    op.create_table(
        'exercise_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workout_id', sa.String(length=36), nullable=False),
        sa.Column('exercise_name', sa.String(length=50), nullable=False),
        sa.Column('session_order', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.Enum('IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='workoutstatus'), nullable=False),
        sa.Column('target_reps', sa.Integer(), nullable=True),
        sa.Column('completed_reps', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_reps', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('invalid_reps', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_form_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('average_tempo_sec', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workout_id'], ['workouts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_sessions_id'), 'exercise_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_exercise_sessions_workout_id'), 'exercise_sessions', ['workout_id'], unique=False)
    op.create_index(op.f('ix_exercise_sessions_exercise_name'), 'exercise_sessions', ['exercise_name'], unique=False)

    # 4. exercise_results table
    op.create_table(
        'exercise_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('exercise_session_id', sa.String(length=36), nullable=False),
        sa.Column('rep_number', sa.Integer(), nullable=False),
        sa.Column('is_valid', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('form_score', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('duration_sec', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('eccentric_duration_sec', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('concentric_duration_sec', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('min_joint_angle', sa.Float(), nullable=True),
        sa.Column('max_joint_angle', sa.Float(), nullable=True),
        sa.Column('faults_detected', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exercise_session_id'], ['exercise_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exercise_results_id'), 'exercise_results', ['id'], unique=False)
    op.create_index(op.f('ix_exercise_results_exercise_session_id'), 'exercise_results', ['exercise_session_id'], unique=False)

    # 5. form_issues table
    op.create_table(
        'form_issues',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('exercise_result_id', sa.String(length=36), nullable=False),
        sa.Column('issue_code', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.Enum('MINOR', 'MODERATE', 'SEVERE', name='issueseverity'), nullable=False),
        sa.Column('feedback_text', sa.Text(), nullable=False),
        sa.Column('timestamp_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['exercise_result_id'], ['exercise_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_form_issues_id'), 'form_issues', ['id'], unique=False)
    op.create_index(op.f('ix_form_issues_exercise_result_id'), 'form_issues', ['exercise_result_id'], unique=False)
    op.create_index(op.f('ix_form_issues_issue_code'), 'form_issues', ['issue_code'], unique=False)

    # 6. coaching_feedbacks table
    op.create_table(
        'coaching_feedbacks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workout_id', sa.String(length=36), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=False, server_default='llama3.2'),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('strengths', sa.JSON(), nullable=False),
        sa.Column('areas_to_improve', sa.JSON(), nullable=False),
        sa.Column('recovery_advice', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workout_id'], ['workouts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workout_id')
    )
    op.create_index(op.f('ix_coaching_feedbacks_id'), 'coaching_feedbacks', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('coaching_feedbacks')
    op.drop_table('form_issues')
    op.drop_table('exercise_results')
    op.drop_table('exercise_sessions')
    op.drop_table('workouts')
    op.drop_table('users')
