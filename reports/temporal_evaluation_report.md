# Exercise Classifier - Model Evaluation Report

## Summary Metrics
- **Test Samples**: 24
- **Accuracy**: 100.00%
- **Macro F1 Score**: 1.0000
- **Weighted F1 Score**: 1.0000
- **Macro Precision**: 1.0000
- **Macro Recall**: 1.0000

## Per-Class Performance
| Class | Precision | Recall | F1 Score | Support |
|---|---|---|---|---|
| `bicep_curl` | 1.0000 | 1.0000 | 1.0000 | 24 |
| `lunge` | 0.0000 | 0.0000 | 0.0000 | 0 |
| `other` | 0.0000 | 0.0000 | 0.0000 | 0 |
| `push_up` | 0.0000 | 0.0000 | 0.0000 | 0 |
| `shoulder_press` | 0.0000 | 0.0000 | 0.0000 | 0 |
| `squat` | 0.0000 | 0.0000 | 0.0000 | 0 |

## Confusion Matrix
Classes: `bicep_curl`, `lunge`, `other`, `push_up`, `shoulder_press`, `squat`

```
[[24  0  0  0  0  0]
 [ 0  0  0  0  0  0]
 [ 0  0  0  0  0  0]
 [ 0  0  0  0  0  0]
 [ 0  0  0  0  0  0]
 [ 0  0  0  0  0  0]]
```

## Full Scikit-Learn Classification Report
```
                precision    recall  f1-score   support

    bicep_curl       1.00      1.00      1.00        24
         lunge       0.00      0.00      0.00         0
         other       0.00      0.00      0.00         0
       push_up       0.00      0.00      0.00         0
shoulder_press       0.00      0.00      0.00         0
         squat       0.00      0.00      0.00         0

      accuracy                           1.00        24
     macro avg       0.17      0.17      0.17        24
  weighted avg       1.00      1.00      1.00        24

```