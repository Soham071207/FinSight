"""
FinSight CIBIL Score ML Model - Training Script
================================================
Run this ONCE to train the model and save artifacts.
Usage: python train_cibil_model.py

Requirements:
    pip install lightgbm scikit-learn pandas openpyxl joblib

Output artifacts (save all these alongside your Flask server):
    cibil_model.pkl
    cibil_medians.pkl
    cibil_features.pkl
    cibil_encoders.pkl
    cibil_cat_cols.pkl
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder
import joblib
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# 1. LOAD DATA
# ─────────────────────────────────────────────
print("Loading datasets...")
internal = pd.read_excel("Internal_Bank_Dataset.xlsx")
external = pd.read_excel("External_Cibil_Dataset.xlsx")
unseen   = pd.read_excel("Unseen_Dataset.xlsx")

print(f"  Internal : {internal.shape}")
print(f"  External : {external.shape}")
print(f"  Unseen   : {unseen.shape}")

# ─────────────────────────────────────────────
# 2. MERGE
# ─────────────────────────────────────────────
print("\nMerging Internal + External on PROSPECTID...")
merged = pd.merge(internal, external, on="PROSPECTID", how="inner")
print(f"  Merged   : {merged.shape}")

# ─────────────────────────────────────────────
# 3. FEATURE SELECTION
# Use only the 42 features present in Unseen
# so the model can predict on new users
# ─────────────────────────────────────────────
FEATURES = list(unseen.columns)   # 42 features
TARGET   = "Credit_Score"

X = merged[FEATURES].copy()
y = merged[TARGET].copy()

print(f"\nTraining features : {len(FEATURES)}")
print(f"Target range      : {y.min():.0f} – {y.max():.0f}")

# ─────────────────────────────────────────────
# 4. PREPROCESSING
# ─────────────────────────────────────────────
# Replace -99999 sentinel (missing) → NaN
X.replace(-99999, np.nan, inplace=True)

# Encode categoricals
cat_cols = X.select_dtypes(include="object").columns.tolist()
encoders = {}
for col in cat_cols:
    le = LabelEncoder()
    X[col] = X[col].fillna("Unknown")
    X[col] = le.fit_transform(X[col].astype(str))
    encoders[col] = le
print(f"Categorical cols  : {cat_cols}")

# Fill remaining NaN with column medians
num_cols = X.select_dtypes(include="number").columns.tolist()
medians  = X[num_cols].median()
X[num_cols] = X[num_cols].fillna(medians)

# ─────────────────────────────────────────────
# 5. TRAIN / TEST SPLIT
# ─────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"\nTrain rows : {len(X_train):,}")
print(f"Test rows  : {len(X_test):,}")

# ─────────────────────────────────────────────
# 6. TRAIN LIGHTGBM
# (same library already used in Stock API)
# ─────────────────────────────────────────────
print("\nTraining LightGBM model...")
model = lgb.LGBMRegressor(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    num_leaves=63,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    verbose=-1
)
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
)

# ─────────────────────────────────────────────
# 7. EVALUATE
# ─────────────────────────────────────────────
preds = model.predict(X_test)
mae   = mean_absolute_error(y_test, preds)
r2    = r2_score(y_test, preds)

print(f"\n{'='*40}")
print(f"  MAE (Mean Abs Error) : {mae:.2f} points")
print(f"  R² Score             : {r2:.4f}  ({r2*100:.1f}% variance explained)")
print(f"{'='*40}")

# Feature importances
importance = pd.Series(
    model.feature_importances_, index=FEATURES
).sort_values(ascending=False)
print("\nTop 10 most important features:")
for feat, imp in importance.head(10).items():
    print(f"  {feat:<35} {imp}")

# ─────────────────────────────────────────────
# 8. VALIDATE ON UNSEEN DATA
# ─────────────────────────────────────────────
print("\nRunning on Unseen_Dataset (100 new users)...")
unseen_X = unseen[FEATURES].copy()
unseen_X.replace(-99999, np.nan, inplace=True)
for col in cat_cols:
    unseen_X[col] = unseen_X[col].fillna("Unknown")
    le = encoders[col]
    unseen_X[col] = unseen_X[col].apply(
        lambda x: le.transform([x])[0] if x in le.classes_ else -1
    )
unseen_X[num_cols] = unseen_X[num_cols].fillna(medians)

unseen_preds = np.clip(model.predict(unseen_X), 300, 900).astype(int)
print(f"  Predictions (first 10) : {unseen_preds[:10].tolist()}")
print(f"  Average predicted score: {unseen_preds.mean():.1f}")

# ─────────────────────────────────────────────
# 9. SAVE ARTIFACTS
# ─────────────────────────────────────────────
joblib.dump(model,               "cibil_model.pkl")
joblib.dump(medians.to_dict(),   "cibil_medians.pkl")
joblib.dump(FEATURES,            "cibil_features.pkl")
joblib.dump(encoders,            "cibil_encoders.pkl")
joblib.dump(cat_cols,            "cibil_cat_cols.pkl")

print("\n✅ All artifacts saved:")
print("   cibil_model.pkl")
print("   cibil_medians.pkl")
print("   cibil_features.pkl")
print("   cibil_encoders.pkl")
print("   cibil_cat_cols.pkl")
print("\nNext step: copy these .pkl files next to your Flask server.")