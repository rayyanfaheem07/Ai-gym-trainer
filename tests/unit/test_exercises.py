import numpy as np

from ai.exercises.base import BaseExerciseAnalyzer, ExerciseAnalysisResult
from ai.exercises.pushup import PushupExercise
from ai.exercises.registry import ExerciseRegistry
from ai.rep_counter.fsm import RepStage, RepStateCounter


def test_exercise_registry_all_exercises():
    exercises = ["squat", "pushup", "bicep_curl", "lunge", "shoulder_press"]
    for ex_name in exercises:
        ex = ExerciseRegistry.get_exercise(ex_name)
        assert ex is not None, f"Failed to instantiate {ex_name}"
        assert ex.name == ex_name
        assert isinstance(ex, BaseExerciseAnalyzer)

    # Test unknown
    unknown = ExerciseRegistry.get_exercise("non_existent")
    assert unknown is None


def test_exercise_registry_list_and_register():
    available = ExerciseRegistry.list_available()
    assert "squat" in available
    assert "pushup" in available
    assert "bicep_curl" in available
    assert "lunge" in available
    assert "shoulder_press" in available

    # Test dynamic registration
    class CustomDeadlift(BaseExerciseAnalyzer):
        def __init__(self):
            super().__init__(name="deadlift")

        def analyze_frame(self, landmarks, timestamp_ms=None):
            return ExerciseAnalysisResult(
                exercise="deadlift",
                phase="standing",
                form_score=100,
            )

    ExerciseRegistry.register("deadlift", CustomDeadlift)
    assert "deadlift" in ExerciseRegistry.list_available()
    dl = ExerciseRegistry.get_exercise("deadlift")
    assert isinstance(dl, CustomDeadlift)
    assert dl.name == "deadlift"


def test_base_exercise_legacy_adapter():
    pushup = PushupExercise()
    landmarks = np.zeros((33, 4), dtype=np.float32)
    landmarks[:, 3] = 0.95
    # Set default positions
    landmarks[11] = [0.4, 0.4, 0.0, 0.95]  # L Shoulder
    landmarks[13] = [0.4, 0.6, 0.0, 0.95]  # L Elbow
    landmarks[15] = [0.4, 0.8, 0.0, 0.95]  # L Wrist
    landmarks[12] = [0.6, 0.4, 0.0, 0.95]  # R Shoulder
    landmarks[14] = [0.6, 0.6, 0.0, 0.95]  # R Elbow
    landmarks[16] = [0.6, 0.8, 0.0, 0.95]  # R Wrist
    landmarks[23] = [0.45, 0.6, 0.0, 0.95] # L Hip
    landmarks[27] = [0.45, 0.9, 0.0, 0.95] # L Ankle

    state = pushup.evaluate_frame(landmarks, timestamp_ms=100.0)
    assert state is not None
    assert state.stage in ["plank", "START"]
    assert 0 <= state.current_form_score <= 100


def test_rep_state_counter_fsm():
    fsm = RepStateCounter(start_threshold=160.0, inflection_threshold=90.0)
    assert fsm.stage == RepStage.START

    # Descend
    stage, completed = fsm.update(120.0)
    assert stage == RepStage.ECCENTRIC
    assert not completed

    # Reach inflection (depth)
    stage, completed = fsm.update(85.0)
    assert stage == RepStage.INFLECTION
    assert not completed

    # Ascend
    stage, completed = fsm.update(110.0)
    assert stage == RepStage.CONCENTRIC
    assert not completed

    # Return to lockout
    stage, completed = fsm.update(165.0)
    assert stage == RepStage.START
    assert completed
    assert fsm.rep_count == 1
