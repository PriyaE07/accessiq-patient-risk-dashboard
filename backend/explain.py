"""
Per-patient prediction explanations via SHAP.

This is deliberately separate from the training-time permutation importance
we computed in the notebooks — that was *global* importance (which features
matter across the whole dataset). SHAP gives *per-prediction* importance:
for this one specific patient, which of their values pushed the risk score
up or down, and by how much. That's what lets the chatbot explain an
individual prediction instead of reciting the same generic fact for everyone.
"""

import shap


def explain_prediction(model, X_aligned, top_n: int = 5) -> list[dict]:
    """Return the top contributing factors for a single aligned prediction row.

    Args:
        model: a trained tree-based model (HistGradientBoostingClassifier here)
        X_aligned: a one-row, already-aligned DataFrame (same shape the model
            was trained on — i.e. the output of align_features())
        top_n: how many top factors to return, ranked by absolute contribution

    Returns a list of dicts, largest absolute contribution first:
        {"feature": str, "value": the patient's actual value for that column,
         "contribution": float (SHAP value; sign indicates direction),
         "direction": "increases risk" | "decreases risk"}
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_aligned)[0]  # single row -> 1D array

    contributions = list(zip(X_aligned.columns, X_aligned.iloc[0].values, shap_values))
    contributions.sort(key=lambda item: abs(item[2]), reverse=True)

    return [
        {
            "feature": name,
            "value": value.item() if hasattr(value, "item") else value,
            "contribution": float(contribution),
            "direction": "increases risk" if contribution > 0 else "decreases risk",
        }
        for name, value, contribution in contributions[:top_n]
    ]
