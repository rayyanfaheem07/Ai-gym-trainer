from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np

from ai.form_analysis.features import SquatFeatureExtractor, SquatKinematicFeatures
from ai.form_analysis.feedback import FeedbackGenerator
from ai.form_analysis.rules import FormIssue, SquatFormRuleConfig, SquatRuleEvaluator
from ai.form_analysis.scoring import FormScoringConfig, FormScoringEngine


@dataclass
class FormAnalysisResult:
    """Structured result returned by the form analysis engine."""
    form_score: int
    issues: List[Dict[str, Any]] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to clean serializable dictionary matching the required JSON format."""
        return {
            "form_score": self.form_score,
            "issues": self.issues,
            "feedback": self.feedback,
            "metrics": self.metrics,
        }


class SquatFormAnalysisEngine:
    """
    Modular, deterministic exercise form-analysis engine for Squats.
    Glues Feature Extraction -> Rule Evaluation -> Scoring -> Feedback Generation.
    """

    def __init__(
        self,
        rule_config: SquatFormRuleConfig | None = None,
        scoring_config: FormScoringConfig | None = None,
    ):
        self.rule_config = rule_config or SquatFormRuleConfig()
        self.scoring_config = scoring_config or FormScoringConfig()

        self.feature_extractor = SquatFeatureExtractor()
        self.rule_evaluator = SquatRuleEvaluator(config=self.rule_config)
        self.scoring_engine = FormScoringEngine(config=self.scoring_config)
        self.feedback_generator = FeedbackGenerator()

    def analyze_trajectory(self, trajectory_frames: List[np.ndarray]) -> FormAnalysisResult:
        """
        Analyzes a full rep trajectory of landmark arrays and returns structured form metrics.
        """
        features = self.feature_extractor.extract_from_trajectory(trajectory_frames)
        return self.analyze_features(features)

    def analyze_frame(self, landmarks: np.ndarray) -> FormAnalysisResult:
        """
        Analyzes a single frame's pose landmarks.
        """
        features = self.feature_extractor.extract_from_frame(landmarks)
        return self.analyze_features(features)

    def analyze_features(self, features: SquatKinematicFeatures) -> FormAnalysisResult:
        """
        Evaluates pre-extracted kinematic features against rules, computes score, and generates feedback.
        """
        # 1. Rule Evaluation
        issues: List[FormIssue] = self.rule_evaluator.evaluate(features)

        # 2. Score Computation (0 - 100)
        form_score: int = self.scoring_engine.compute_score(issues)

        # 3. Feedback Generation
        feedback: List[str] = self.feedback_generator.generate_feedback(issues)

        # 4. Serialize issues
        serialized_issues = [
            {
                "type": issue.type,
                "severity": issue.severity,
                "confidence": round(issue.confidence, 2),
                "details": issue.details,
            }
            for issue in issues
        ]

        metrics = {
            "min_knee_angle": round(features.min_knee_angle, 1),
            "max_torso_lean_deg": round(features.max_torso_lean_deg, 1),
            "knee_valgus_index": round(features.knee_valgus_index, 2),
            "symmetry_delta_deg": round(features.symmetry_delta_deg, 1),
            "lateral_instability_std": round(features.lateral_instability_std, 3),
        }

        return FormAnalysisResult(
            form_score=form_score,
            issues=serialized_issues,
            feedback=feedback,
            metrics=metrics,
        )
