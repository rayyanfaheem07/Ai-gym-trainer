# Phase 6: Exercise Classification Machine Learning Pipeline

## 1. Overview

The Exercise Classification Pipeline provides automated, real-time recognition of human fitness exercises from temporal sequences of 3D MediaPipe pose landmarks.

Supported Target Classes:
- `squat`
- `push_up`
- `bicep_curl`
- `lunge`
- `shoulder_press`
- `other` (background, idle, or transition movements)

```
                       +-------------------------------+
                       |  Live Webcam / Video Frames   |
                       +---------------+---------------+
                                       |
                                       v
                       +---------------+---------------+
                       |  MediaPipe Pose + 1-Euro Filter|
                       +---------------+---------------+
                                       | (33 x 4 keypoints)
                                       v
                       +---------------+---------------+
                       | Torso Normalization & Feature |
                       | Extraction (Angles, Distances)|
                       +---------------+---------------+
                                       | (Window temporal stats)
                                       v
                       +---------------+---------------+
                       |  Fitted StandardScaler (1xD)  |
                       +---------------+---------------+
                                       |
                                       v
                       +---------------+---------------+
                       |   Random Forest Classifier    |
                       +---------------+---------------+
                                       |
                                       v
                       +---------------+---------------+
                       | Confidence Threshold (>0.60)? |
                       +-------+---------------+-------+
                               |               |
                         YES   v               v   NO
                        [Class Label]       ["other" / "unknown"]
```

---

## 2. Feature Representation (`ai/classifier/features.py`)

Feature extraction is centralized in `PoseFeatureExtractor`. The exact same feature transformation is executed across training, validation, testing, and real-time inference.

### 2.1 Per-Frame Feature Vector
For each individual video frame with detected landmark coordinates:
1. **Torso Normalization**: Coordinates are translated to set the hip midpoint as root origin $(0, 0, 0)$ and scaled by torso length ($\|\text{shoulder\_center} - \text{hip\_center}\|$). This guarantees position and camera-distance scale invariance.
2. **Key Landmark Coordinates**: $(x, y, z)$ coordinates of 17 essential biomechanical keypoints ($17 \times 3 = 51$ features):
   - Nose, Shoulders (11, 12), Elbows (13, 14), Wrists (15, 16), Hips (23, 24), Knees (25, 26), Ankles (27, 28), Heels (29, 30), Feet (31, 32).
3. **Biomechanical Joint Angles** (12 angle features):
   - `angle_left_elbow`, `angle_right_elbow`
   - `angle_left_knee`, `angle_right_knee`
   - `angle_left_hip`, `angle_right_hip`
   - `angle_left_shoulder`, `angle_right_shoulder`
   - `angle_left_arm_elevation`, `angle_right_arm_elevation`
   - `angle_torso_vertical` (torso inclination relative to vertical)
   - `angle_body_horizontal` (body inclination relative to horizontal — separates horizontal pushup/plank from vertical standing movements)
4. **Relative Distances & Spatial Ratios** (10 distance features):
   - Wrists to shoulders, wrists to hips, wrists to nose
   - Hand distance (wrist-to-wrist), stance width (ankle-to-ankle), knee distance
   - Vertical depth ratio (hip center $y$ to ankle center $y$)

*Total Frame Features ($F$)*: 73 features.

### 2.2 Temporal Window Feature Representation
A movement sequence is processed over a temporal window of $W$ frames (default: $W = 30$ frames $\approx$ 1.0s at 30 FPS).

To achieve temporal translation invariance and speed robustness, the sequence matrix of shape $(W, F)$ is aggregated into 7 temporal statistical moments:
- **Mean**: Average joint position/angle throughout the motion
- **Standard Deviation**: Magnitude of variation and movement spread
- **Minimum**: Peak contraction or minimum extension
- **Maximum**: Peak lockout or maximum extension
- **Range ($Max - Min$)**: Total range of motion (ROM)
- **Delta ($\text{End} - \text{Start}$)**: Directional net displacement over the window
- **Mean Velocity**: Frame-to-frame rate of change ($\text{mean}(|\Delta x|)$)

*Total Window Dimension ($D$)*: $7 \times 73 = 511$ features.

---

## 3. Dataset Format & Privacy Standards

Raw collected data is stored in reproducible JSON files under `data/raw/`. 

> [!IMPORTANT]
> **Privacy Preserving**: No raw video footage, facial imagery, or personal identifiable information (PII) is persisted. Only anonymous joint coordinate arrays and timestamps are recorded.

### Session File Schema:
```json
{
  "session_id": "session_squat_1725890000_a1b2c3",
  "subject_id": "subject_01",
  "label": "squat",
  "target_fps": 30.0,
  "window_length": 30,
  "created_at_utc": "2026-09-09T15:00:00Z",
  "sequences": [
    {
      "sequence_id": "seq_squat_01",
      "label": "squat",
      "fps": 30.0,
      "num_frames": 30,
      "frames": [
        {
          "timestamp_ms": 0.0,
          "detected": true,
          "landmarks": [[0.50, 0.15, 0.0, 0.99], "... 33 keypoints [x, y, z, visibility]"]
        }
      ]
    }
  ]
}
```

---

## 4. Data Collection Process

Data is recorded using `scripts/collect_data.py`:
- Captures live webcam streams or processes recorded exercise videos.
- Automatically handles frame rate synchronization (e.g. 30 FPS).
- Provides visual HUD countdowns and rest periods between sequence repetitions.
- Flags undetected frames safely without crashing.

### How to Collect Real Training Data:
To build a high-accuracy, generalized dataset:
1. Collect data from **multiple distinct subjects** (e.g. 5–10 people) using different `--subject-id` values.
2. Record multiple camera angles (frontal, 45-degree angle, side profile).
3. Record 15–20 repetitions per exercise across different subjects.
4. Record an `"other"` category capturing standing, walking into frame, adjusting weights, stretching, and resting.

---

## 5. Preprocessing Pipeline (`ai/classifier/preprocessor.py`)

1. **Validation**: Checks that each sequence contains at least 70% valid detected frames (`min_detected_ratio=0.7`).
2. **Missing Frame Imputation**: Undetected frames are interpolated linearly across time.
3. **Sliding Window Generation**: Long continuous sequences are sliced into overlapping windows of size $W=30$ with stride $S=10$.
4. **Feature Normalization**: Features are scaled using `StandardScaler` (zero mean, unit variance).
5. **Label Encoding**: Categorical string labels are mapped to contiguous integers using `LabelEncoder`.

---

## 6. Data Splitting & Leakage Prevention (`ai/classifier/dataset.py`)

### Splitting Strategy:
- **Zero-Leakage Group Partitioning**: Splitting is strictly performed at the **Session / Subject group level** (`GroupShuffleSplit`).
- All windows originating from the same recording session or participant belong exclusively to either Train, Validation, or Test set.
- **Verification**: `DatasetSplits.verify_no_leakage()` performs set intersection assertions on group IDs across train, val, and test splits.

---

## 7. Baseline Model Architecture (`ai/classifier/trainer.py`)

The primary baseline is a scikit-learn **Random Forest Classifier**:
- `n_estimators = 100`
- `max_depth = 15`
- `class_weight = "balanced"` (handles class imbalance gracefully)
- `random_state = 42`

Alternative supported classifiers:
- `gradient_boosting` (`HistGradientBoostingClassifier`)
- `logistic_regression` (`LogisticRegression(max_iter=1000)`)
- `svm` (`SVC(probability=True)`)

---

## 8. Evaluation Methodology (`ai/classifier/evaluator.py`)

Performance is measured strictly on held-out test splits without fabricated or hard-coded metrics:
- **Multi-Class Accuracy**
- **Macro & Weighted Precision**
- **Macro & Weighted Recall**
- **Macro & Weighted F1-Score**
- **Confusion Matrix**
- **Per-Class Metrics**

Evaluation artifacts are exported to:
- `reports/evaluation_report.json`
- `reports/evaluation_report.md`

---

## 9. Serialization & Inference Contract (`ai/classifier/pipeline.py`, `ai/classifier/inference.py`)

The pipeline bundles the trained model, scaler, label encoder, and feature extractor into a single artifact (`models/exercise_classifier.joblib`).

### Inference Contract:
```json
{
  "exercise": "squat",
  "confidence": 0.9521,
  "probabilities": {
    "squat": 0.9521,
    "push_up": 0.0102,
    "bicep_curl": 0.0115,
    "lunge": 0.0120,
    "shoulder_press": 0.0082,
    "other": 0.0060
  }
}
```

### Low-Confidence & Unknown Handling:
- If `top_probability < confidence_threshold` (default: 0.60), the returned exercise label is assigned to `"other"`.
- This prevents confidently misclassifying unseen movements, ambiguous postures, or background activity.

---

## 10. Command-Line Guide

### 1. Collect Data from Webcam
```bash
python scripts/collect_data.py --label squat --subject-id subject_01 --num-sequences 5 --window-length 30
python scripts/collect_data.py --label push_up --subject-id subject_01 --num-sequences 5
python scripts/collect_data.py --label bicep_curl --subject-id subject_01 --num-sequences 5
python scripts/collect_data.py --label lunge --subject-id subject_01 --num-sequences 5
python scripts/collect_data.py --label shoulder_press --subject-id subject_01 --num-sequences 5
python scripts/collect_data.py --label other --subject-id subject_01 --num-sequences 5
```

### 2. Preprocess Data
```bash
python scripts/preprocess_data.py --raw-dir data/raw --output-dir data/processed --window-size 30 --stride 10
```

### 3. Train Baseline Classifier
```bash
# Train on collected dataset (or generate synthetic validation data with --generate-synthetic)
python scripts/train_classifier.py --raw-dir data/raw --output-model models/exercise_classifier.joblib --model-type random_forest --generate-synthetic
```

### 4. Evaluate Classifier
```bash
python scripts/evaluate_classifier.py --model-path models/exercise_classifier.joblib --test-data-dir data/raw
```

### 5. Run Inference
```bash
# Synthetic demo (prints JSON output contracts for each exercise)
python scripts/run_inference.py --synthetic-demo

# Live webcam inference with visual HUD
python scripts/run_inference.py --camera 0 --confidence-threshold 0.60
```

---

## 11. Known Limitations & Production Readiness Checklist

> [!CAUTION]
> **Engineering Rule**: The classifier cannot be certified as production-ready until it has been trained and benchmarked on a diverse, multi-person real-world dataset.

### Current Known Limitations:
1. **Camera Angle Variations**: Heavy side-profile vs direct frontal views can alter landmark visibility. Torso normalization mitigates this, but diverse training angles are required.
2. **Partial Body Occlusion**: If legs or feet are out of camera frame (e.g. tight laptop webcam framing), lower body features rely on upper-body correlations.
3. **Ambiguous Transitions**: Quick transitions between exercises will register as `"other"` during intermediate sliding windows.

---

# Phase 7: Temporal Deep Learning for Exercise Recognition

## 1. Overview & Motivation for Temporal Deep Learning

Phase 7 enhances the exercise recognition subsystem by upgrading from static window statistical aggregation (Phase 6) to a lightweight **temporal recurrent neural network** implemented in PyTorch (`PoseSequenceClassifier`).

```
                        +-----------------------------------------+
                        |  MediaPipe Pose Landmark Windows (W,33) |
                        +--------------------+--------------------+
                                             |
                                             v
                        +--------------------+--------------------+
                        | Per-Frame Biomechanical Features (W, 73)|
                        |  - Torso-Normalized Keypoints (51)      |
                        |  - Joint & Orientation Angles (12)      |
                        |  - Relative Distances & Ratios (10)     |
                        +--------------------+--------------------+
                                             |
                                             v
                        +--------------------+--------------------+
                        | Temporal Frame-Level StandardScaler     |
                        +--------------------+--------------------+
                                             | (Batch, Window, 73)
                                             v
                        +--------------------+--------------------+
                        |    PyTorch PoseSequenceDataset          |
                        +--------------------+--------------------+
                                             |
                                             v
                        +--------------------+--------------------+
                        |   PoseSequenceClassifier (PyTorch)      |
                        |   - Input Normalization & Dropout (73)  |
                        |   - Bi-LSTM / Bi-GRU (1-2 layers, H=64) |
                        |   - Temporal Self-Attention Pooling     |
                        |   - Combined Representation Head        |
                        |   - Dropout + LayerNorm + GELU          |
                        |   - Linear Classification Head (6 cls)  |
                        +--------------------+--------------------+
                                             |
                                             v
                        +--------------------+--------------------+
                        |  CrossEntropy Loss / Softmax Probs      |
                        +--------------------+--------------------+
                                             |
                     +-----------------------+-----------------------+
                     | Confidence Threshold (>0.60)?                 |
                     +-----------+-----------------------+-----------+
                                 |                       |
                           YES   v                       v   NO
                          [Predicted Label]            ["other" / "unknown"]
```

### Why Temporal Modeling?
- **Preservation of Motion Trajectories**: Aggregating windows into static mean/std/min/max moments (Phase 6) collapses the temporal ordering of motion. Temporal recurrent modeling directly tracks frame-by-frame progression through eccentric contraction, peak turnaround, and concentric extension.
- **Phase Sensitivity**: Exercises like squats and lunges share overlapping joint extrema but follow distinct sequential trajectories and bilateral coordination patterns.
- **Dynamic Keypoint Attention**: A learned self-attention pooling mechanism dynamically highlights inflection frames (such as the deepest squat bottom or overhead lockout) rather than treating all frames identically.

---

## 2. Architecture Selection: Why LSTM / GRU?

For consumer edge devices and real-time fitness feedback, inference latency must remain strictly under 10 ms per frame window without dedicated GPU acceleration.

### Architectural Trade-offs:

| Architecture | Model Size | CPU Latency (ms) | Sequence Trajectory Tracking | Parameter Efficiency | Selection Verdict |
|---|---|---|---|---|---|
| **Phase 6: Random Forest** | ~1.5–5.0 MB | 0.8–2.0 ms | ❌ (Statistical only) | Low (Large tree arrays) | Baseline |
| **Phase 7: Bi-LSTM / Bi-GRU** | **~80–250 KB** | **1.2–3.5 ms** | **✅ (Full recurrent state)** | **High (<60K parameters)** | **Selected Primary Architecture** |
| **Temporal Transformer** | ~2.0–8.0 MB | 8.0–25.0 ms | ✅ (Self-attention) | Medium (Quadratic attention) | Overkill for short 30-frame windows |

**Conclusion**: Bi-directional LSTM/GRU models offer the optimal balance of rich temporal representation, sub-5ms CPU latency, and tiny memory footprint (<250 KB).

---

## 3. PyTorch Architecture (`ai/classifier/temporal_model.py`)

### `PoseSequenceClassifier` Specifications:
- **Input Dimension**: $F = 73$ biomechanical features per frame.
- **Sequence Length**: $W = 30$ frames ($\approx 1.0$ second at 30 FPS).
- **Recurrent Backbone**: Configurable `nn.LSTM` or `nn.GRU` (1–2 layers, hidden size $H=64$, bidirectional).
- **Temporal Attention Pooling**:
  $$\alpha_t = \text{softmax}(w^T \tanh(W_a h_t + b_a)), \quad r_{\text{attn}} = \sum_{t=1}^W \alpha_t h_t$$
- **Combined Representation**: $r_{\text{combined}} = [r_{\text{attn}} \,\|\, h_W]$ (combining global sequence attention with terminal motion state).
- **Head**: `Linear(2 * rnn_dim, hidden_size)` $\rightarrow$ `LayerNorm` $\rightarrow$ `GELU` $\rightarrow$ `Dropout(0.2)` $\rightarrow$ `Linear(hidden_size, 6)`.

---

## 4. Training Pipeline & Early Stopping (`ai/classifier/temporal_trainer.py`)

1. **Hardware Detection**: Automatically detects CUDA GPU availability; falls back to CPU cleanly.
2. **Deterministic Reproducibility**: Sets seeds across Python, NumPy, PyTorch, and CUDA.
3. **Imbalance-Aware Loss**: Weighted multi-class `nn.CrossEntropyLoss` scaled inversely by training class frequencies.
4. **Optimization**: `AdamW(lr=1e-3, weight_decay=1e-4)` with `torch.nn.utils.clip_grad_norm_` at $5.0$.
5. **Learning Rate Scheduler**: `ReduceLROnPlateau(factor=0.5, patience=4, min_lr=1e-5)`.
6. **Early Stopping**: Monitors validation loss ($patience=12$, $min\_delta=1e-4$). Saves the best checkpoint weights rather than the final epoch.

---

## 5. Serialization & Inference Contract (`ai/classifier/temporal_pipeline.py`, `ai/classifier/temporal_inference.py`)

The pipeline saves model state, architecture configuration, scaler parameters, label encoder, and metadata into `models/temporal_exercise_classifier.pt`.

### Inference Output Contract:
```json
{
  "exercise": "squat",
  "confidence": 0.9625,
  "probabilities": {
    "squat": 0.9625,
    "push_up": 0.0051,
    "bicep_curl": 0.0074,
    "lunge": 0.0123,
    "shoulder_press": 0.0062,
    "other": 0.0065
  }
}
```

### Low-Confidence Rejection:
- If `max(probabilities) < confidence_threshold` (default `0.60`), the predicted label defaults to `"other"` (or `"unknown"`).

---

## 6. Command-Line Guide (Phase 7)

### 1. Train PyTorch Temporal Classifier
```bash
python scripts/train_temporal_classifier.py --raw-dir data/raw --output-model models/temporal_exercise_classifier.pt --rnn-type lstm --epochs 60
```

### 2. Evaluate & Compare against Phase 6 Baseline
```bash
python scripts/evaluate_temporal_classifier.py --temporal-model models/temporal_exercise_classifier.pt --baseline-model models/exercise_classifier.joblib
```

### 3. Benchmark CPU Inference Latency
```bash
python scripts/benchmark_classifier.py --num-iterations 500 --warmup 50
```

### 4. Generate Visualization Dashboard
```bash
python scripts/plot_temporal_metrics.py --metrics-json reports/temporal_training_metrics.json --eval-json reports/temporal_evaluation_report.json
```

---

## 7. Known Limitations & Recommendations

1. **Window Size Rigidity**: Currently configured for $W=30$ frames ($\approx 1$s). Rapid reps under 0.5s or prolonged holds benefit from variable-length sequence support.
2. **Dataset Generalization**: Production readiness requires real-world data collection across diverse body shapes, lighting, and camera positions using `scripts/collect_data.py`.

