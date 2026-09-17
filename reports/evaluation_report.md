# Exercise Classifier - Model Evaluation Report

## Summary Metrics
- **Test Samples**: 120
- **Accuracy**: 100.00%
- **Macro F1 Score**: 1.0000
- **Weighted F1 Score**: 1.0000
- **Macro Precision**: 1.0000
- **Macro Recall**: 1.0000

## Per-Class Performance
| Class | Precision | Recall | F1 Score | Support |
|---|---|---|---|---|
| `bicep_curl` | 1.0000 | 1.0000 | 1.0000 | 20 |
| `lunge` | 1.0000 | 1.0000 | 1.0000 | 20 |
| `other` | 1.0000 | 1.0000 | 1.0000 | 20 |
| `push_up` | 1.0000 | 1.0000 | 1.0000 | 20 |
| `shoulder_press` | 1.0000 | 1.0000 | 1.0000 | 20 |
| `squat` | 1.0000 | 1.0000 | 1.0000 | 20 |

## Confusion Matrix
Classes: `bicep_curl`, `lunge`, `other`, `push_up`, `shoulder_press`, `squat`

```
[[20  0  0  0  0  0]
 [ 0 20  0  0  0  0]
 [ 0  0 20  0  0  0]
 [ 0  0  0 20  0  0]
 [ 0  0  0  0 20  0]
 [ 0  0  0  0  0 20]]
```

## Full Scikit-Learn Classification Report
```
                precision    recall  f1-score   support

    bicep_curl       1.00      1.00      1.00        20
         lunge       1.00      1.00      1.00        20
         other       1.00      1.00      1.00        20
       push_up       1.00      1.00      1.00        20
shoulder_press       1.00      1.00      1.00        20
         squat       1.00      1.00      1.00        20

      accuracy                           1.00       120
     macro avg       1.00      1.00      1.00       120
  weighted avg       1.00      1.00      1.00       120

```