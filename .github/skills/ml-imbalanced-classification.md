---
name: ml-imbalanced-classification
description: >
  Decision framework for classification problems with severe class imbalance
  (positive rate < 10%). Use when building any model that predicts rare events:
  SLA breaches, delinquencies, P1 incidents, churn, anomalies. Covers metric
  selection, split strategy, encoding safety, leakage prevention, and threshold
  calibration. Prevents the common failure modes: trusting ROC-AUC alone,
  reading the 0.5-threshold confusion matrix, and fitting scalers on the whole dataset.
---

# ML Imbalanced Classification

## When to invoke this skill

| Trigger | Action |
|---|---|
| Positive class rate < 10% | Apply this entire skill |
| "Why does my model predict all zeros?" | Check threshold — 0.5 is wrong; see §5 |
| "F1 is only 0.08 — is that bad?" | Read the F1 ceiling first; see §4 |
| "ROC-AUC looks fine but model is useless" | Switch to PR-AUC; see §4 |
| Any train/val/test split on imbalanced data | Stratify every split; see §2 |
| Encoding categorical features | Use OOF encoding for high-cardinality; see §3 |

---

## 1. Before You Touch the Data — Understand the Imbalance

Compute and record the positive rate immediately.

```python
rate = y.mean()
n_pos = y.sum()
print(f"Positive rate: {rate:.4f} ({rate*100:.2f}%)")
print(f"Positives: {n_pos} / {len(y)}")
```

The positive rate drives almost every subsequent decision:
- **< 1%** — PR-AUC is the only honest primary metric. ROC-AUC is misleading.
- **1–5%** — PR-AUC primary; ROC-AUC supplementary only.
- **5–10%** — Both are useful; watch for threshold problems.
- **Positives in any split < 50** — cross-validation is required; single val estimates are too noisy.

---

## 2. Splitting — Stratify Every Split, Without Exception

**Never use a plain random split on imbalanced data.** A random 80/20 split on a 1.78%-positive dataset can produce a validation set with almost no positive examples purely by chance.

```python
from sklearn.model_selection import train_test_split

X_trainval, X_test, y_trainval, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y   # <-- required
)
X_train, X_val, y_train, y_val = train_test_split(
    X_trainval, y_trainval, test_size=0.125, random_state=42, stratify=y_trainval
)
# Result: 70% train / 10% val / 20% test, each with same positive rate as full dataset
```

**Check your splits** — verify the positive rate is preserved:

```python
for name, y_ in [("train", y_train), ("val", y_val), ("test", y_test)]:
    print(f"{name}: {y_.mean():.4f}  ({y_.sum()} positives)")
```

If any split has fewer than ~50 positives, add cross-validation on the training set as a supplement — single-split estimates at that size will have high variance.

---

## 3. Leakage Prevention Checklist

Data leakage produces metrics that look great in development and collapse in production. The two most common failure modes on imbalanced data:

### 3a. Scaling leakage — fit only on training data

```python
# WRONG — leaks val/test statistics into training
scaler.fit(X_all)                  # never do this
X_train_scaled = scaler.transform(X_train)

# CORRECT — fit on train only, transform everywhere
scaler.fit(X_train)
X_train_scaled = scaler.transform(X_train)
X_val_scaled   = scaler.transform(X_val)
X_test_scaled  = scaler.transform(X_test)
```

### 3b. Target encoding leakage — use Out-of-Fold (OOF) encoding

If encoding a high-cardinality categorical column (e.g., US state, product category), computing per-category target means on the full training set and applying them back to training rows means each row indirectly "sees" its own label.

**Fix: OOF encoding**

```python
from sklearn.model_selection import StratifiedKFold
import numpy as np

def oof_target_encode(X_train, y_train, col, smoothing=10):
    global_mean = y_train.mean()
    oof_encoded  = np.zeros(len(X_train))
    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for train_idx, val_idx in kf.split(X_train, y_train):
        cat_means = y_train.iloc[train_idx].groupby(X_train.iloc[train_idx][col]).mean()
        counts    = X_train.iloc[train_idx].groupby(col).size()
        smoothed  = (cat_means * counts + global_mean * smoothing) / (counts + smoothing)
        oof_encoded[val_idx] = X_train.iloc[val_idx][col].map(smoothed).fillna(global_mean)
    return oof_encoded

# Verify OOF encoding didn't leak: mean of encoded values should ≈ true target rate
print(f"OOF mean: {oof_encoded.mean():.4f}  |  True rate: {y_train.mean():.4f}")
# If OOF mean >> true rate, encoding leaked
```

**When to use OOF vs OHE:**
- Low-cardinality (< 10 categories): use one-hot encoding — simpler, leakage-free
- High-cardinality (≥ 10 categories, especially ordinal): use smoothed OOF target encoding

---

## 4. Evaluation Metrics — Which to Use and Why

### Primary metric: PR-AUC (Precision-Recall AUC)

For imbalanced data, **PR-AUC is the honest primary metric**. It directly measures how useful the model's flagged positives are, without being diluted by the enormous negative class.

```python
from sklearn.metrics import average_precision_score, roc_auc_score

pr_auc  = average_precision_score(y_test, y_scores)
roc_auc = roc_auc_score(y_test, y_scores)

# Sanity check: random baseline for PR-AUC = positive rate itself
random_baseline = y_test.mean()
print(f"PR-AUC:  {pr_auc:.4f}  (random baseline: {random_baseline:.4f}, {pr_auc/random_baseline:.1f}× better)")
print(f"ROC-AUC: {roc_auc:.4f}  (random baseline: 0.500)")
```

**Why ROC-AUC misleads on imbalanced data:** The False Positive Rate (FPR) denominator is the huge negative class. A model can accumulate many false positives and barely move FPR — making ROC-AUC look decent even when the model is nearly useless in practice. Use it as a supplementary signal only.

### F1 score — always compute against the imbalanced ceiling

F1 has a mathematical ceiling imposed by class imbalance. Before calling any F1 "low":

```python
# F1 ceiling: a model that flags X% of all data at perfect recall
# Maximum achievable F1 when recall=1.0 and precision=positive_rate:
rate = y_test.mean()
f1_ceiling = 2 * rate / (1 + rate)
print(f"F1 ceiling (positive rate={rate:.4f}): {f1_ceiling:.4f}")
# e.g. with 1.78% positive rate: F1 ceiling = 0.035 — so F1=0.08 is >2× ceiling, which is good
```

**Never report F1 without the ceiling.** An F1 of 0.08 with a ceiling of 0.035 is strong. An F1 of 0.08 with a ceiling of 0.80 is a failure.

### Summary table

| Metric | Use it for | Watch out for |
|---|---|---|
| PR-AUC | **Primary** — ranks quality, imbalance-aware | Compare against positive rate as random baseline |
| ROC-AUC | Supplementary ranking signal | Looks decent even on weak models with heavy imbalance |
| F1 | Threshold-specific summary | Read against ceiling = `2*rate/(1+rate)`, not against 1.0 |
| Precision | Catching false alarms in a final model | Gamed by flagging almost nothing |
| Recall | Catching real positives | Gamed by flagging almost everything |

---

## 5. Classification Threshold — 0.5 Is Almost Always Wrong

For imbalanced data, the default 0.5 threshold is nearly always wrong. Raw model scores often don't cross 0.5 for a rare class even when the model is working correctly.

**Find the right threshold by sweeping the PR curve:**

```python
from sklearn.metrics import precision_recall_curve
import numpy as np

precisions, recalls, thresholds = precision_recall_curve(y_val, y_val_scores)

# Find threshold that maximizes F1 on validation set
f1_scores = 2 * precisions[:-1] * recalls[:-1] / (precisions[:-1] + recalls[:-1] + 1e-9)
best_idx   = np.argmax(f1_scores)
best_threshold = thresholds[best_idx]
print(f"Best threshold: {best_threshold:.4f}  |  P={precisions[best_idx]:.3f}  R={recalls[best_idx]:.3f}  F1={f1_scores[best_idx]:.3f}")

# Apply to test set
y_test_pred = (y_test_scores >= best_threshold).astype(int)
```

**If the model shows 0 true positives at threshold=0.5**, this is NOT total failure. Inspect the raw score distribution of positive examples:

```python
import pandas as pd
scores_df = pd.DataFrame({'score': y_test_scores, 'label': y_test})
print(scores_df[scores_df['label']==1]['score'].describe())
# Useful range for positive class will be visible here
```

---

## 6. Class Weighting — Tell the Model About the Imbalance

For tree-based models (XGBoost/LightGBM) and logistic regression, explicitly weight the minority class:

```python
# Logistic Regression
from sklearn.linear_model import LogisticRegression
lr = LogisticRegression(class_weight='balanced', ...)

# XGBoost
scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
# e.g. 9,822 negative / 178 positive = 55.2
import xgboost as xgb
xgb_model = xgb.XGBClassifier(scale_pos_weight=scale_pos_weight, ...)

# LightGBM
import lightgbm as lgb
lgb_model = lgb.LGBMClassifier(scale_pos_weight=scale_pos_weight, ...)
```

Without this, tree models and logistic regression silently ignore the minority class and learn to always predict the majority.

---

## 7. Missing Value Strategy — Preserve Absence Signal

For features where "missing" means something (e.g., "no prior credit history", "no previous incident"), plain median imputation destroys signal:

```python
# WRONG for semantically meaningful missingness
df['feature'].fillna(df['feature'].median(), inplace=True)

# CORRECT — add binary flag before filling
df['feature_was_missing'] = df['feature'].isna().astype(int)
df['feature'] = df['feature'].fillna(df['feature'].median())
```

Reserve plain median imputation for features where absence is truly random/administrative.

---

## Quick Checklist

```
Before training any classifier on imbalanced data:
[ ] Computed positive rate — recorded as baseline for all metric interpretation
[ ] Stratified every split (train/val/test AND any cross-validation)
[ ] Checked positives count in each split — if < 50, added CV supplement
[ ] Scaler fitted on training data only — never on val or test
[ ] High-cardinality encoding uses OOF — verified OOF mean ≈ true positive rate
[ ] Primary metric is PR-AUC — compared against positive-rate baseline
[ ] Computed F1 ceiling — all reported F1 scores read against ceiling
[ ] Swept PR curve to find threshold — not using 0.5 default
[ ] Set scale_pos_weight (tree models) or class_weight='balanced' (LR)
[ ] Semantically meaningful missing values: binary flag + fill, not median alone
```
