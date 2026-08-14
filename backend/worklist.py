"""
Builds an in-memory patient worklist: a sample of real, held-out patients
with model-scored risk, for the "who should I be worried about right now"
table view — as opposed to the single-patient forms, which only answer
"what's the risk for this one patient."

"Held-out" here means genuinely unseen by the model during training: we
recompute the exact same train/test split train.py used (same random_state,
same test_size), so the test portion is provably the same rows that were
never used to fit the model — nothing new to persist, since the split is
fully deterministic.
"""

from dataclasses import dataclass

import pandas as pd
from sklearn.model_selection import train_test_split

from explain import explain_prediction


@dataclass
class WorklistSource:
    """The cached held-out set for one model, built once at startup.

    Two model objects, not one -- see plan.md's calibration fix notes:
    `score_model` (the calibrated model) produces the risk_score/threshold
    decision actually shown to users; `explain_model` (the raw, uncalibrated
    base model) is what SHAP explains, since CalibratedClassifierCV wraps
    the base model in a structure shap.TreeExplainer can't run on directly,
    and calibration only rescales the final number -- it doesn't change
    which features drove the prediction, so explaining off the raw model
    stays accurate.
    """

    readable_df: pd.DataFrame  # human-readable columns, for display
    X_test: pd.DataFrame  # one-hot encoded, aligned — ready for predict_proba
    score_model: object  # calibrated -- used for predict_proba / threshold
    explain_model: object  # raw -- used for SHAP
    threshold: float


def build_worklist_source(
    raw_df, clean_fn, build_features_fn, score_model, explain_model, threshold
) -> WorklistSource:
    """Reproduce the held-out test split and pair it with readable columns.

    clean_fn/build_features_fn are the same clean_*_data / build_features
    functions from each model's preprocess.py — reused here so the worklist
    is cleaned/encoded identically to how the model was actually trained.
    """
    df_clean = clean_fn(raw_df)
    X, y = build_features_fn(df_clean)

    # Same split call as train.py — reproduces the identical held-out rows.
    _, X_test, _, _ = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    # X_test's index still lines up with df_clean's index, so we can look up
    # the readable (pre-encoding) version of each held-out row directly.
    readable_df = df_clean.loc[X_test.index]

    return WorklistSource(
        readable_df=readable_df,
        X_test=X_test,
        score_model=score_model,
        explain_model=explain_model,
        threshold=threshold,
    )


def sample_worklist(source: WorklistSource, n: int, display_columns: list[str]) -> list[dict]:
    """Sample n held-out patients, score them, and return display-ready rows."""
    sample_index = source.X_test.sample(n=min(n, len(source.X_test)), random_state=None).index

    X_sample = source.X_test.loc[sample_index]
    readable_sample = source.readable_df.loc[sample_index]

    risk_scores = source.score_model.predict_proba(X_sample)[:, 1]

    rows = []
    for (idx, readable_row), risk_score in zip(readable_sample.iterrows(), risk_scores):
        row = {col: readable_row[col] for col in display_columns if col in readable_row}
        row["risk_score"] = float(risk_score)
        row["flagged_high_risk"] = bool(risk_score >= source.threshold)
        # One-row DataFrame, same shape explain_prediction expects (it's the
        # same function the single-patient endpoints use for their chat).
        # Explains off the raw model -- see WorklistSource's docstring.
        row["top_factors"] = explain_prediction(source.explain_model, X_sample.loc[[idx]])
        rows.append(row)

    # Highest risk first — this is a triage list, not a raw dump.
    rows.sort(key=lambda r: r["risk_score"], reverse=True)
    return rows


def summarize_worklist(source: WorklistSource, sample_size: int = 300) -> dict:
    """Aggregate stats over a larger sample of the held-out set: how many
    patients are flagged, the average risk, how they spread across the same
    Low/Moderate/High bands RiskMeter uses, and which factors show up most
    often as a top driver.

    Uses a bigger sample than the row-level worklist (which shows ~20 at a
    time) since aggregate stats are more stable with more data — but still
    capped well below the full held-out set, since SHAP explanation is one
    explainer call per patient and gets slow at full scale.
    """
    sample_index = source.X_test.sample(
        n=min(sample_size, len(source.X_test)), random_state=42
    ).index
    X_sample = source.X_test.loc[sample_index]
    risk_scores = source.score_model.predict_proba(X_sample)[:, 1]

    # Same band logic as RiskMeter.jsx's getStatus(): below half the
    # threshold is "good," below the threshold is "warning," at/above is
    # "critical" (flagged).
    threshold = source.threshold
    band_counts = {"low": 0, "moderate": 0, "high": 0}
    for score in risk_scores:
        if score < threshold / 2:
            band_counts["low"] += 1
        elif score < threshold:
            band_counts["moderate"] += 1
        else:
            band_counts["high"] += 1

    # Tally how often each feature shows up as one of a patient's top-3
    # SHAP drivers, across the whole sample — an aggregate answer to
    # "what's actually driving risk right now," not just for one patient.
    factor_totals: dict[str, list] = {}  # feature -> [times_seen, sum_abs_contribution]
    for idx in sample_index:
        for factor in explain_prediction(source.explain_model, X_sample.loc[[idx]], top_n=3):
            name = factor["feature"]
            count, total_abs = factor_totals.get(name, [0, 0.0])
            factor_totals[name] = [count + 1, total_abs + abs(factor["contribution"])]

    top_factors_overall = sorted(
        (
            {
                "feature": name,
                "times_top_factor": count,
                "pct_of_sample": round(100 * count / len(sample_index), 1),
                "avg_contribution": round(total_abs / count, 4),
            }
            for name, (count, total_abs) in factor_totals.items()
        ),
        key=lambda f: f["times_top_factor"],
        reverse=True,
    )[:8]

    flagged_count = int((risk_scores >= threshold).sum())

    return {
        "sample_size": len(sample_index),
        "flagged_count": flagged_count,
        "flagged_pct": round(100 * flagged_count / len(sample_index), 1),
        "avg_risk": round(float(risk_scores.mean()), 4),
        "band_counts": band_counts,
        "top_factors": top_factors_overall,
    }
