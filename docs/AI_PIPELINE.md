# AI, Computer Vision & Biomechanics Pipeline

## 1. Landmark Extraction & Filtering
1. **MediaPipe Pose**: Ingests frames and outputs 33 3D body keypoints.
2. **One-Euro (1€) Adaptive Filtering**: Applies cutoff frequency dynamically based on keypoint velocity to eliminate high-frequency jitter while preserving sharp motion turns.

## 2. Biomechanical Geometric Rules

### Squat Evaluation
- **Primary Joint**: Knee flexion (Hip [23/24] - Knee [25/26] - Ankle [27/28]).
- **Lockout Angle**: $\ge 160^\circ$.
- **Target Depth**: $\le 95^\circ$.
- **Torso Lean**: Shoulder [11/12] - Hip [23/24] - Knee [25/26] must remain $\ge 60^\circ$ to prevent excessive forward spinal shearing.

### Push-up Evaluation
- **Primary Joint**: Elbow flexion (Shoulder [11/12] - Elbow [13/14] - Wrist [15/16]).
- **Lockout Angle**: $\ge 160^\circ$.
- **Depth Inflection**: $\le 90^\circ$.
- **Spinal Rigidity**: Shoulder - Hip - Ankle alignment angle must remain $\ge 150^\circ$ (prevent sagging hips).

### Bicep Curl Evaluation
- **Primary Joint**: Elbow flexion (Shoulder [12] - Elbow [14] - Wrist [16]).
- **Full Extension**: $\ge 150^\circ$.
- **Peak Contraction**: $\le 45^\circ$.
- **Upper Arm Drift**: Hip - Shoulder - Elbow sway angle must not exceed $25^\circ$.
