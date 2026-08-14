"""
Cleaning and feature-engineering logic for the no-show dataset.

This mirrors the decisions made during EDA in notebooks/01_no_show_eda.ipynb —
kept here as a shared, importable module so both the training script and any
future serving code (e.g. the FastAPI backend) apply the exact same
transformations to raw data.
"""

import pandas as pd


def clean_no_show_data(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the EDA-driven cleaning decisions to a raw no-show dataframe.

    Steps (see notebooks/01_no_show_eda.ipynb for the reasoning behind each):
      1. Engineer wait_days (AppointmentDay - ScheduledDay) and no_show_flag (target)
      2. Drop rows with negative wait_days or Age == -1 (data errors)
      3. Drop SMS_received (leaks post-booking information)
      4. Collapse Handcap to binary (has any handicap vs none)
      5. Group neighborhoods with < 500 appointments into "Other"
    """
    df = df.copy()

    df["ScheduledDay"] = pd.to_datetime(df["ScheduledDay"])
    df["AppointmentDay"] = pd.to_datetime(df["AppointmentDay"])
    df["wait_days"] = (
        (df["AppointmentDay"].dt.date - df["ScheduledDay"].dt.date)
        .apply(lambda d: d.days)
    )
    df["no_show_flag"] = (df["No-show"] == "Yes").astype(int)

    df = df[(df["wait_days"] >= 0) & (df["Age"] != -1)]

    df = df.drop(columns=["SMS_received"])

    df["Handcap"] = (df["Handcap"] > 0).astype(int)

    neigh_counts = df["Neighbourhood"].value_counts()
    rare_neighs = neigh_counts[neigh_counts < 500].index
    df["Neighbourhood"] = df["Neighbourhood"].apply(
        lambda x: "Other" if x in rare_neighs else x
    )

    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split a cleaned dataframe into model-ready features (X) and target (y).

    Drops identifiers, raw date columns, and the original text target,
    then one-hot encodes the remaining categorical columns.
    """
    X = df.drop(
        columns=[
            "PatientId",
            "AppointmentID",
            "ScheduledDay",
            "AppointmentDay",
            "No-show",
            "no_show_flag",
        ]
    )
    y = df["no_show_flag"]
    X_encoded = pd.get_dummies(X, drop_first=True)
    return X_encoded, y


def align_features(X: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Reindex a one-hot encoded dataframe to match the training column set.

    Needed at serving time: encoding a single new patient (or a small batch)
    won't naturally reproduce every column the model was trained on (e.g. most
    neighborhood dummy columns will be absent). This fills any missing columns
    with 0 and drops/reorders to match exactly what the model expects.
    """
    return X.reindex(columns=feature_columns, fill_value=0)
