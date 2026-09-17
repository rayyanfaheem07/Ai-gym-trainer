from ai.classifier.collector import PoseDataCollector
from ai.classifier.dataset import DatasetSplits, GroupAwareDatasetSplitter
from ai.classifier.evaluator import EvaluationMetrics, ModelEvaluator
from ai.classifier.features import PoseFeatureExtractor
from ai.classifier.inference import (
    CANONICAL_EXERCISES,
    ExerciseInferenceEngine,
    StreamingExerciseClassifier,
)
from ai.classifier.model import ExerciseClassifier
from ai.classifier.pipeline import ExerciseClassificationPipeline, PipelineMetadata
from ai.classifier.preprocessor import DataPreprocessor, ProcessedDataset, ProcessedTemporalDataset
from ai.classifier.synthetic import BiomechanicalDataGenerator
from ai.classifier.trainer import ExerciseModelTrainer, TrainingResult

# Temporal PyTorch modules (conditionally loaded if PyTorch is installed)
try:
    from ai.classifier.temporal_dataset import PoseSequenceDataset, create_temporal_dataloaders
    from ai.classifier.temporal_evaluator import BaselineComparison, TemporalModelEvaluator
    from ai.classifier.temporal_inference import TemporalExerciseInferenceEngine
    from ai.classifier.temporal_model import PoseSequenceClassifier, TemporalAttention
    from ai.classifier.temporal_pipeline import TemporalClassificationPipeline
    from ai.classifier.temporal_trainer import (
        TemporalModelTrainer,
        TemporalTrainingResult,
        TrainingHistory,
        set_seed,
    )
except ImportError:
    PoseSequenceDataset = None  # type: ignore
    create_temporal_dataloaders = None  # type: ignore
    BaselineComparison = None  # type: ignore
    TemporalModelEvaluator = None  # type: ignore
    TemporalExerciseInferenceEngine = None  # type: ignore
    PoseSequenceClassifier = None  # type: ignore
    TemporalAttention = None  # type: ignore
    TemporalClassificationPipeline = None  # type: ignore
    TemporalModelTrainer = None  # type: ignore
    TemporalTrainingResult = None  # type: ignore
    TrainingHistory = None  # type: ignore
    set_seed = None  # type: ignore

__all__ = [
    "CANONICAL_EXERCISES",
    "BaselineComparison",
    "BiomechanicalDataGenerator",
    "DataPreprocessor",
    "DatasetSplits",
    "EvaluationMetrics",
    "ExerciseClassificationPipeline",
    "ExerciseClassifier",
    "ExerciseInferenceEngine",
    "ExerciseModelTrainer",
    "GroupAwareDatasetSplitter",
    "ModelEvaluator",
    "PipelineMetadata",
    "PoseDataCollector",
    "PoseFeatureExtractor",
    "PoseSequenceClassifier",
    "PoseSequenceDataset",
    "ProcessedDataset",
    "ProcessedTemporalDataset",
    "StreamingExerciseClassifier",
    "TemporalAttention",
    "TemporalClassificationPipeline",
    "TemporalExerciseInferenceEngine",
    "TemporalModelEvaluator",
    "TemporalModelTrainer",
    "TemporalTrainingResult",
    "TrainingHistory",
    "TrainingResult",
    "create_temporal_dataloaders",
    "set_seed",
]
