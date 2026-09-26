# FinSight ML Upgrade Pack — Integration Guide

Three drop-in modules, ordered by expected payoff vs. effort. All tested and
runnable as-is (synthetic smoke tests included at the bottom of each file).

---

## 01_global_regime_lgbm.py — Fix the regime-routing regression

**Replaces:** your 4 independent per-regime LightGBM models.
**With:** 1 LightGBM model, `regime` passed as a categorical feature.

**Why:** Each of your 4 regime models currently trains on ~25% of your data.
That data starvation is almost certainly why regime-routing showed a **−0.4pp**
hit in your ablation instead of a gain. A single global model with `regime`
as a feature lets the tree split on regime only where it actually helps,
and pool statistical power everywhere else.

**Wiring into your pipeline:**
```python
from importlib import import_module
mod = import_module("01_global_regime_lgbm")

X = mod.build_feature_matrix(your_df, your_existing_26_feature_cols)
models, fold_metrics = mod.train_global_regime_model(X, your_target_series)
```
At inference: no more "detect regime → pick model" branch. Just compute
`regime` the same way and pass it in as a feature column to the single model.

**Expected outcome:** regime-aware contribution flips from negative to
positive (or at least neutral) in your ablation table, because you're no
longer destroying 75% of your training signal per model.

---

## 02_stacker_upgrade.py — Fix the meta-learner + the recall/specificity imbalance

**Replaces:** `sklearn.linear_model.Ridge` as your meta-learner.
**With:** a head-to-head comparison (Ridge / LogisticRegression / shallow
LightGBM / shallow XGBoost), evaluated on identical folds — pick the AUC
winner — **plus** isotonic calibration + Youden's-J threshold selection.

**Why — two separate problems, one fix:**
1. Ridge assumes the 5 inputs (`lstm_prob` + 4 LightGBM class probs)
   combine *linearly*. A shallow tree-based stacker can capture interactions
   like "LSTM bullish AND regime says Bull-Trending" that Ridge structurally
   cannot.
2. Your current 92.3% recall / 14.5% specificity split happens because
   you tune the decision threshold to **maximize F1** on an imbalanced-ish
   target — that objective rewards predicting the majority class almost
   always. Youden's J statistic (`sensitivity + specificity − 1`) forces
   a threshold that actually balances both error types.

**Wiring into your pipeline:**
```python
from importlib import import_module
mod = import_module("02_stacker_upgrade")

X_meta = mod.build_meta_features(your_lstm_probs, your_lgbm_4class_probs)
comparison = mod.StackerComparison(n_splits=3, test_size=252)
summary = comparison.run(X_meta, your_binary_target)
best_name = comparison.best_by_auc()
print("Use this as your production stacker:", best_name)

# Then calibrate + re-derive threshold on the winner:
final_model, threshold, metrics = mod.calibrate_and_retune(
    winning_model_instance, X_train, y_train, X_test, y_test
)
```

**Expected outcome:** AUC should move meaningfully above 0.50–0.54 if there's
real signal in your features (if it doesn't, that's itself useful — it tells
you the features need work, not the stacker). Recall/specificity should land
somewhere balanced (e.g., 65–75% each) instead of 92%/14%.

---

## 03_tcn_and_attention_lstm.py — Fix the weak LSTM (51.2% acc, AUC 0.509)

**Two options provided, pick one:**

**Option A — `build_tcn_model()` (recommended primary replacement):**
Dilated causal convolutions (dilations 1,2,4,8,16) replace the LSTM entirely.
Same input shape `(60, n_features)`, same sigmoid output — fully drop-in.
TCNs avoid vanishing-gradient issues over long windows and train faster.

**Option B — `build_lstm_attention_model()` (minimal-change alternative):**
Keeps your existing LSTM(128→64) architecture but makes the second LSTM
layer return full sequences and adds an additive (Bahdanau) attention layer
on top, so the model learns which of the 60 days matter most instead of
relying only on the final hidden state.

**Why:** Your standalone LSTM (51.2% accuracy, AUC 0.509) is barely above
noise and is your weakest individual component feeding the meta-learner.
Either option should raise the ceiling on what the stacker has to work with.

**Wiring into your pipeline:**
```python
from importlib import import_module
mod = import_module("03_tcn_and_attention_lstm")

# Option A:
model = mod.build_tcn_model(lookback=60, n_features=your_n_features)

# Option B:
model = mod.build_lstm_attention_model(lookback=60, n_features=your_n_features)

mod.train_sequence_model(model, X_train, y_train, X_val, y_val)
```
Run **both** and report them side by side in your ablation table — "LSTM vs
LSTM+Attention vs TCN" is a clean three-way comparison reviewers like.

---

## Suggested order of operations

1. Run `01` first — cheapest, fixes your worst current ablation result.
2. Run `02` next — cheap, likely your biggest single AUC/specificity gain.
3. Run `03` last — most expensive (GPU/CPU time for retraining), but fixes
   your weakest individual model. Feed its output (`lstm_prob` equivalent)
   back into `02`'s `build_meta_features()` once trained.

## After all three: re-run your existing tables

- Table VI (model performance) — re-generate with the new LSTM/TCN + new stacker
- Table VIII (ablation) — add a "Global regime-feature LightGBM" row
- Table IX (confusion matrix) — recall/specificity should look far less skewed
- Re-check AUC across the board — this is the metric that tells you whether
  these changes added real signal or just shuffled the same noise around
