# Form Scoring Methodology: Biomechanical Rules & Scoring Engine

This document details the deterministic, explainable form analysis and scoring engine used for exercise movement evaluation.

---

## 1. Core Principles

1. **Deterministic & Explainable**: Every point deducted from the form score corresponds to an observable, measurable kinematic violation.
2. **No Black-Box / No LLM for Real-Time Scoring**: Mathematical geometry and biomechanical thresholds dictate penalties and feedback.
3. **Bounded & Normal Scale**: Scores range from $0$ to $100$ ($100$ represents textbook execution).
4. **Configurable**: Thresholds, penalty points, and severity multipliers are customizable via configuration classes without code modifications.

---

## 2. Form Score Mathematical Formulation

The overall repetition form score $S \in [0, 100]$ is computed as:

$$S = \max\left(0, \min\left(100, S_{\text{base}} - \sum_{i=1}^{N} P_i \cdot M(\text{severity}_i)\right)\right)$$

Where:
- $S_{\text{base}} = 100$ (Baseline maximum score for a perfect rep).
- $P_i$ = Base penalty points assigned to detected issue $i$.
- $M(\text{severity}_i)$ = Multiplier based on the severity level of issue $i$:
  - $\text{Low}: 1.0\times$
  - $\text{Medium}: 1.0\times$
  - $\text{High}: 1.25\times$

---

## 3. Squat Form Issue Definitions & Thresholds

### Issue 1: Insufficient Squat Depth (`insufficient_depth`)
- **Kinematic Metric**: Minimum bilateral knee flexion angle ($\theta_{\text{knee}}$ in degrees) reached during the rep.
- **Biomechanical Reference**: Full depth requires femur to break parallel to floor ($\theta_{\text{knee}} \le 95^\circ$).
- **Rules**:
  - $\theta_{\text{knee}} \le 95^\circ$: **Clean** (0 pts deducted)
  - $95^\circ < \theta_{\text{knee}} \le 105^\circ$: **Low Severity** (8 pts deduction)
  - $105^\circ < \theta_{\text{knee}} \le 120^\circ$: **Medium Severity** (15 pts deduction)
  - $\theta_{\text{knee}} > 120^\circ$: **High Severity** (25 pts deduction $\times 1.25 = 31.25$ pts)

---

### Issue 2: Knee Alignment / Knee Valgus (`knee_alignment_problem`)
- **Kinematic Metric**: Valgus Ratio $R_{\text{valgus}} = \frac{\|\mathbf{p}_{\text{knee, left}} - \mathbf{p}_{\text{knee, right}}\|}{\|\mathbf{p}_{\text{ankle, left}} - \mathbf{p}_{\text{ankle, right}}\|}$ measured at the bottom phase of the squat.
- **Biomechanical Reference**: Knees should track in line with or slightly outside the ankles ($R_{\text{valgus}} \ge 0.90$).
- **Rules**:
  - $R_{\text{valgus}} \ge 0.90$: **Clean** (0 pts deducted)
  - $0.78 \le R_{\text{valgus}} < 0.90$: **Low Severity** (6 pts deduction)
  - $0.65 \le R_{\text{valgus}} < 0.78$: **Medium Severity** (12 pts deduction)
  - $R_{\text{valgus}} < 0.65$: **High Severity** (20 pts deduction $\times 1.25 = 25$ pts)

---

### Issue 3: Excessive Forward Torso Lean (`excessive_torso_lean`)
- **Kinematic Metric**: Angular deviation $\theta_{\text{lean}}$ in degrees of the torso vector $(\mathbf{p}_{\text{shoulder}} - \mathbf{p}_{\text{hip}})$ from vertical.
- **Biomechanical Reference**: Excessive forward pitch shifts shearing stress directly to the lumbar spine.
- **Rules**:
  - $\theta_{\text{lean}} \le 35^\circ$: **Clean** (0 pts deducted)
  - $35^\circ < \theta_{\text{lean}} \le 48^\circ$: **Low Severity** (6 pts deduction)
  - $48^\circ < \theta_{\text{lean}} \le 60^\circ$: **Medium Severity** (12 pts deduction)
  - $\theta_{\text{lean}} > 60^\circ$: **High Severity** (20 pts deduction $\times 1.25 = 25$ pts)

---

### Issue 4: Bilateral Left/Right Asymmetry (`left_right_asymmetry`)
- **Kinematic Metric**: Angular difference $\Delta_{\text{sym}} = |\theta_{\text{knee, left}} - \theta_{\text{knee, right}}|$ during movement.
- **Biomechanical Reference**: Equal loading across both legs prevents hip shift and pelvic rotational shear.
- **Rules**:
  - $\Delta_{\text{sym}} \le 8^\circ$: **Clean** (0 pts deducted)
  - $8^\circ < \Delta_{\text{sym}} \le 16^\circ$: **Medium Severity** (8 pts deduction)
  - $\Delta_{\text{sym}} > 16^\circ$: **High Severity** (15 pts deduction $\times 1.25 = 18.75$ pts)

---

### Issue 5: Movement Instability / Bar Sway (`movement_instability`)
- **Kinematic Metric**: Standard deviation $\sigma_{x}$ of the horizontal center-of-mass/hip coordinate trajectory across the repetition.
- **Biomechanical Reference**: Controlled vertical descent/ascent with minimal lateral perturbation.
- **Rules**:
  - $\sigma_{x} \le 0.035$: **Clean** (0 pts deducted)
  - $0.035 < \sigma_{x} \le 0.070$: **Medium Severity** (8 pts deduction)
  - $\sigma_{x} > 0.070$: **High Severity** (15 pts deduction $\times 1.25 = 18.75$ pts)

---

## 4. Structured Output Format

```json
{
  "form_score": 82,
  "issues": [
    {
      "type": "insufficient_depth",
      "severity": "medium",
      "confidence": 0.88,
      "details": "Minimum knee flexion was 108.4° (target: <= 95.0°)."
    }
  ],
  "feedback": [
    "Increase squat depth; break parallel by lowering hips below knee level."
  ],
  "metrics": {
    "min_knee_angle": 108.4,
    "max_torso_lean_deg": 28.5,
    "knee_valgus_index": 0.94,
    "symmetry_delta_deg": 3.2,
    "lateral_instability_std": 0.018
  }
}
```
