import json
from pathlib import Path

import pytest

from ai.classifier.dataset import GroupAwareDatasetSplitter
from ai.classifier.evaluator import ModelEvaluator
from ai.classifier.pipeline import ExerciseClassificationPipeline, PipelineMetadata
from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.classifier.trainer import ExerciseModelTrainer


@pytest.fixture
def sample_splits(tmp_path: Path):
    session_files = BiomechanicalDataGenerator.generate_synthetic_dataset(
        output_dir=tmp_path / "raw",
        num_sessions_per_class=3,
        sequences_per_session=2,
    )
    preprocessor = DataPreprocessor()
    sessions = preprocessor.load_raw_sessions(session_files)
    dataset = preprocessor.process_sessions(sessions)
    processed = preprocessor.fit_transform_dataset(dataset)

    splitter = GroupAwareDatasetSplitter(test_size=0.25, val_size=0.25, random_state=42)
    return splitter.split(processed), preprocessor


@pytest.mark.parametrize("model_type", ["random_forest", "gradient_boosting", "logistic_regression", "svm"])
def test_baseline_models_training(sample_splits, model_type):
    splits, _ = sample_splits
    trainer = ExerciseModelTrainer(model_type=model_type, n_estimators=20, max_depth=6, random_state=42)
    result = trainer.train(splits)

    assert result.model is not None
    assert result.train_score > 0.0
    assert result.model_type == model_type


def test_model_evaluation_metrics_and_report(sample_splits, tmp_path: Path):
    splits, preprocessor = sample_splits
    trainer = ExerciseModelTrainer(model_type="random_forest", n_estimators=30, random_state=42)
    result = trainer.train(splits)

    metrics = ModelEvaluator.evaluate(result.model, splits)
    assert 0.0 <= metrics.accuracy <= 1.0
    assert 0.0 <= metrics.f1_macro <= 1.0
    assert len(metrics.confusion_matrix) == len(splits.classes)
    assert metrics.num_test_samples == len(splits.y_test)

    # Report saving
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    ModelEvaluator.save_report(metrics, json_path, md_path)

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "accuracy" in data
        assert "per_class_metrics" in data


def test_pipeline_serialization_and_loading(sample_splits, tmp_path: Path):
    splits, preprocessor = sample_splits
    trainer = ExerciseModelTrainer(model_type="random_forest", n_estimators=20, random_state=42)
    train_res = trainer.train(splits)

    meta = PipelineMetadata(
        created_at_utc="2026-09-09T00:00:00Z",
        model_type="random_forest",
        version="1.0.0",
        classes=splits.classes,
        window_size=30,
        num_features=splits.X_train.shape[1],
        train_samples=len(splits.X_train),
        train_accuracy=train_res.train_score,
        val_accuracy=train_res.val_score,
    )

    pipeline = ExerciseClassificationPipeline(
        model=train_res.model,
        preprocessor=preprocessor,
        metadata=meta,
    )

    model_file = tmp_path / "classifier_pipeline.joblib"
    pipeline.save(model_file)
    assert model_file.exists()

    loaded = ExerciseClassificationPipeline.load(model_file)
    assert loaded.classes == splits.classes
    assert loaded.metadata.model_type == "random_forest"
