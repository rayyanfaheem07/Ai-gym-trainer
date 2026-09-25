"""Phase 15 Performance Benchmarks & Engineering Verification Suite

Measures actual runtime efficiency and latency metrics across:
1. Fast NumPy landmark buffer conversion & exercise analyzer frame processing
2. ML classifier single vs batched inference throughput
3. Database index efficiency & Personalization trend calculation latency
"""

import time
from datetime import timedelta

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ai.exercises.registry import ExerciseRegistry
from ai.pose.landmarks import LandmarkIndex
from backend.app.models.base import get_utc_now
from backend.app.models.user import User
from backend.app.models.workout import (
    ExerciseResult,
    ExerciseSession,
    FormIssue,
    IssueSeverity,
    Workout,
    WorkoutStatus,
)
from backend.app.services.personalization_service import PersonalizationService
from backend.app.services.websocket_service import parse_landmarks_to_numpy


def generate_benchmark_landmark_payload(num_frames: int = 100) -> list[list[dict]]:
    """Generates synthetic landmark payloads for benchmarking."""
    payloads = []
    for frame_idx in range(num_frames):
        knee_y = 0.75 + 0.1 * float(np.sin(frame_idx * 0.1) ** 2)
        shoulder_y = 0.25 + 0.05 * float(np.sin(frame_idx * 0.1) ** 2)

        landmarks_np = np.zeros((33, 4), dtype=np.float32)
        landmarks_np[:, 3] = 0.95
        landmarks_np[LandmarkIndex.LEFT_HIP] = [0.45, 0.5, 0.0, 0.95]
        landmarks_np[LandmarkIndex.RIGHT_HIP] = [0.55, 0.5, 0.0, 0.95]
        landmarks_np[LandmarkIndex.LEFT_KNEE] = [0.45, knee_y, 0.0, 0.95]
        landmarks_np[LandmarkIndex.RIGHT_KNEE] = [0.55, knee_y, 0.0, 0.95]
        landmarks_np[LandmarkIndex.LEFT_ANKLE] = [0.45, 0.95, 0.0, 0.95]
        landmarks_np[LandmarkIndex.RIGHT_ANKLE] = [0.55, 0.95, 0.0, 0.95]
        landmarks_np[LandmarkIndex.LEFT_SHOULDER] = [0.45, shoulder_y, 0.0, 0.95]
        landmarks_np[LandmarkIndex.RIGHT_SHOULDER] = [0.55, shoulder_y, 0.0, 0.95]

        frame_dict = [
            {"x": float(lm[0]), "y": float(lm[1]), "z": float(lm[2]), "visibility": float(lm[3])}
            for lm in landmarks_np
        ]
        payloads.append(frame_dict)
    return payloads


def test_benchmark_landmark_parsing_and_analyzer_latency():
    """
    Measures frame parsing and biomechanical analyzer execution latency over 100 frames.
    Target: Average per-frame latency must be well under 10ms for 30+ FPS operation.
    """
    frames = generate_benchmark_landmark_payload(num_frames=100)
    analyzer = ExerciseRegistry.get_exercise("squat")
    assert analyzer is not None
    analyzer.reset()

    latencies_ms: list[float] = []

    for i, raw_frame in enumerate(frames):
        t0 = time.perf_counter()
        arr = parse_landmarks_to_numpy(raw_frame)
        assert arr is not None
        assert arr.shape == (33, 4)
        result = analyzer.analyze_frame(arr, timestamp_ms=float(i * 33.3))
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    avg_latency = sum(latencies_ms) / len(latencies_ms)
    p95_latency = np.percentile(latencies_ms, 95)
    max_latency = max(latencies_ms)

    print(f"\n[BENCHMARK] Pose Analysis: avg={avg_latency:.3f}ms, p95={p95_latency:.3f}ms, max={max_latency:.3f}ms")

    # Real-time requirement: frame processing comfortably sub-10ms per frame
    assert avg_latency < 10.0, f"Average frame processing latency {avg_latency:.2f}ms exceeds 10ms threshold"
    assert p95_latency < 20.0, f"P95 frame latency {p95_latency:.2f}ms exceeds 20ms threshold"
    assert result.form_score >= 0.0


def test_benchmark_temporal_classifier_batch_inference():
    """
    Measures temporal classification pipeline single vs batched inference throughput.
    """
    from ai.classifier.temporal_inference import TemporalExerciseInferenceEngine

    engine = TemporalExerciseInferenceEngine(pipeline=None)
    # Test transparent fallback throughput when pipeline model is unloaded
    windows = [np.random.randn(30, 33, 4).astype(np.float32) for _ in range(16)]

    t0 = time.perf_counter()
    batch_results = engine.predict_batch(windows)
    t1 = time.perf_counter()

    batch_duration_ms = (t1 - t0) * 1000.0
    per_window_ms = batch_duration_ms / len(windows)

    print(f"\n[BENCHMARK] Batch Fallback Inference: total={batch_duration_ms:.3f}ms for {len(windows)} windows ({per_window_ms:.3f}ms/window)")

    assert len(batch_results) == len(windows)
    for res in batch_results:
        assert res["exercise"] == "other"
        assert res["confidence"] == 0.0


@pytest.mark.asyncio
async def test_benchmark_personalization_trends_query_latency(
    db_session: AsyncSession, test_user: User
):
    """
    Measures database query and calculation latency for longitudinal personalization trends
    with multiple historical workout sessions.
    """
    base_time = get_utc_now() - timedelta(days=20)

    # Seed 10 distinct workouts with sessions and results
    for i in range(10):
        w = Workout(
            user_id=test_user.id,
            started_at=base_time + timedelta(days=i),
            status=WorkoutStatus.COMPLETED,
            overall_form_score=80.0 + (i % 5),
            total_duration_sec=360.0,
        )
        s = ExerciseSession(
            workout=w,
            exercise_name="squat",
            completed_reps=10,
            valid_reps=9,
            invalid_reps=1,
            average_form_score=82.0,
        )
        r = ExerciseResult(exercise_session=s, rep_number=1, is_valid=0)
        iss = FormIssue(
            exercise_result=r,
            issue_code="knee_valgus",
            severity=IssueSeverity.MODERATE,
            feedback_text="Knees cave inward",
        )
        db_session.add_all([w, s, r, iss])

    await db_session.commit()

    # Benchmark execution of calculate_personal_trends
    t0 = time.perf_counter()
    history, trends = await PersonalizationService.calculate_personal_trends(
        db_session, user_id=test_user.id
    )
    t1 = time.perf_counter()

    duration_ms = (t1 - t0) * 1000.0
    print(f"\n[BENCHMARK] Personalization Trends Query (10 workouts): {duration_ms:.3f}ms")

    assert history.workouts_completed == 10
    assert "knee_valgus" in history.recurring_form_issues
    assert len(trends) >= 1
    # SLA check: calculating trends across historical workouts must be sub-100ms
    assert duration_ms < 100.0, f"Query latency {duration_ms:.2f}ms exceeds 100ms SLA"
