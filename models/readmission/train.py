"""
Train the readmission gradient boosting model end-to-end from raw data.

Usage:
    python train.py

Reproduces the same pipeline built interactively in
notebooks/02_readmission_eda.ipynb and notebooks/04_readmission_baseline_model.ipynb,
as a single reusable, rerunnable script.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

from preprocess import build_features, clean_readmission_data

# Paths are relative to this file, so the script works regardless of the
# directory it's run from.
THIS_DIR = Path(__file__).resolve().parent
RAW_DATA_PATH = THIS_DIR.parents[1] / "data" / "raw" / "diabetic_data.csv"
MODEL_PATH = THIS_DIR / "gradient_boosting_v1.joblib"
CALIBRATED_MODEL_PATH = THIS_DIR / "calibrated_v1.joblib"
FEATURE_COLUMNS_PATH = THIS_DIR / "feature_columns.joblib"

# Original threshold, tuned against the *raw* (uncalibrated) model's scores
# — see progress-log/2026-08-12.md. Kept only so the raw model's evaluation
# below stays comparable to that original reasoning; no longer used for any
# real decision (the calibrated model below uses DECISION_THRESHOLD instead).
RAW_REFERENCE_THRESHOLD = 0.6

# Superseded 2026-08-14 once the model was calibrated. A pure expected-value
# analysis (threshold = cost_of_outreach_call / cost_of_missed_readmission,
# roughly $50 / $10,000) also said to flag almost everyone (~0.005) -- but
# unlike an automated reminder, a care coordinator's outreach time is
# capacity-constrained, not free at any scale, so pure cost math isn't
# enough here. Instead picked a capacity-based cutoff: the threshold that
# flags roughly the top 10% riskiest patients (~1986 of the ~19868 held-out
# set) -- a realistic caseload for a small coordinator team. Landed on 0.20,
# which flags ~10.8% (recall 0.251, precision 0.265) on the calibrated
# held-out set -- see notebooks/05_calibration_check.ipynb /
# progress-log/2026-08-14.md for the full threshold sweep. This is
# calibrated-model-scale, NOT comparable to RAW_REFERENCE_THRESHOLD above.
DECISION_THRESHOLD = 0.20


def main():
    df_raw = pd.read_csv(RAW_DATA_PATH, na_values=["?"])
    df_clean = clean_readmission_data(df_raw)
    X, y = build_features(df_clean)

    # This split is untouched from before, and must stay that way: several
    # other places (backend/worklist.py, notebooks/05_calibration_check.ipynb)
    # reproduce this exact call with the same random_state to recover the
    # same held-out test rows. Changing this line would silently break that
    # reproducibility contract.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # Calibration has to be fit on data the base model didn't train on --
    # calibrating against the same rows the model memorized would just
    # measure how well it fit itself, not how honest its scores are on new
    # patients. So we carve a calibration set out of the training portion
    # only (X_test stays fully untouched, reserved for final evaluation).
    # Net split across the full dataset: 60% fit / 20% calibrate / 20% test.
    X_fit, X_calib, y_fit, y_calib = train_test_split(
        X_train, y_train, test_size=0.25, stratify=y_train, random_state=42
    )

    # The raw model -- this is what explain.py's SHAP explainer runs
    # against (see plan.md: calibration only rescales the final number, it
    # doesn't change which features drove the prediction, so explaining off
    # the raw model stays accurate). No feature scaling needed here --
    # HistGradientBoostingClassifier is tree-based and unaffected by
    # feature scale (unlike the logistic regression baseline explored in
    # the notebook).
    model = HistGradientBoostingClassifier(class_weight="balanced", random_state=42)
    model.fit(X_fit, y_fit)

    # FrozenEstimator tells CalibratedClassifierCV "don't refit this, it's
    # already trained -- just learn a calibration curve on top of it using
    # the data I give you." method="sigmoid" (Platt scaling) rather than
    # "isotonic": boosted-tree models are known to produce a specific
    # sigmoid-shaped overconfidence pattern (scores pushed toward the
    # extremes), which is exactly the shape sigmoid calibration is designed
    # to correct -- and it's less prone to overfitting than isotonic's more
    # flexible step function.
    calibrated_model = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
    calibrated_model.fit(X_calib, y_calib)

    print("=== Raw (uncalibrated) model, for reference only ===")
    raw_proba = model.predict_proba(X_test)[:, 1]
    raw_pred = (raw_proba >= RAW_REFERENCE_THRESHOLD).astype(int)
    print(f"Evaluation at threshold={RAW_REFERENCE_THRESHOLD} (raw scale):")
    print(classification_report(y_test, raw_pred))
    print("ROC-AUC:", roc_auc_score(y_test, raw_proba))

    print("\n=== Calibrated model -- this is the one actually used for decisions ===")
    calibrated_proba = calibrated_model.predict_proba(X_test)[:, 1]
    calibrated_pred = (calibrated_proba >= DECISION_THRESHOLD).astype(int)
    print(f"Evaluation at threshold={DECISION_THRESHOLD} (calibrated scale):")
    print(classification_report(y_test, calibrated_pred))
    print("ROC-AUC:", roc_auc_score(y_test, calibrated_proba))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(calibrated_model, CALIBRATED_MODEL_PATH)
    joblib.dump(list(X.columns), FEATURE_COLUMNS_PATH)
    print(f"\nSaved raw model to {MODEL_PATH}")
    print(f"Saved calibrated model to {CALIBRATED_MODEL_PATH}")
    print(f"Saved feature column list to {FEATURE_COLUMNS_PATH}")


if __name__ == "__main__":
    main()
