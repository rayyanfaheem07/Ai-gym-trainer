from pathlib import Path

import pytest

from ai.classifier.inference import CANONICAL_EXERCISES, ExerciseInferenceEngine, StreamingExerciseClassifier
from ai.classifier.model import ExerciseClassifier
from ai.classifier.pipeline import ExerciseClassificationPipeline
from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.classifier.trainer import ExerciseModelTrainer


@pytest.fixture
def trained_pipeline(tmp_path: Path):
    session_files = BiomechanicalDataGenerator.generate_synthetic_dataset(
        output_dir=tmp_path / "raw",
        num_sessions_per_class=3,
        sequences_per_session=2,
    )
    preprocessor = DataPreprocessor()
    sessions = preprocessor.load_raw_sessions(session_files)
    dataset = preprocessor.process_sessions(sessions)
    processed = preprocessor.fit_transform_dataset(dataset)

    from ai.classifier.dataset import GroupAwareDatasetSplitter
    splitter = GroupAwareDatasetSplitter(test_size=0.2, val_size=0.2, random_state=42)
    splits = splitter.split(processed)

    trainer = ExerciseModelTrainer(model_type="random_forest", n_estimators=30, random_state=42)
    train_res = trainer.train(splits)

    pipeline = ExerciseClassificationPipeline(
        model=train_res.model,
        preprocessor=preprocessor,
    )
    return pipeline


def test_inference_engine_output_contract(trained_pipeline):
    engine = ExerciseInferenceEngine(pipeline=trained_pipeline, confidence_threshold=0.50)

    traj = BiomechanicalDataGenerator.generate_exercise_trajectory("squat", num_frames=30)
    result = engine.predict_sequence(traj)

    # 1. Structure Verification
    assert "exercise" in result
    assert "confidence" in result
    assert "probabilities" in result

    assert isinstance(result["exercise"], str)
    assert isinstance(result["confidence"], float)
    assert isinstance(result["probabilities"], dict)

    # 2. Canonical vocabulary keys
    for canon in CANONICAL_EXERCISES:
        assert canon in result["probabilities"]
        assert 0.0 <= result["probabilities"][canon] <= 1.0

    # 3. Sum of probabilities should be ~1.0
    total_p = sum(result["probabilities"].values())
    assert pytest.approx(total_p, abs=1e-2) == 1.0


def test_inference_low_confidence_fallback(trained_pipeline):
    # Set high confidence threshold that won't be met
    engine = ExerciseInferenceEngine(pipeline=trained_pipeline, confidence_threshold=0.9999, unknown_label="other")

    traj = BiomechanicalDataGenerator.generate_exercise_trajectory("squat", num_frames=30)
    result = engine.predict_sequence(traj)

    # Should fall back to "other" because confidence < 0.9999
    assert result["exercise"] == "other"
    assert result["confidence"] < 0.9999


def test_inference_empty_or_none_input(trained_pipeline):
    engine = ExerciseInferenceEngine(pipeline=trained_pipeline)

    res_empty = engine.predict_sequence([])
    assert res_empty["exercise"] == "other"
    assert res_empty["confidence"] == 0.0

    res_none = engine.predict_sequence(None)
    assert res_none["exercise"] == "other"
    assert res_none["confidence"] == 0.0


def test_streaming_classifier_rolling_buffer(trained_pipeline):
    engine = ExerciseInferenceEngine(pipeline=trained_pipeline, confidence_threshold=0.50)
    streaming = StreamingExerciseClassifier(
        inference_engine=engine,
        window_size=30,
        prediction_interval=2,
        smoothing_window=3,
    )

    traj = BiomechanicalDataGenerator.generate_exercise_trajectory("push_up", num_frames=40)

    # First 29 frames: buffer filling
    for f in range(29):
        res = streaming.process_frame(traj[f])
        assert res["exercise"] == "other"
        assert res["buffer_fill_pct"] < 1.0

    # Frame 30: buffer full, should run inference
    res_full = streaming.process_frame(traj[29])
    assert res_full["buffer_fill_pct"] == 1.0
    assert "probabilities" in res_full
    assert res_full["confidence"] >= 0.0

    # Test reset
    streaming.reset()
    assert len(streaming.buffer) == 0
    assert streaming.last_result is None


def test_high_level_exercise_classifier_wrapper(trained_pipeline, tmp_path: Path):
    model_path = tmp_path / "model.joblib"
    trained_pipeline.save(model_path)

    # 1. With trained pipeline
    clf = ExerciseClassifier(model_path=model_path)
    traj = BiomechanicalDataGenerator.generate_exercise_trajectory("bicep_curl", num_frames=30)

    pred_str = clf.predict(traj)
    assert isinstance(pred_str, str)

    detailed = clf.predict_detailed(traj)
    assert detailed["exercise"] == pred_str
    assert "probabilities" in detailed

    # 2. Without model (heuristic mode fallback)
    clf_heuristic = ExerciseClassifier(model_path=tmp_path / "non_existent.joblib")
    assert clf_heuristic.inference_engine is None
    h_result = clf_heuristic.predict_detailed(traj)
    assert "exercise" in h_result
    assert "probabilities" in h_result
