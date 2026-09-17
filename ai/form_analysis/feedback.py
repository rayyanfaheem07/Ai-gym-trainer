from typing import Dict, List

from ai.form_analysis.rules import FormIssue, IssueType, Severity


class FeedbackGenerator:
    """
    Generates clear, concise, actionable coaching feedback strings based on evaluated form issues.
    """

    _FEEDBACK_TEMPLATES: Dict[str, Dict[str, str]] = {
        IssueType.INSUFFICIENT_DEPTH.value: {
            Severity.LOW.value: "Squat just a little deeper to reach full parallel depth.",
            Severity.MEDIUM.value: "Increase squat depth; break parallel by lowering hips below knee level.",
            Severity.HIGH.value: "Squat significantly deeper. Ensure hips drop below knees at the bottom.",
        },
        IssueType.KNEE_ALIGNMENT.value: {
            Severity.LOW.value: "Keep knees pressed outward over toes.",
            Severity.MEDIUM.value: "Prevent knees from caving inward; push your knees outward during ascent.",
            Severity.HIGH.value: "Severe knee valgus detected. Actively drive knees out to protect joints.",
        },
        IssueType.EXCESSIVE_TORSO_LEAN.value: {
            Severity.LOW.value: "Keep your chest proud throughout the descent.",
            Severity.MEDIUM.value: "Avoid excessive forward torso lean; keep chest up and engage upper back.",
            Severity.HIGH.value: "Excessive forward torso collapse. Maintain an upright torso to protect lumbar spine.",
        },
        IssueType.ASYMMETRY.value: {
            Severity.LOW.value: "Focus on equal weight distribution between left and right legs.",
            Severity.MEDIUM.value: "Noticeable limb asymmetry. Distribute loading evenly through both feet.",
            Severity.HIGH.value: "Significant left/right imbalance. Check hip alignment and drive evenly.",
        },
        IssueType.MOVEMENT_INSTABILITY.value: {
            Severity.LOW.value: "Control your descent tempo for smoother balance.",
            Severity.MEDIUM.value: "Stabilize your movement path; minimize lateral hip sway.",
            Severity.HIGH.value: "Excessive lateral instability. Slow down and maintain a rigid core.",
        },
    }

    _DEFAULT_PERFECT_FEEDBACK = [
        "Excellent form! Depth, knee tracking, and torso stability were on point."
    ]

    @classmethod
    def generate_feedback(cls, issues: List[FormIssue]) -> List[str]:
        """
        Translates a list of FormIssues into prioritized feedback messages.
        """
        if not issues:
            return list(cls._DEFAULT_PERFECT_FEEDBACK)

        # Sort issues by penalty points (highest impact first)
        sorted_issues = sorted(issues, key=lambda x: x.penalty_points, reverse=True)

        feedback_list: List[str] = []
        for issue in sorted_issues:
            type_templates = cls._FEEDBACK_TEMPLATES.get(issue.type, {})
            msg = type_templates.get(issue.severity)
            if not msg:
                msg = f"Improve {issue.type.replace('_', ' ')}."
            if msg not in feedback_list:
                feedback_list.append(msg)

        return feedback_list
