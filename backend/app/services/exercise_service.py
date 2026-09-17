from ai.exercises.registry import ExerciseRegistry
from backend.app.schemas.exercise import ExerciseItemResponse, ExerciseListResponse

# Canonical exercise metadata dictionary
EXERCISE_METADATA: dict[str, dict] = {
    "squat": {
        "display_name": "Bodyweight & Barbell Squat",
        "category": "compound_lower",
        "target_muscles": ["Quadriceps", "Gluteus Maximus", "Hamstrings", "Core"],
        "primary_joints": ["Left Hip", "Right Hip", "Left Knee", "Right Knee"],
        "description": "Full lower-body compound movement emphasizing hip hinge, knee flexion past parallel, and upright thoracic posture.",
        "form_rules": [
            "Depth check: Hips must descend below knee level (knee angle <= 90 deg)",
            "Knee valgus: Knees must track over toes without collapsing inward",
            "Back alignment: Torso must avoid excessive forward lean",
            "Lockout: Full hip and knee extension at the top of the rep",
        ],
    },
    "pushup": {
        "display_name": "Standard Push-Up",
        "category": "compound_upper_push",
        "target_muscles": ["Pectoralis Major", "Anterior Deltoids", "Triceps Brachii", "Core"],
        "primary_joints": ["Left Elbow", "Right Elbow", "Left Shoulder", "Right Shoulder"],
        "description": "Upper-body horizontal pressing movement maintaining a rigid plank and full elbow flexion/extension.",
        "form_rules": [
            "Depth check: Chest must lower until elbows reach <= 90 degrees",
            "Plank integrity: Hips must not sag below shoulder-ankle line",
            "Piking: Hips must not elevate excessively above line",
            "Lockout: Complete elbow extension at rep completion",
        ],
    },
    "bicep_curl": {
        "display_name": "Standing Dumbbell Bicep Curl",
        "category": "isolation_upper_pull",
        "target_muscles": ["Biceps Brachii", "Brachialis", "Brachioradialis"],
        "primary_joints": ["Left Elbow", "Right Elbow", "Left Shoulder", "Right Shoulder"],
        "description": "Isolated elbow flexion movement with stationary torso and fixed elbow positioning.",
        "form_rules": [
            "Elbow stability: Elbows must remain pinned to the torso sides without swinging",
            "Full range of motion: Elbow flexion reaching <= 50 degrees",
            "Extension: Complete controlled eccentric extension (>= 155 degrees)",
            "Torso momentum: No lumbar extension / body swing during concentric phase",
        ],
    },
    "lunge": {
        "display_name": "Forward & Reverse Walking Lunge",
        "category": "unilateral_lower",
        "target_muscles": ["Quadriceps", "Gluteus Medius", "Gluteus Maximus", "Hamstrings"],
        "primary_joints": ["Lead Knee", "Trail Knee", "Lead Hip", "Trail Hip"],
        "description": "Unilateral lower body stepping exercise assessing single-leg stability, depth, and vertical torso alignment.",
        "form_rules": [
            "Lead knee angle: Must reach ~90 degree bend at lowest point",
            "Knee over toe: Lead knee should not excessively surpass front toes",
            "Trail knee: Should lightly hover just above floor level",
            "Pelvic tilt: Hips must remain square and level throughout step",
        ],
    },
    "shoulder_press": {
        "display_name": "Overhead Shoulder Press",
        "category": "compound_upper_push",
        "target_muscles": ["Anterior Deltoids", "Lateral Deltoids", "Triceps Brachii", "Upper Trapezius"],
        "primary_joints": ["Left Shoulder", "Right Shoulder", "Left Elbow", "Right Elbow"],
        "description": "Vertical pressing movement requiring full overhead lockout with neutral spine and stable core.",
        "form_rules": [
            "Starting depth: Elbows tucked near shoulder height (~80-90 degrees)",
            "Overhead lockout: Full elbow extension overhead with bar/hands over shoulders",
            "Lumbar hyperextension: Avoid arching lower back during pressing phase",
            "Symmetry: Both arms must press evenly without unilateral deviation",
        ],
    },
}


class ExerciseService:
    @staticmethod
    def get_supported_exercises() -> ExerciseListResponse:
        """
        Retrieves list of all supported exercises registered in the AI system.
        """
        registered_keys = ExerciseRegistry.list_available()
        exercise_items: list[ExerciseItemResponse] = []

        for name in registered_keys:
            meta = EXERCISE_METADATA.get(
                name,
                {
                    "display_name": name.replace("_", " ").title(),
                    "category": "exercise",
                    "target_muscles": ["Full Body"],
                    "primary_joints": ["Core"],
                    "description": f"AI-tracked {name.replace('_', ' ')} exercise.",
                    "form_rules": ["Maintain proper form and tempo throughout."],
                },
            )
            exercise_items.append(
                ExerciseItemResponse(
                    name=name,
                    display_name=meta["display_name"],
                    category=meta["category"],
                    target_muscles=meta["target_muscles"],
                    primary_joints=meta["primary_joints"],
                    description=meta["description"],
                    form_rules=meta["form_rules"],
                )
            )

        return ExerciseListResponse(
            exercises=exercise_items,
            count=len(exercise_items),
        )
