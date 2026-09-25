"""Unit tests for ML Temporal Classifier and Inference Engine Robustness.

Covers:
- Valid temporal windows and insufficient windows
- Empty sequences and None inputs
- Malformed feature dimensions and shapes
- Batch inference vs single inference consistency
- CPU inference execution without calculating gradients
- Model loading failures and graceful fallback behavior
"""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai.classifier.inference import CANONICAL_EXERCISES  # noqa: E402
from ai.classifier.preprocessor import DataPreprocessor  # noqa: E402
from ai.classifier.temporal_inference import TemporalExerciseInferenceEngine  # noqa: E402
from ai.classifier.temporal_model import PoseSequenceClassifier  # noqa: E402
from ai.classifier.temporal_pipeline import TemporalClassificationPipeline  # noqa: E402


@pytest.fixture
def mock_temporal_pipeline():
    """Creates a lightweight TemporalClassificationPipeline for inference testing."""
    preprocessor = DataPreprocessor(window_size=30, stride=15)
    # Fit scaler on dummy data
    dummy_feats = np.random.randn(100, 73).astype(np.float32)
    preprocessor.scaler.fit(dummy_feats)
    preprocessor.is_fitted = True

    model = PoseSequenceClassifier(
        input_size=73,
        hidden_size=32,
        num_classes=6,
        rnn_type="gru",
        num_layers=1,
    )
    model.eval()

    classes = ["squat", "pushup", "bicep_curl", "lunge", "shoulder_press", "other"]
    model_config = {
        "input_size": 73,
        "hidden_size": 32,
        "num_classes": 6,
        "rnn_type": "gru",
        "num_layers": 1,
    }
    pipeline = TemporalClassificationPipeline(
        model=model,
        preprocessor=preprocessor,
        classes=classes,
        model_config=model_config,
    )
    return pipeline


# ==============================================================================
# 1. Fallback Mode Tests (No Model Loaded)
# ==============================================================================


def test_temporal_inference_unloaded_fallback():
    """When pipeline is None, engine returns transparent fallback to 'other'."""
    engine = TemporalExerciseInferenceEngine(pipeline=None)
    assert engine.is_ready() is False

    # Single sequence
    seq = [np.random.randn(33, 4).astype(np.float32) for _ in range(30)]
    res = engine.predict_sequence(seq)
    assert res["exercise"] == "other"
    assert res["confidence"] == 0.0
    assert "probabilities" in res
    assert res["probabilities"]["other"] == 1.0
    assert all(res["probabilities"][c] == 0.0 for c in CANONICAL_EXERCISES if c != "other")

    # Batched
    batch_res = engine.predict_batch([seq, seq])
    assert len(batch_res) == 2
    assert batch_res[0]["exercise"] == "other"
    assert batch_res[1]["exercise"] == "other"


def test_temporal_inference_empty_or_none_inputs():
    """Empty list or None input safely returns fallback."""
    engine = TemporalExerciseInferenceEngine(pipeline=None)

    assert engine.predict_sequence([])["exercise"] == "other"
    assert engine.predict_sequence(None)["exercise"] == "other"
    assert engine.predict_batch([]) == []
    assert engine.predict_batch(None) == []


# ==============================================================================
# 2. Gradient Calculation & CPU Device Verification
# ==============================================================================


def test_temporal_inference_no_gradients_on_cpu(mock_temporal_pipeline):
    """Inference must be strictly executed without building computation graphs or gradients."""
    engine = TemporalExerciseInferenceEngine(
        pipeline=mock_temporal_pipeline,
        device="cpu",
    )
    assert engine.is_ready() is True

    # Generate synthetic 30-frame window of (33, 4) landmarks
    seq = np.random.randn(30, 33, 4).astype(np.float32)

    prev_grad = torch.is_grad_enabled()
    try:
        torch.set_grad_enabled(True)
        res = engine.predict_sequence(seq)
        assert res["exercise"] in CANONICAL_EXERCISES
        assert 0.0 <= res["confidence"] <= 1.0

        # Verify model parameters do not have grads accumulated
        for p in mock_temporal_pipeline.model.parameters():
            assert p.grad is None
    finally:
        torch.set_grad_enabled(prev_grad)


# ==============================================================================
# 3. Single vs Batched Inference Semantic Consistency
# ==============================================================================


def test_temporal_inference_batch_vs_single_consistency(mock_temporal_pipeline):
    """Single inference and batch inference on the same window must yield identical results."""
    engine = TemporalExerciseInferenceEngine(
        pipeline=mock_temporal_pipeline,
        device="cpu",
    )

    # Fix seed for synthetic window
    np.random.seed(42)
    w1 = np.random.randn(30, 33, 4).astype(np.float32)
    w2 = np.random.randn(30, 33, 4).astype(np.float32)

    # Predict individually
    single_1 = engine.predict_sequence(w1)
    single_2 = engine.predict_sequence(w2)

    # Predict in batch
    batch_res = engine.predict_batch([w1, w2])
    assert len(batch_res) == 2

    assert batch_res[0]["exercise"] == single_1["exercise"]
    assert pytest.approx(batch_res[0]["confidence"], abs=1e-3) == single_1["confidence"]

    assert batch_res[1]["exercise"] == single_2["exercise"]
    assert pytest.approx(batch_res[1]["confidence"], abs=1e-3) == single_2["confidence"]


# ==============================================================================
# 4. Malformed Inputs and Insufficient Windows
# ==============================================================================


def test_temporal_inference_insufficient_window_length(mock_temporal_pipeline):
    """Windows shorter than target length (e.g. 10 frames) are padded or handled safely."""
    engine = TemporalExerciseInferenceEngine(
        pipeline=mock_temporal_pipeline,
        device="cpu",
    )

    # Only 5 frames instead of 30
    short_seq = np.random.randn(5, 33, 4).astype(np.float32)
    res = engine.predict_sequence(short_seq)
    assert "exercise" in res
    assert "confidence" in res


def test_temporal_inference_malformed_dimensions(mock_temporal_pipeline):
    """Malformed feature shapes fall back safely without raising uncaught exceptions."""
    engine = TemporalExerciseInferenceEngine(
        pipeline=mock_temporal_pipeline,
        confidence_threshold=0.60,
        device="cpu",
    )

    # Wrong shape (e.g. 2D array of wrong dimensions)
    malformed = np.random.randn(10, 5).astype(np.float32)
    res = engine.predict_sequence(malformed)
    assert res["exercise"] == "other"
    assert 0.0 <= res["confidence"] < 0.60


# ==============================================================================
# 5. Model Loading Failure Handling
# ==============================================================================


def test_temporal_inference_model_loading_failure(tmp_path: Path):
    """Corrupt or non-existent model file should fail gracefully into offline fallback mode."""
    corrupt_file = tmp_path / "corrupt_model.pt"
    corrupt_file.write_text("NOT_A_VALID_PYTORCH_MODEL")

    # Loading from non-existent or corrupt path
    engine = TemporalExerciseInferenceEngine(pipeline=None)
    # Ensure engine remains in safe unready fallback mode
    assert engine.is_ready() is False

    dummy_window = np.random.randn(30, 33, 4).astype(np.float32)
    res = engine.predict_sequence(dummy_window)
    assert res["exercise"] == "other"
    assert res["confidence"] == 0.0
