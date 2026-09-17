from pathlib import Path

from ai.classifier.dataset import GroupAwareDatasetSplitter
from ai.classifier.evaluator import ModelEvaluator
from ai.classifier.inference import ExerciseInferenceEngine
from ai.classifier.pipeline import ExerciseClassificationPipeline, PipelineMetadata
from ai.classifier.preprocessor import DataPreprocessor
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.classifier.trainer import ExerciseModelTrainer


def test_end_to_end_ml_pipeline_lifecycle(tmp_path: Path):
    """
    Validates complete lifecycle:
    1. Synthetic Session Generation
    2. Data Preprocessing & Feature Extraction
    3. Group-aware Splitting (Zero Leakage)
    4. Model Training (Random Forest)
    5. Test Split Evaluation & Metrics Computation
    6. Report Serialization (JSON & Markdown)
    7. Pipeline Artifact Packaging & Saving (.joblib)
    8. Pipeline Deserialization & Live Sequence Inference
    """
    raw_dir = tmp_path / "data" / "raw"
    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"

    # Step 1: Generate synthetic sessions across all 6 classes
    session_files = BiomechanicalDataGenerator.generate_synthetic_dataset(
        output_dir=raw_dir,
        num_sessions_per_class=4,
        sequences_per_session=3,
        window_length=30,
        fps=30.0,
    )
    assert len(session_files) == 24

    # Step 2: Preprocess raw sessions
    preprocessor = DataPreprocessor(window_size=30, stride=10, min_detected_ratio=0.7)
    sessions = preprocessor.load_raw_sessions(session_files)
    dataset = preprocessor.process_sessions(sessions)
    processed_dataset = preprocessor.fit_transform_dataset(dataset)

    assert processed_dataset.X.shape[0] > 50
    assert len(processed_dataset.classes) == 6

    # Step 3: Zero-Leakage Group Splitting
    splitter = GroupAwareDatasetSplitter(test_size=0.25, val_size=0.25, random_state=42)
    splits = splitter.split(processed_dataset)
    assert splits.verify_no_leakage() is True

    # Step 4: Model Training
    trainer = ExerciseModelTrainer(
        model_type="random_forest",
        n_estimators=50,
        max_depth=12,
        random_state=42,
    )
    train_res = trainer.train(splits)
    assert train_res.train_score > 0.80

    # Step 5 & 6: Evaluation & Report
    eval_metrics = ModelEvaluator.evaluate(train_res.model, splits)
    assert eval_metrics.accuracy >= 0.70  # Synthetic distinct trajectories should classify well
    assert eval_metrics.f1_macro > 0.0

    report_json = reports_dir / "eval_report.json"
    report_md = reports_dir / "eval_report.md"
    ModelEvaluator.save_report(eval_metrics, report_json, report_md)

    assert report_json.exists()
    assert report_md.exists()

    # Step 7: Packaging & Saving
    meta = PipelineMetadata(
        created_at_utc="2026-09-09T00:00:00Z",
        model_type="random_forest",
        version="1.0.0",
        classes=splits.classes,
        window_size=30,
        num_features=processed_dataset.X.shape[1],
        train_samples=len(splits.X_train),
        train_accuracy=train_res.train_score,
        val_accuracy=train_res.val_score,
    )
    pipeline = ExerciseClassificationPipeline(
        model=train_res.model,
        preprocessor=preprocessor,
        metadata=meta,
    )
    model_artifact = models_dir / "exercise_classifier.joblib"
    pipeline.save(model_artifact)
    assert model_artifact.exists()

    # Step 8: Inference from Loaded Artifact
    loaded_pipeline = ExerciseClassificationPipeline.load(model_artifact)
    engine = ExerciseInferenceEngine(pipeline=loaded_pipeline, confidence_threshold=0.60)

    for target_ex in ["squat", "push_up", "bicep_curl", "lunge", "shoulder_press"]:
        traj = BiomechanicalDataGenerator.generate_exercise_trajectory(target_ex, num_frames=30)
        inf_res = engine.predict_sequence(traj)

        assert "exercise" in inf_res
        assert "confidence" in inf_res
        assert "probabilities" in inf_res
        assert 0.0 <= inf_res["confidence"] <= 1.0
        assert len(inf_res["probabilities"]) == 6
