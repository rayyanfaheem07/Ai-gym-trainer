from dataclasses import dataclass
from typing import List

from ai.form_analysis.rules import FormIssue, Severity


@dataclass
class FormScoringConfig:
    """Configurable scoring parameters for form analysis."""
    base_score: float = 100.0                # Baseline maximum score for a perfect rep
    min_score: float = 0.0                   # Lower bound
    max_score: float = 100.0                 # Upper bound
    severity_multipliers: dict = None        # Multipliers for severity levels

    def __post_init__(self):
        if self.severity_multipliers is None:
            self.severity_multipliers = {
                Severity.LOW.value: 1.0,
                Severity.MEDIUM.value: 1.0,
                Severity.HIGH.value: 1.25,
            }


class FormScoringEngine:
    """
    Computes a deterministic, explainable form score from 0-100 based on evaluated form issues.

    Formula:
      Form Score = max(0, min(100, Base Score - sum(penalty_points * severity_multiplier)))
    """

    def __init__(self, config: FormScoringConfig | None = None):
        self.config = config or FormScoringConfig()

    def compute_score(self, issues: List[FormIssue]) -> int:
        """
        Calculates the integer form score between 0 and 100.
        """
        if not issues:
            return int(self.config.max_score)

        total_penalty = 0.0
        for issue in issues:
            multiplier = self.config.severity_multipliers.get(issue.severity, 1.0)
            total_penalty += issue.penalty_points * multiplier

        final_score = self.config.base_score - total_penalty
        clamped_score = max(self.config.min_score, min(self.config.max_score, final_score))
        return int(round(clamped_score))
