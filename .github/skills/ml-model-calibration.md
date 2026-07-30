---
name: ml-model-calibration
description: >
  Decision framework for ML model probability calibration. Use when a model's
  predicted probability numbers need to be trustworthy (not just its rankings) —
  e.g., expected-loss calculations, risk scoring, threshold-based alerts, or any
  use case that does arithmetic with the score. Covers when to calibrate, Platt
  vs. Isotonic selection, Brier score interpretation, calibration curve validation,
  and the critical distinction between discrimination and calibration.
---

# ML Model Calibration

## The core question to ask first

> "Do I need the *number* to be trustworthy, or just the *ranking*?"

| Use case | Calibration needed? |
|---|---|
| Rank loans by default risk (who to review first?) | **No** — ranking is unaffected by calibration |
| Compute expected dollar loss = `P(default) × loan_amount` | **Yes** — arithmetic on uncalibrated scores is wrong |
| Set a hard alert threshold ("flag if score > 3.5%") | **Yes** — threshold means nothing if the scale is arbitrary |
| Feature importance / SHAP analysis | **No** — ranking still valid |
| Reporting a probability to a human ("this loan has 3.5% default risk") | **Yes** — the number must mean what it claims |

If the answer is "ranking only," stop here. Calibration adds complexity and no benefit for pure ranking tasks.

---

## What calibration does (and does not do)

Calibration applies a **monotonic transformation** to raw model scores:
- It does **not** change the *order* of predictions — ROC-AUC and PR-AUC are unchanged
- It **does** change the *number* attached to each prediction so that a predicted 3.5% really means "roughly 3.5% of similarly-scored instances are positive"
- A calibrated model can have the same discrimination (ROC-AUC/PR-AUC) as the uncalibrated model with a dramatically lower Brier score

```
Uncalibrated:  ROC-AUC=0.72  PR-AUC=0.04  Brier=0.067  (probability numbers meaningless)
Calibrated:    ROC-AUC=0.72  PR-AUC=0.04  Brier=0.018  (probability numbers trustworthy)
```

If calibration changes ROC-AUC or PR-AUC, something went wrong (refitting, leakage).

---

## 1. Detect Miscalibration Before Deciding to Calibrate

### Brier Score — the primary calibration diagnostic

```python
from sklearn.metrics import brier_score_loss

brier = brier_score_loss(y_test, y_scores)

# Sanity anchors:
# - A model that always predicts the base rate gets Brier ≈ rate × (1-rate)
#   e.g. 1.78% positive → Brier_floor ≈ 0.0178 × 0.9822 ≈ 0.0175
# - Uncalibrated tree models on imbalanced data typically score Brier 3–5× above this
# - After calibration, Brier should drop to near the floor

base_rate   = y_test.mean()
brier_floor = base_rate * (1 - base_rate)
print(f"Brier score: {brier:.4f}")
print(f"Brier floor (always predict base rate): {brier_floor:.4f}")
print(f"Ratio above floor: {brier/brier_floor:.1f}×")
# Ratio > 2× → miscalibration is significant, calibration will help
# Ratio ≈ 1× → already well-calibrated (rare for tree models out of the box)
```

**Do NOT read Brier score in isolation.** A model with no discriminative signal can achieve a low Brier by always predicting the base rate — that's not calibration, it's a useless model. Always pair Brier with ROC-AUC/PR-AUC.

### Calibration Curve (Reliability Diagram)

```python
from sklearn.calibration import calibration_curve
import matplotlib.pyplot as plt

fraction_pos, mean_pred = calibration_curve(y_test, y_scores, n_bins=10, strategy='quantile')

plt.figure(figsize=(6, 5))
plt.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
plt.plot(mean_pred, fraction_pos, 's-', label='Model')
plt.xlabel('Mean predicted probability')
plt.ylabel('Fraction of positives (actual rate)')
plt.title('Calibration Curve')
plt.legend()
plt.tight_layout()
```

**Reading the curve:**
- Points **above** the diagonal → model is underconfident (predicts lower probability than actual)
- Points **below** the diagonal → model is overconfident (predicts higher probability than actual)
- Tree models (XGBoost/LightGBM) on imbalanced data typically cluster predictions toward 0 with overconfidence — points fall far below the diagonal in the low-score range

---

## 2. Choose a Calibration Method

The single most important factor is **how many positive examples are in your calibration set**.

```python
n_pos_cal = y_cal.sum()
print(f"Positives in calibration set: {n_pos_cal}")
```

| Positives in calibration set | Recommended method | Reason |
|---|---|---|
| **< 100** | Platt scaling (sigmoid) | Isotonic will overfit to exact calibration points |
| **100–1,000** | Platt scaling preferred; isotonic if curve clearly non-sigmoid | Isotonic becomes viable but Platt is safer |
| **> 1,000** | Either; isotonic if miscalibration is clearly non-sigmoid | Isotonic can capture complex curve shapes |
| **> 10,000** | Isotonic preferred if complex miscalibration exists | Enough data to estimate step function reliably |

**The small-data trap:** Isotonic regression will almost always win on Brier score evaluated on its own calibration set, regardless of calibration set size — because it can fit a step function exactly to those points. This is overfitting, not better calibration. Verify by checking PR-AUC on a held-out **test** set (never seen during calibration). If isotonic drops PR-AUC vs. uncalibrated on test, it overfit.

### Platt Scaling (Sigmoid)

Fits a 2-parameter logistic curve: `P_cal = 1 / (1 + exp(-(A × score + B)))`

- **Strengths:** stable with < 100 positives; cannot overfit (only 2 parameters)
- **Weaknesses:** can only correct sigmoid-shaped miscalibration; if the true curve has plateaus or kinks, Platt cannot capture them

### Isotonic Regression

Fits a non-parametric, monotone step function.

- **Strengths:** can represent any monotonic calibration curve; often wins with large datasets
- **Weaknesses:** overfits badly with < ~1,000 positives; produces "plateaus" (ties) that reflect calibration-set noise, not real probability structure

---

## 3. Fit the Calibrator — Leakage-Safe

**Critical rule:** the calibrator must never see the data used to train the base model. Use a separate held-out validation set or `CalibratedClassifierCV`.

### Option A: `CalibratedClassifierCV` (preferred for new models)

```python
from sklearn.calibration import CalibratedClassifierCV

# method='sigmoid' → Platt   |   method='isotonic' → Isotonic
calibrated_model = CalibratedClassifierCV(
    base_estimator=xgb_model,
    cv=5,              # 5-fold: fits base model on 4 folds, calibrates on held-out fold
    method='sigmoid'
)
calibrated_model.fit(X_train, y_train)
# Note: this refits the base model internally — use only when you want the full pipeline retrained
```

### Option B: Manual calibration on a held-out validation set (preferred when base model is already trained)

```python
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import numpy as np

# Get raw scores from already-trained model on validation set
val_scores = trained_model.predict_proba(X_val)[:, 1]

# Platt scaling
platt = LogisticRegression()
platt.fit(val_scores.reshape(-1, 1), y_val)
def platt_calibrate(scores):
    return platt.predict_proba(scores.reshape(-1, 1))[:, 1]

# Isotonic regression
iso = IsotonicRegression(out_of_bounds='clip')
iso.fit(val_scores, y_val)
def iso_calibrate(scores):
    return iso.predict(scores)

# Apply to test set
test_scores_raw    = trained_model.predict_proba(X_test)[:, 1]
test_scores_platt  = platt_calibrate(test_scores_raw)
test_scores_iso    = iso_calibrate(test_scores_raw)
```

**scikit-learn version note:** `CalibratedClassifierCV` with `cv='prefit'` was removed in scikit-learn 1.8. If you see `ValueError: cv='prefit' is not supported`, use Option B (manual calibration on the validation set) instead.

---

## 4. Validate Calibration — Required Steps

Run all three checks. None alone is sufficient.

### Check 1 — Brier score (before and after)

```python
from sklearn.metrics import brier_score_loss

b_raw   = brier_score_loss(y_test, test_scores_raw)
b_cal   = brier_score_loss(y_test, test_scores_platt)
print(f"Brier (uncalibrated): {b_raw:.4f}")
print(f"Brier (calibrated):   {b_cal:.4f}  ({b_raw/b_cal:.1f}× improvement)")
```

A 2–5× improvement is typical for tree models on imbalanced data.

### Check 2 — Discrimination unchanged (ROC-AUC and PR-AUC must be stable)

```python
from sklearn.metrics import roc_auc_score, average_precision_score

roc_raw = roc_auc_score(y_test, test_scores_raw)
roc_cal = roc_auc_score(y_test, test_scores_platt)
pr_raw  = average_precision_score(y_test, test_scores_raw)
pr_cal  = average_precision_score(y_test, test_scores_platt)

print(f"ROC-AUC: {roc_raw:.4f} → {roc_cal:.4f}  (should be identical)")
print(f"PR-AUC:  {pr_raw:.4f}  → {pr_cal:.4f}  (should be identical)")
```

If ROC-AUC or PR-AUC changes by more than 0.002: the calibrator is changing prediction *order*, not just *scale*. This indicates leakage, refitting on wrong data, or isotonic overfitting. Investigate before proceeding.

### Check 3 — Calibration curve on test set

```python
from sklearn.calibration import calibration_curve

frac_raw, mean_raw = calibration_curve(y_test, test_scores_raw,   n_bins=10, strategy='quantile')
frac_cal, mean_cal = calibration_curve(y_test, test_scores_platt, n_bins=10, strategy='quantile')

# Points from calibrated model should lie close to the diagonal
# Compute mean absolute deviation from diagonal as a scalar summary
mad_raw = np.mean(np.abs(frac_raw - mean_raw))
mad_cal = np.mean(np.abs(frac_cal - mean_cal))
print(f"Calibration MAD (raw):        {mad_raw:.4f}")
print(f"Calibration MAD (calibrated): {mad_cal:.4f}  (should be << raw)")
```

---

## 5. Select Final Model — Decision Table

After running both Platt and Isotonic (if applicable), use this decision table:

| Scenario | Use |
|---|---|
| Isotonic PR-AUC on test ≥ Platt PR-AUC on test AND Brier better | Isotonic |
| Isotonic PR-AUC on test < Platt PR-AUC on test | Platt — isotonic overfit |
| Positives in calibration set < 100 | Platt — no comparison needed |
| Brier improvement < 20% from either | Reconsider: model may lack signal; calibration won't rescue a weak model |

---

## 6. Use the Calibrated Model Correctly

```python
# For RANKING tasks (who to review first, leaderboard ordering):
# Use raw scores — calibration adds nothing and isn't needed
ranked = sorted(zip(loan_ids, test_scores_raw), key=lambda x: -x[1])

# For ARITHMETIC tasks (expected loss, dollar-weighted risk):
# Use calibrated scores — only these are trustworthy as probabilities
expected_loss = test_scores_platt * loan_amounts  # only valid with calibrated scores

# For THRESHOLD tasks (alert if risk > 3.5%):
# Use calibrated scores — threshold means something only when probabilities are honest
alerts = loan_ids[test_scores_platt > 0.035]
```

---

## Quick Checklist

```
Before reporting model probabilities as meaningful numbers:
[ ] Determined use case: ranking-only (skip calibration) vs. arithmetic/threshold (calibrate)
[ ] Brier score computed and compared to base-rate floor
[ ] Calibration curve plotted on validation set
[ ] Counted positives in calibration set — chose method accordingly
[ ] If < 100 positives: Platt only, no isotonic comparison needed
[ ] If ≥ 100 positives: ran both, compared PR-AUC on held-out TEST set
[ ] Calibrator fitted on data NOT used to train base model (no leakage)
[ ] Brier improved ≥ 2×; if not, investigated signal vs. calibration issue
[ ] ROC-AUC and PR-AUC unchanged after calibration (within 0.002)
[ ] Calibration curve shows test points near diagonal
[ ] Final code paths: raw scores for ranking, calibrated scores for arithmetic/thresholds
```
