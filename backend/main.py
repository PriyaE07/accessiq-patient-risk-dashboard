import importlib.util
import os
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai.types import HttpOptions
from pydantic import BaseModel

from alerts_db import create_alert, init_db, list_alerts, update_alert_status
from explain import explain_prediction
from worklist import build_worklist_source, sample_worklist, summarize_worklist

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent

# Loads GEMINI_API_KEY from backend/.env (gitignored) into the environment.
# The genai.Client() call below picks it up automatically from there.
load_dotenv(THIS_DIR / ".env")
# Explicit timeout -- without one, the underlying HTTP client has no upper
# bound, so a network hiccup between the host and Google's API (seen on
# Render: some cloud providers have flaky outbound routing that causes a
# TCP connection to hang instead of failing fast) blocks the request
# forever instead of erroring out in a few seconds.
gemini_client = genai.Client(http_options=HttpOptions(timeout=20000))
GEMINI_MODEL = "gemini-3.6-flash"


def load_module(name: str, file_path: Path):
    """Load a .py file as a module under an explicit, unique name.

    Both models/no_show/preprocess.py and models/readmission/preprocess.py
    share the filename "preprocess" — a plain `import preprocess` after
    adding both folders to sys.path would silently reuse whichever one
    Python imported first for both, since Python caches modules by name,
    not file path. Loading each one explicitly by path with a distinct
    name (e.g. "no_show_preprocess") avoids that collision entirely.
    """
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


no_show_preprocess = load_module(
    "no_show_preprocess", PROJECT_ROOT / "models" / "no_show" / "preprocess.py"
)
readmission_preprocess = load_module(
    "readmission_preprocess", PROJECT_ROOT / "models" / "readmission" / "preprocess.py"
)

# Two model objects per prediction type, not one -- see plan.md's
# calibration fix notes. `*_raw_model` is the original uncalibrated model,
# used only for SHAP explanations (shap.TreeExplainer can't run on a
# CalibratedClassifierCV-wrapped model, and calibration doesn't change
# *why* a prediction was made, only rescales the final number). The
# calibrated model is what actually produces the risk score shown to users
# and compared against the threshold.
NO_SHOW_MODEL_DIR = PROJECT_ROOT / "models" / "no_show"
no_show_raw_model = joblib.load(NO_SHOW_MODEL_DIR / "gradient_boosting_v1.joblib")
no_show_model = joblib.load(NO_SHOW_MODEL_DIR / "calibrated_v1.joblib")
no_show_feature_columns = joblib.load(NO_SHOW_MODEL_DIR / "feature_columns.joblib")
# Re-derived 2026-08-14 against the calibrated model's score scale -- NOT
# comparable to the old raw-scale 0.4. See plan.md "Calibration fix" for
# the full reasoning (capped cost-based threshold).
NO_SHOW_THRESHOLD = 0.20

READMISSION_MODEL_DIR = PROJECT_ROOT / "models" / "readmission"
readmission_raw_model = joblib.load(READMISSION_MODEL_DIR / "gradient_boosting_v1.joblib")
readmission_model = joblib.load(READMISSION_MODEL_DIR / "calibrated_v1.joblib")
readmission_feature_columns = joblib.load(READMISSION_MODEL_DIR / "feature_columns.joblib")
# Re-derived 2026-08-14 against the calibrated model's score scale -- NOT
# comparable to the old raw-scale 0.6. See plan.md "Calibration fix" for
# the full reasoning (capacity-based threshold: top ~10% riskiest patients).
READMISSION_THRESHOLD = 0.20

# Built once at startup: reconstructs each model's held-out test split and
# caches it in memory, so worklist requests just sample + predict — no
# re-cleaning the raw CSVs on every call.
no_show_worklist_source = build_worklist_source(
    raw_df=pd.read_csv(PROJECT_ROOT / "data" / "raw" / "KaggleV2-May-2016.csv"),
    clean_fn=no_show_preprocess.clean_no_show_data,
    build_features_fn=no_show_preprocess.build_features,
    score_model=no_show_model,
    explain_model=no_show_raw_model,
    threshold=NO_SHOW_THRESHOLD,
)
NO_SHOW_DISPLAY_COLUMNS = ["AppointmentID", "Age", "Gender", "Neighbourhood", "wait_days", "Scholarship", "Hipertension", "Diabetes"]

readmission_worklist_source = build_worklist_source(
    raw_df=pd.read_csv(PROJECT_ROOT / "data" / "raw" / "diabetic_data.csv", na_values=["?"]),
    clean_fn=readmission_preprocess.clean_readmission_data,
    build_features_fn=readmission_preprocess.build_features,
    score_model=readmission_model,
    explain_model=readmission_raw_model,
    threshold=READMISSION_THRESHOLD,
)
READMISSION_DISPLAY_COLUMNS = [
    "encounter_id", "age", "gender", "race", "time_in_hospital", "number_inpatient", "number_diagnoses", "diag_1_cat",
]

init_db()

app = FastAPI()

# Allow the React dev server (running on a different port, so a different
# "origin") to actually call this API from the browser. Without this,
# fetch() requests from the frontend would be silently blocked by the
# browser's CORS policy, even though curl/backend-to-backend calls work fine.
#
# ALLOWED_ORIGINS lets the deployed frontend's real domain be added without
# another code change -- set it as a comma-separated env var in the hosting
# platform's dashboard (e.g. "https://accessiq-dashboard.netlify.app"). Not
# set locally, so local dev keeps working against localhost:5173 unchanged.
_extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = ["http://localhost:5173"] + [
    origin.strip() for origin in _extra_origins.split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoShowPatientData(BaseModel):
    Gender: str
    Age: int
    Neighbourhood: str
    Scholarship: int
    Hipertension: int
    Diabetes: int
    Alcoholism: int
    Handcap: int
    wait_days: int


class ReadmissionPatientData(BaseModel):
    race: str
    gender: str
    age: str
    admission_type_id: str
    discharge_disposition_id: str
    admission_source_id: str
    time_in_hospital: int
    payer_code: str
    medical_specialty: str
    num_lab_procedures: int
    num_procedures: int
    num_medications: int
    number_outpatient: int
    number_emergency: int
    number_inpatient: int
    number_diagnoses: int
    max_glu_serum: str
    A1Cresult: str
    metformin: str
    repaglinide: str
    nateglinide: str
    chlorpropamide: str
    glimepiride: str
    acetohexamide: str
    glipizide: str
    glyburide: str
    tolbutamide: str
    pioglitazone: str
    rosiglitazone: str
    acarbose: str
    miglitol: str
    troglitazone: str
    tolazamide: str
    insulin: str
    glyburide_metformin: str
    glipizide_metformin: str
    glimepiride_pioglitazone: str
    metformin_rosiglitazone: str
    metformin_pioglitazone: str
    change: str
    diabetesMed: str
    diag_1_cat: str
    diag_2_cat: str
    diag_3_cat: str


# The original dataset's medication combo columns use hyphens (e.g.
# "glyburide-metformin"), which aren't valid Python identifiers and so can't
# be Pydantic field names directly. Clients send these with underscores
# instead (e.g. "glyburide_metformin"); this maps them back to the real
# hyphenated column names the model was trained on before building the
# dataframe.
READMISSION_HYPHEN_FIELDS = {
    "glyburide_metformin": "glyburide-metformin",
    "glipizide_metformin": "glipizide-metformin",
    "glimepiride_pioglitazone": "glimepiride-pioglitazone",
    "metformin_rosiglitazone": "metformin-rosiglitazone",
    "metformin_pioglitazone": "metformin-pioglitazone",
}


@app.get("/")
def home():
    return {"message": "AccessIQ backend is running"}


@app.post("/predict/no-show")
def predict_no_show(patient: NoShowPatientData):
    input_df = pd.DataFrame([patient.model_dump()])
    input_encoded = pd.get_dummies(input_df)
    input_aligned = no_show_preprocess.align_features(input_encoded, no_show_feature_columns)

    risk_score = no_show_model.predict_proba(input_aligned)[:, 1][0]
    will_no_show = risk_score >= NO_SHOW_THRESHOLD
    # Explains off the raw model, not the calibrated one -- see the model
    # loading comment above for why.
    top_factors = explain_prediction(no_show_raw_model, input_aligned)

    # Only flagged predictions get persisted -- a genuine decision point for
    # staff to follow up on, not every prediction made.
    if will_no_show:
        create_alert("no-show", float(risk_score), top_factors, patient.model_dump())

    return {
        "no_show_risk": float(risk_score),
        "flagged_high_risk": bool(will_no_show),
        "top_factors": top_factors,
    }


@app.post("/predict/readmission")
def predict_readmission(patient: ReadmissionPatientData):
    input_dict = patient.model_dump()
    # Rename the underscore-safe field names back to the model's actual
    # hyphenated column names before building the dataframe.
    for safe_name, real_name in READMISSION_HYPHEN_FIELDS.items():
        input_dict[real_name] = input_dict.pop(safe_name)

    input_df = pd.DataFrame([input_dict])
    input_encoded = pd.get_dummies(input_df)
    input_aligned = readmission_preprocess.align_features(input_encoded, readmission_feature_columns)

    risk_score = readmission_model.predict_proba(input_aligned)[:, 1][0]
    will_readmit = risk_score >= READMISSION_THRESHOLD
    # Explains off the raw model, not the calibrated one -- see the model
    # loading comment above for why.
    top_factors = explain_prediction(readmission_raw_model, input_aligned)

    if will_readmit:
        create_alert("readmission", float(risk_score), top_factors, patient.model_dump())

    return {
        "readmission_risk": float(risk_score),
        "flagged_high_risk": bool(will_readmit),
        "top_factors": top_factors,
    }


class ChatRequest(BaseModel):
    prediction_type: str  # "no-show" or "readmission"
    risk_score: float
    top_factors: list[dict]
    message: str
    # Set on follow-up turns to the interaction_id returned from the previous
    # /explain-chat response — lets Gemini's Interactions API chain the
    # conversation server-side instead of us resending full history.
    previous_interaction_id: Optional[str] = None


PREDICTION_THRESHOLDS = {"no-show": NO_SHOW_THRESHOLD, "readmission": READMISSION_THRESHOLD}


def get_risk_band(prediction_type: str, risk_score: float) -> str:
    """Same band logic as RiskMeter.jsx's getStatus() — kept in sync so the
    chat never describes a risk level that contradicts what's on screen."""
    threshold = PREDICTION_THRESHOLDS[prediction_type]
    if risk_score < threshold / 2:
        return "Low risk"
    if risk_score < threshold:
        return "Moderate risk"
    return "High risk"


def build_system_instruction(prediction_type: str, risk_score: float, top_factors: list[dict]) -> str:
    """Build the grounding context for the explanation chat.

    This is direct context injection, not RAG (see plan.md / progress log for
    why): the grounding data is a small, complete, already-computed set of
    values from this one prediction — nothing to retrieve, just hand it over
    and instruct the model to stick to it.
    """
    factor_lines = "\n".join(
        f"- {f['feature']} = {f['value']} ({f['direction']}, contribution {f['contribution']:.3f})"
        for f in top_factors
    )
    outcome = "no-show" if prediction_type == "no-show" else "30-day readmission"
    risk_band = get_risk_band(prediction_type, risk_score)
    return (
        f"You are explaining a patient {outcome} risk prediction to hospital staff "
        f"(a scheduler or care coordinator), not a data scientist. Be clear, warm, and concise, "
        f"as if speaking to a colleague — not reading off a spreadsheet.\n\n"
        f"Overall risk level: {risk_band}\n"
        f"This dashboard deliberately does not use an exact risk percentage — the model's "
        f"underlying probabilities are still being calibrated, so only the risk band above "
        f"({risk_band}) is considered reliable right now. Never state or imply a specific "
        f"percentage chance yourself, even if asked directly — if asked for an exact number, "
        f"explain plainly that this dashboard only reports a risk level (Low/Moderate/High), "
        f"not a precise percentage, because the underlying model isn't calibrated to support "
        f"that level of precision yet.\n\n"
        f"Top contributing factors for this specific patient, from the model's SHAP explanation:\n"
        f"{factor_lines}\n\n"
        f"These raw factor names come straight from the underlying dataset's column names, so "
        f"translate them into plain English — never quote a raw variable name, an underscore, "
        f"an '=' sign, or the word 'contribution' in your reply. A few translation notes:\n"
        f"- A feature like 'Neighbourhood_X' being true means the patient lives in neighborhood X; "
        f"false means they live somewhere else (don't name every neighborhood they don't live in — "
        f"just say their neighborhood is a modest factor, if it's not a major one).\n"
        f"- A feature like 'Gender_M' being 0 means the patient is female; 1 means male.\n"
        f"- 'wait_days' means the number of days between booking and the appointment.\n"
        f"- Numeric fields (Age, number_inpatient, time_in_hospital, etc.) can be stated directly, "
        f"just in a normal sentence, not as 'field = value'.\n\n"
        f"Only reference the factors listed above — do not invent other explanations or "
        f"speculate about factors not listed. If asked something the factors above can't "
        f"answer, say so plainly rather than guessing."
    )


@app.post("/explain-chat")
def explain_chat(chat: ChatRequest):
    system_instruction = build_system_instruction(
        chat.prediction_type, chat.risk_score, chat.top_factors
    )

    try:
        interaction = gemini_client.interactions.create(
            model=GEMINI_MODEL,
            system_instruction=system_instruction,
            input=chat.message,
            previous_interaction_id=chat.previous_interaction_id,
        )
    except Exception as exc:
        # Surface a clean 502 instead of letting an unhandled exception (or,
        # before the client timeout was added, an indefinite hang) reach the
        # user as a bare "Load failed" with no explanation.
        raise HTTPException(
            status_code=502, detail=f"The chat service didn't respond in time: {exc}"
        )

    return {
        "reply": interaction.output_text,
        "interaction_id": interaction.id,
    }


@app.get("/worklist/no-show")
def worklist_no_show(n: int = 20):
    return sample_worklist(no_show_worklist_source, n, NO_SHOW_DISPLAY_COLUMNS)


@app.get("/worklist/readmission")
def worklist_readmission(n: int = 20):
    return sample_worklist(readmission_worklist_source, n, READMISSION_DISPLAY_COLUMNS)


@app.get("/summary/no-show")
def summary_no_show(n: int = 300):
    return summarize_worklist(no_show_worklist_source, sample_size=n)


@app.get("/summary/readmission")
def summary_readmission(n: int = 300):
    return summarize_worklist(readmission_worklist_source, sample_size=n)


class AlertStatusUpdate(BaseModel):
    status: str  # "new" | "acknowledged" | "resolved"


@app.get("/alerts")
def get_alerts(status: Optional[str] = None):
    return list_alerts(status=status)


@app.patch("/alerts/{alert_id}")
def patch_alert(alert_id: int, update: AlertStatusUpdate):
    updated = update_alert_status(alert_id, update.status)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No alert with id {alert_id}")
    return updated
