"""
Cleaning and feature-engineering logic for the readmission dataset.

This mirrors the decisions made during EDA in notebooks/02_readmission_eda.ipynb —
kept here as a shared, importable module so both the training script and any
future serving code (e.g. the FastAPI backend) apply the exact same
transformations to raw data.
"""

import pandas as pd

# discharge_disposition_id codes meaning the patient expired or entered
# hospice — readmission is not a meaningful outcome for these, so rows with
# these codes are dropped entirely rather than recoded.
EXPIRED_CODES = [11, 13, 14, 19, 20, 21]

# Numeric codes that stand in for "missing"/"unknown" in three ID columns
# (NULL, Not Mapped, Unknown/Invalid, Not Available) — consolidated into a
# single "Unknown" category per column rather than dropped, since the
# readmission outcome is still valid for these rows.
UNKNOWN_LIKE_CODES_BY_COL = {
    "discharge_disposition_id": [18, 25, 26],
    "admission_type_id": [5, 6, 8],
    "admission_source_id": [9, 15, 17, 20, 21],
}

RARE_SPECIALTY_THRESHOLD = 500


def map_icd9_to_category(code) -> str:
    """Map a raw ICD-9 diagnosis code to one of 9 broad clinical chapters.

    Follows the standard grouping used in the original research behind this
    dataset. V/E-prefixed codes (supplementary classification, not numeric
    diagnoses) and anything unrecognized fall into 'Other'; missing codes
    become 'Missing'.
    """
    if pd.isna(code):
        return "Missing"
    code = str(code)
    if code.startswith("V") or code.startswith("E"):
        return "Other"
    try:
        code_num = float(code)
    except ValueError:
        return "Other"

    if 390 <= code_num <= 459 or code_num == 785:
        return "Circulatory"
    elif 460 <= code_num <= 519 or code_num == 786:
        return "Respiratory"
    elif 520 <= code_num <= 579 or code_num == 787:
        return "Digestive"
    elif 250 <= code_num < 251:
        return "Diabetes"
    elif 800 <= code_num <= 999:
        return "Injury"
    elif 710 <= code_num <= 739:
        return "Musculoskeletal"
    elif 580 <= code_num <= 629 or code_num == 788:
        return "Genitourinary"
    elif 140 <= code_num <= 239:
        return "Neoplasms"
    else:
        return "Other"


def clean_readmission_data(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the EDA-driven cleaning decisions to a raw readmission dataframe.

    Steps (see notebooks/02_readmission_eda.ipynb for the reasoning behind each):
      1. Engineer readmit_30_flag (target) and tested-flags for lab columns
      2. Drop rows with expired/hospice discharge codes
      3. Consolidate unknown-like codes into "Unknown" across 3 ID columns
      4. Drop weight (96.9% missing)
      5. Fill max_glu_serum/A1Cresult missing values with "Not_Tested"
      6. Drop examide/citoglipton (zero variance)
      7. Fill race/medical_specialty/payer_code missing values with "Unknown"
      8. Drop rows with invalid gender
      9. Group diag_1/2/3 into ICD-9 chapter categories
      10. Group rare medical_specialty categories (<500 occurrences) into "Other"

    Note: expects raw data already loaded with na_values=["?"] (see train.py).
    """
    df = df.copy()

    df["readmit_30_flag"] = (df["readmitted"] == "<30").astype(int)

    df = df[~df["discharge_disposition_id"].isin(EXPIRED_CODES)]

    for col, codes in UNKNOWN_LIKE_CODES_BY_COL.items():
        df[col] = df[col].replace(codes, "Unknown")

    df = df.drop(columns=["weight"])

    df["max_glu_serum"] = df["max_glu_serum"].fillna("Not_Tested")
    df["A1Cresult"] = df["A1Cresult"].fillna("Not_Tested")

    df = df.drop(columns=["examide", "citoglipton"])

    for col in ["race", "medical_specialty", "payer_code"]:
        df[col] = df[col].fillna("Unknown")

    df = df[df["gender"] != "Unknown/Invalid"]

    for col in ["diag_1", "diag_2", "diag_3"]:
        df[col + "_cat"] = df[col].apply(map_icd9_to_category)
    df = df.drop(columns=["diag_1", "diag_2", "diag_3"])

    spec_counts = df["medical_specialty"].value_counts()
    rare_specs = spec_counts[spec_counts < RARE_SPECIALTY_THRESHOLD].index
    df["medical_specialty"] = df["medical_specialty"].apply(
        lambda x: "Other" if x in rare_specs else x
    )

    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split a cleaned dataframe into model-ready features (X) and target (y).

    Drops identifiers, the original 3-value target text column (readmitted —
    this literally contains the answer, not just something correlated with
    it), then one-hot encodes the remaining categorical columns.
    """
    X = df.drop(
        columns=["encounter_id", "patient_nbr", "readmitted", "readmit_30_flag"]
    )
    y = df["readmit_30_flag"]
    X_encoded = pd.get_dummies(X, drop_first=True)
    return X_encoded, y


def align_features(X: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Reindex a one-hot encoded dataframe to match the training column set.

    Needed at serving time: encoding a single new patient (or a small batch)
    won't naturally reproduce every column the model was trained on. This
    fills any missing columns with 0 and drops/reorders to match exactly
    what the model expects.
    """
    return X.reindex(columns=feature_columns, fill_value=0)
