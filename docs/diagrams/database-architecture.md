# Database Architecture & Entity Relationships

This document outlines the relational data schema managed via SQLAlchemy (async) and Alembic migrations within the PostgreSQL database.

```mermaid
erDiagram
    users ||--o| user_profiles : "has profile (1:1)"
    users ||--o{ workouts : "owns (1:N)"
    workouts ||--o{ exercise_sessions : "contains (1:N)"
    workouts ||--o| coaching_feedbacks : "has feedback (1:1)"
    exercise_sessions ||--o{ exercise_results : "records reps (1:N)"
    exercise_results ||--o{ form_issues : "details faults (1:N)"

    users {
        string id PK
        string email UK "Indexed"
        string password_hash
        string full_name
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    user_profiles {
        string id PK
        string user_id FK "UK, Indexed, CASCADE"
        enum fitness_goal "strength, muscle_gain, fat_loss, general_fitness, endurance"
        enum experience_level "beginner, intermediate, advanced"
        enum preferred_focus "form, strength, consistency, endurance, balanced"
        enum coaching_style "concise, supportive, detailed, technical"
        datetime created_at
        datetime updated_at
    }

    workouts {
        string id PK
        string user_id FK "Indexed, CASCADE"
        enum status "in_progress, completed, cancelled"
        datetime started_at "Composite Indexed (user_id, started_at)"
        datetime ended_at
        float total_duration_sec
        float total_calories
        float overall_form_score
        text notes
        datetime created_at
        datetime updated_at
    }

    exercise_sessions {
        string id PK
        string workout_id FK "Composite Indexed (workout_id, session_order)"
        string exercise_name "Indexed"
        integer session_order
        enum status "in_progress, completed, cancelled"
        integer target_reps
        integer completed_reps
        integer valid_reps
        integer invalid_reps
        float average_form_score
        float average_tempo_sec
        datetime created_at
        datetime updated_at
    }

    exercise_results {
        string id PK
        string exercise_session_id FK "Composite Indexed (exercise_session_id, rep_number)"
        integer rep_number
        integer is_valid "1 = valid, 0 = invalid"
        float form_score
        float duration_sec
        float eccentric_duration_sec
        float concentric_duration_sec
        float min_joint_angle
        float max_joint_angle
        json faults_detected
        datetime created_at
        datetime updated_at
    }

    form_issues {
        string id PK
        string exercise_result_id FK "Composite Indexed (exercise_result_id, issue_code)"
        string issue_code "Indexed"
        enum severity "minor, moderate, severe"
        text feedback_text
        float timestamp_ms
        datetime created_at
        datetime updated_at
    }

    coaching_feedbacks {
        string id PK
        string workout_id FK "UK, CASCADE"
        string llm_model
        text summary
        json strengths
        json areas_to_improve
        text recovery_advice
        datetime created_at
        datetime updated_at
    }
```

## Schema Highlights

1. **User Ownership & Cascade Deletion**:
   - `users` owns `user_profiles` and `workouts` via Foreign Keys with `ON DELETE CASCADE`.
   - Deleting a user purges all associated profiles, workouts, exercise sessions, rep results, form issues, and coaching feedbacks.
   - Deleting a workout purges all sets, reps, issues, and AI coach summaries.

2. **Index Optimization**:
   - `ix_workouts_user_started` index on `(user_id, started_at)` optimizes workout history and trend queries.
   - `ix_exercise_sessions_workout_order` on `(workout_id, session_order)` orders sets efficiently.
   - `ix_exercise_results_session_rep` on `(exercise_session_id, rep_number)` orders repetitions.
   - `ix_form_issues_result_code` on `(exercise_result_id, issue_code)` indexes fine-grained faults for fast aggregation.

3. **Data Integrity & Types**:
   - UUIDv4 strings for all primary keys (`id`).
   - SQLite / PostgreSQL dual-dialect support: alembic migrations (`001_initial_schema.py` through `004_security_hardening.py`) maintain schema integrity across testing and production.
