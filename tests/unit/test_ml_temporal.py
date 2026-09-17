import tempfile
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai.classifier.dataset import GroupAwareDatasetSplitter  # noqa: E402
from ai.classifier.inference import CANONICAL_EXERCISES  # noqa: E402
from ai.classifier.model import ExerciseClassifier  # noqa: E402
from ai.classifier.preprocessor import DataPreprocessor  # noqa: E402
from ai.classifier.synthetic import BiomechanicalDataGenerator  # noqa: E402
from ai.classifier.temporal_dataset import (  # noqa: E402
    PoseSequenceDataset,
    create_temporal_dataloaders,
)
from ai.classifier.temporal_evaluator import TemporalModelEvaluator  # noqa: E402
from ai.classifier.temporal_inference import (  # noqa: E402
    TemporalExerciseInferenceEngine,
)
from ai.classifier.temporal_model import (  # noqa: E402
    PoseSequenceClassifier,
    TemporalAttention,
)
from ai.classifier.temporal_pipeline import (  # noqa: E402
    TemporalClassificationPipeline,
)
from ai.classifier.temporal_trainer import TemporalModelTrainer  # noqa: E402


@pytest.fixture
def synthetic_sessions():
    return BiomechanicalDataGenerator.generate_synthetic_sessions(
        num_sessions_per_class=3,
        sequences_per_session=2,
        window_length=60,
    )


@pytest.fixture
def temporal_splits(synthetic_sessions):
    preprocessor = DataPreprocessor(window_size=30, stride=15)
    temporal_ds = preprocessor.process_sessions_temporal(synthetic_sessions)
    splitter = GroupAwareDatasetSplitter(test_size=0.2, val_size=0.2, random_state=42)
    splits = splitter.split(temporal_ds)
    preprocessor.fit_temporal(temporal_ds)

    feat_dim = temporal_ds.feature_dim
    splits.X_train = preprocessor.scaler.transform(
        splits.X_train.reshape(-1, feat_dim)
    ).reshape(splits.X_train.shape).astype(np.float32)

    if len(splits.X_val) > 0:
        splits.X_val = preprocessor.scaler.transform(
            splits.X_val.reshape(-1, feat_dim)
        ).reshape(splits.X_val.shape).astype(np.float32)

    splits.X_test = preprocessor.scaler.transform(
        splits.X_test.reshape(-1, feat_dim)
    ).reshape(splits.X_test.shape).astype(np.float32)

    return splits, preprocessor


# ============================================================================
# 1. PyTorch Dataset Tests
# ============================================================================

def test_pose_sequence_dataset_basic():
    N, T, F = 10, 30, 73
    dummy_x = np.random.randn(N, T, F).astype(np.float32)
    dummy_y = np.random.randint(0, 6, size=(N,)).astype(np.int64)

    ds = PoseSequenceDataset(dummy_x, dummy_y)
    assert len(ds) == N
    assert ds.sequence_length == T
    assert ds.feature_dim == F

    x_tensor, y_tensor = ds[0]
    assert isinstance(x_tensor, torch.Tensor)
    assert isinstance(y_tensor, torch.Tensor)
    assert x_tensor.shape == (T, F)
    assert y_tensor.shape == ()
    assert x_tensor.dtype == torch.float32
    assert y_tensor.dtype == torch.int64


def test_pose_sequence_dataset_padding_truncation():
    # Test truncation
    long_x = np.random.randn(5, 50, 73).astype(np.float32)
    ds_trunc = PoseSequenceDataset(long_x, sequence_length=30)
    assert ds_trunc.sequence_length == 30
    assert ds_trunc[0].shape == (30, 73)

    # Test padding
    short_x = np.random.randn(5, 15, 73).astype(np.float32)
    ds_pad = PoseSequenceDataset(short_x, sequence_length=30)
    assert ds_pad.sequence_length == 30
    assert ds_pad[0].shape == (30, 73)


def test_create_temporal_dataloaders(temporal_splits):
    splits, _ = temporal_splits
    train_loader, val_loader, test_loader = create_temporal_dataloaders(splits, batch_size=8)

    assert train_loader is not None
    assert test_loader is not None

    batch_x, batch_y = next(iter(train_loader))
    assert batch_x.dim() == 3
    assert batch_x.shape[0] <= 8
    assert batch_x.shape[1] == 30
    assert batch_x.shape[2] == 73
    assert batch_y.shape[0] == batch_x.shape[0]


# ============================================================================
# 2. PyTorch Model Architecture Tests
# ============================================================================

def test_pose_sequence_classifier_lstm_forward():
    model = PoseSequenceClassifier(
        input_size=73,
        hidden_size=32,
        num_layers=2,
        num_classes=6,
        rnn_type="lstm",
        bidirectional=True,
    )
    model.eval()

    batch_x = torch.randn(4, 30, 73)
    with torch.no_grad():
        logits = model(batch_x)
        probs = model.predict_proba(batch_x)

    assert logits.shape == (4, 6)
    assert probs.shape == (4, 6)
    assert torch.allclose(probs.sum(dim=-1), torch.ones(4), atol=1e-4)


def test_pose_sequence_classifier_gru_forward():
    model = PoseSequenceClassifier(
        input_size=73,
        hidden_size=32,
        num_layers=1,
        num_classes=6,
        rnn_type="gru",
        bidirectional=False,
    )
    model.eval()

    batch_x = torch.randn(2, 30, 73)
    with torch.no_grad():
        logits = model(batch_x)
    assert logits.shape == (2, 6)


def test_temporal_attention_layer():
    attn = TemporalAttention(hidden_dim=64)
    hidden = torch.randn(4, 30, 64)
    pooled = attn(hidden)
    assert pooled.shape == (4, 64)


def test_model_config_roundtrip():
    model = PoseSequenceClassifier(
        input_size=73,
        hidden_size=48,
        num_layers=2,
        num_classes=6,
        rnn_type="gru",
        bidirectional=True,
        dropout=0.3,
    )
    cfg = model.to_config()
    assert cfg["hidden_size"] == 48
    assert cfg["rnn_type"] == "gru"
    assert cfg["num_parameters"] > 0

    rebuilt = PoseSequenceClassifier.from_config(cfg)
    assert rebuilt.hidden_size == 48
    assert rebuilt.rnn_type == "gru"
    assert rebuilt.get_num_parameters() == model.get_num_parameters()


# ============================================================================
# 3. Preprocessor Temporal Methods Tests
# ============================================================================

def test_preprocessor_temporal_dataset_flow(synthetic_sessions):
    prep = DataPreprocessor(window_size=30, stride=15)
    ds = prep.process_sessions_temporal(synthetic_sessions)

    assert ds.X.ndim == 3
    assert ds.X.shape[1] == 30
    assert ds.X.shape[2] == 73
    assert len(ds.classes) == 6

    # Fit and transform
    prep.fit_temporal(ds)
    assert prep.is_fitted
    transformed = prep.transform_temporal_dataset(ds)
    assert transformed.X.shape == ds.X.shape

    # Single window transform
    sample_win = synthetic_sessions[0]["sequences"][0]["frames"][:30]
    win_arr = np.array([f["landmarks"] for f in sample_win if f["landmarks"] is not None])
    scaled_win = prep.transform_sequence_window(win_arr)
    assert scaled_win.shape == (1, 30, 73)


# ============================================================================
# 4. Training Engine & Early Stopping Tests
# ============================================================================

def test_temporal_trainer_execution(temporal_splits):
    splits, _ = temporal_splits
    trainer = TemporalModelTrainer(
        rnn_type="lstm",
        hidden_size=16,
        num_layers=1,
        dropout=0.1,
        epochs=3,
        patience=2,
        batch_size=8,
        seed=42,
        device="cpu",
    )

    result = trainer.train(splits)
    assert result.model is not None
    assert len(result.history.epochs) == 3
    assert len(result.history.train_loss) == 3
    assert len(result.history.val_loss) == 3
    assert result.best_val_loss > 0.0
    assert result.best_epoch >= 1


# ============================================================================
# 5. Pipeline Serialization & Roundtrip Tests
# ============================================================================

def test_temporal_pipeline_save_and_load(temporal_splits):
    splits, preprocessor = temporal_splits
    trainer = TemporalModelTrainer(
        rnn_type="gru",
        hidden_size=16,
        num_layers=1,
        epochs=2,
        batch_size=8,
        device="cpu",
    )
    result = trainer.train(splits)

    pipeline = TemporalClassificationPipeline(
        model=result.model,
        preprocessor=preprocessor,
        classes=splits.classes,
        model_config=result.model.to_config(),
        metadata={"test_run": True},
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        save_path = Path(tmp_dir) / "test_model.pt"
        pipeline.save(save_path)
        assert save_path.exists()

        loaded = TemporalClassificationPipeline.load(save_path, device="cpu")
        assert loaded.classes == splits.classes
        assert loaded.model.hidden_size == 16
        assert loaded.preprocessor.is_fitted

        # Verify predictions match
        sample_x = torch.randn(2, 30, 73)
        with torch.no_grad():
            orig_preds = result.model(sample_x).numpy()
            loaded_preds = loaded.model(sample_x).numpy()
        np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-4, atol=1e-4)


# ============================================================================
# 6. Inference Engine & Contract Tests
# ============================================================================

def test_temporal_inference_contract(temporal_splits):
    splits, preprocessor = temporal_splits
    trainer = TemporalModelTrainer(
        rnn_type="lstm",
        hidden_size=16,
        num_layers=1,
        epochs=2,
        batch_size=8,
        device="cpu",
    )
    result = trainer.train(splits)

    pipeline = TemporalClassificationPipeline(
        model=result.model,
        preprocessor=preprocessor,
        classes=splits.classes,
        model_config=result.model.to_config(),
    )

    engine = TemporalExerciseInferenceEngine(
        pipeline=pipeline,
        confidence_threshold=0.60,
        device="cpu",
    )
    assert engine.is_ready()

    sample_seq = np.random.randn(30, 73).astype(np.float32)
    res = engine.predict_sequence(sample_seq)

    assert "exercise" in res
    assert "confidence" in res
    assert "probabilities" in res
    assert isinstance(res["confidence"], float)
    assert all(k in res["probabilities"] for k in CANONICAL_EXERCISES)
    assert abs(sum(res["probabilities"].values()) - 1.0) < 0.01


def test_temporal_inference_low_confidence(temporal_splits):
    splits, preprocessor = temporal_splits
    model = PoseSequenceClassifier(input_size=73, hidden_size=16, num_classes=6)
    pipeline = TemporalClassificationPipeline(
        model=model,
        preprocessor=preprocessor,
        classes=splits.classes,
        model_config=model.to_config(),
    )

    # Set very high confidence threshold (0.999) -> must return "other"
    engine = TemporalExerciseInferenceEngine(
        pipeline=pipeline,
        confidence_threshold=0.999,
        unknown_label="other",
        device="cpu",
    )

    sample_seq = np.random.randn(30, 73).astype(np.float32)
    res = engine.predict_sequence(sample_seq)
    assert res["exercise"] == "other"


# ============================================================================
# 7. Evaluator Tests
# ============================================================================

def test_temporal_evaluator(temporal_splits):
    splits, preprocessor = temporal_splits
    trainer = TemporalModelTrainer(
        rnn_type="lstm",
        hidden_size=16,
        num_layers=1,
        epochs=2,
        batch_size=8,
        device="cpu",
    )
    result = trainer.train(splits)

    metrics = TemporalModelEvaluator.evaluate(result.model, splits, device="cpu")
    assert 0.0 <= metrics.accuracy <= 1.0
    assert 0.0 <= metrics.f1_macro <= 1.0
    assert len(metrics.confusion_matrix) == len(splits.classes)
    assert metrics.num_test_samples == len(splits.X_test)


# ============================================================================
# 8. High-Level ExerciseClassifier Backward Compatibility
# ============================================================================

def test_exercise_classifier_with_temporal_model(temporal_splits):
    splits, preprocessor = temporal_splits
    trainer = TemporalModelTrainer(
        rnn_type="lstm",
        hidden_size=16,
        num_layers=1,
        epochs=2,
        batch_size=8,
        device="cpu",
    )
    result = trainer.train(splits)

    with tempfile.TemporaryDirectory() as tmp_dir:
        model_path = Path(tmp_dir) / "temporal_classifier.pt"
        pipeline = TemporalClassificationPipeline(
            model=result.model,
            preprocessor=preprocessor,
            classes=splits.classes,
            model_config=result.model.to_config(),
        )
        pipeline.save(model_path)

        classifier = ExerciseClassifier(model_path=model_path)
        sample_seq = np.random.randn(30, 73).astype(np.float32)
        detailed = classifier.predict_detailed(sample_seq)

        assert "exercise" in detailed
        assert "confidence" in detailed
        assert "probabilities" in detailed
        assert all(k in detailed["probabilities"] for k in CANONICAL_EXERCISES)
