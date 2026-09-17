# Biomechanical Multi-Exercise Engine Documentation

This document describes the common architecture, phase state machines, kinematic joint angle calculations, and explainable form rules for the 5 supported exercises.

---

## 1. Common Architecture: `BaseExerciseAnalyzer`

All exercises extend [`BaseExerciseAnalyzer`](file:///c:/Users/MOD/Desktop/ai-gym-trainer/ai/exercises/base.py) and produce a standardized [`ExerciseAnalysisResult`](file:///c:/Users/MOD/Desktop/ai-gym-trainer/ai/exercises/base.py):

```python
@dataclass
class ExerciseAnalysisResult:
    exercise: str
    phase: str
    rep_count: int = 0
    valid_reps: int = 0
    invalid_reps: int = 0
    confidence: float = 0.0
    primary_angle: float = 0.0
    current_angles: Dict[str, float] = field(default_factory=dict)
    form_score: int = 100
    is_valid_rep: bool = True
    issues: List[Dict[str, Any]] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    rep_duration_sec: float = 0.0
```

---

## 2. Exercise Specifications

### 1. Squat (`SquatDetector`)
- **Primary Angle**: Knee Flexion (Hip $\to$ Knee $\to$ Ankle).
- **Secondary Angles**: Hip angle, Torso lean from vertical.
- **Phases**: `standing` $\to$ `descending` $\to$ `bottom` $\to$ `ascending` $\to$ `completed_rep`.
- **Form Rules**:
  - `insufficient_depth`: $\theta_{\text{knee}} > 95^\circ$ at bottom.
  - `knee_alignment_problem`: $R_{\text{valgus}} < 0.90$ (knees caving inward).
  - `excessive_torso_lean`: $\theta_{\text{lean}} > 35^\circ$ forward inclination.
  - `left_right_asymmetry`: $|\theta_{\text{knee, left}} - \theta_{\text{knee, right}}| > 8^\circ$.
  - `movement_instability`: Lateral trajectory sway $\sigma_x > 0.035$.

---

### 2. Push-up (`PushupExercise`)
- **Primary Angle**: Elbow Flexion (Shoulder $\to$ Elbow $\to$ Wrist).
- **Secondary Angles**: Body line (Shoulder $\to$ Hip $\to$ Ankle), Elbow flare (Hip $\to$ Shoulder $\to$ Elbow).
- **Phases**: `plank` $\to$ `descending` $\to$ `bottom` $\to$ `ascending` $\to$ `completed_rep`.
- **Form Rules**:
  - `insufficient_depth`: $\theta_{\text{elbow}} > 90^\circ$ at bottom.
  - `hips_sagging`: $\theta_{\text{body}} < 155^\circ$ (sagging core).
  - `hips_piking`: $\theta_{\text{body}} > 195^\circ$ (elevated hips).
  - `excessive_elbow_flare`: $\theta_{\text{flare}} > 75^\circ$ from torso.
  - `arm_asymmetry`: $|\theta_{\text{elbow, left}} - \theta_{\text{elbow, right}}| > 12^\circ$.

---

### 3. Bicep Curl (`BicepCurlExercise`)
- **Primary Angle**: Elbow Flexion (Shoulder $\to$ Elbow $\to$ Wrist).
- **Secondary Angles**: Shoulder sway (Hip $\to$ Shoulder $\to$ Elbow), Torso pitch momentum.
- **Phases**: `extended` $\to$ `concentric` $\to$ `peak_flexion` $\to$ `eccentric` $\to$ `completed_rep`.
- **Form Rules**:
  - `incomplete_curl_flexion`: $\theta_{\text{elbow}} > 55^\circ$ at peak contraction.
  - `elbow_swinging`: Upper arm sway $\theta_{\text{sway}} > 20^\circ$.
  - `torso_momentum`: Backward torso pitch $\theta_{\text{pitch}} > 15^\circ$.
  - `arm_asymmetry`: $|\theta_{\text{elbow, left}} - \theta_{\text{elbow, right}}| > 15^\circ$.

---

### 4. Lunge (`LungeExercise`)
- **Primary Angle**: Lead Knee Flexion (Hip $\to$ Knee $\to$ Ankle).
- **Secondary Angles**: Trail Knee Flexion, Torso vertical inclination.
- **Phases**: `standing` $\to$ `descending` $\to$ `bottom` $\to$ `ascending` $\to$ `completed_rep`.
- **Form Rules**:
  - `insufficient_depth`: Lead knee $\theta_{\text{lead}} > 95^\circ$ at bottom.
  - `excessive_torso_lean`: Torso forward tilt $\theta_{\text{lean}} > 25^\circ$.
  - `stiff_trail_leg`: Trail knee $\theta_{\text{trail}} > 125^\circ$ (short step/stiff rear knee).
  - `movement_instability`: Lateral balance sway $\sigma_x > 0.040$.

---

### 5. Shoulder Press (`ShoulderPressExercise`)
- **Primary Angle**: Elbow Extension (Shoulder $\to$ Elbow $\to$ Wrist).
- **Secondary Angles**: Shoulder elevation (Hip $\to$ Shoulder $\to$ Elbow), Lumbar spine arch.
- **Phases**: `rack_position` $\to$ `ascending` $\to$ `overhead_lockout` $\to$ `descending` $\to$ `completed_rep`.
- **Form Rules**:
  - `incomplete_lockout`: Overhead elbow lockout $\theta_{\text{elbow}} < 155^\circ$.
  - `lumbar_hyperextension`: Excessive lower back arch $\theta_{\text{arch}} > 15^\circ$.
  - `arm_asymmetry`: Bilateral lockout delta $|\theta_{\text{left}} - \theta_{\text{right}}| > 12^\circ$.
  - `movement_instability`: Lateral bar trajectory sway $\sigma_x > 0.040$.

---

## 3. Dynamic Registration (Open-Closed Principle)

New exercises can be plugged into the engine at runtime without altering existing code:

```python
from ai.exercises.registry import ExerciseRegistry
from ai.exercises.base import BaseExerciseAnalyzer

class LateralRaiseExercise(BaseExerciseAnalyzer):
    def __init__(self):
        super().__init__(name="lateral_raise")

    def analyze_frame(self, landmarks, timestamp_ms=None):
        ...

# Dynamic registration
ExerciseRegistry.register("lateral_raise", LateralRaiseExercise)
```
