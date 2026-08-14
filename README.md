# AccessIQ — Patient Risk Dashboard

A predictive dashboard for two hospital operations problems, built to flag risk *before* the event happens rather than analyze it afterward:

1. **No-show risk** — will a patient miss their appointment? Flagged at the moment of booking.
2. **30-day readmission risk** — will a discharged patient return within 30 days? Flagged at the moment of discharge.

**Live app**: https://accessiq0814.netlify.app
**API**: https://accessiq-backend-ur89.onrender.com

> Free-tier hosting note: the backend spins down after 15 minutes of inactivity and takes ~30–60s to wake on the next visit. The Alerts feature's SQLite storage resets on restart (Render's free tier has no persistent disk) — expected on this tier, not a bug.

---

## Why two separate models, one dashboard

No-shows and readmissions are both "a patient risk, predicted early, that a staff member acts on" — similar enough in shape to share one dashboard's UI patterns, but they're solved with two independent public datasets, no shared patient IDs:

- **No-show**: [Kaggle "Medical Appointment No Shows"](https://www.kaggle.com/datasets/joniarroba/noshowappointments) — ~110k Brazilian outpatient appointments (2016)
- **Readmission**: [UCI "Diabetes 130-US Hospitals"](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008) — ~100k US inpatient encounters (1999–2008)

The one constraint that shaped every feature decision in both models: **no data leakage**. Every feature had to be genuinely known *before* the predicted event — nothing recorded after booking (no-show) or after discharge (readmission) was allowed in, even when it correlated strongly with the outcome.

## Architecture

```
Raw CSVs → EDA (notebooks) → cleaning/feature engineering → trained models (joblib)
                                                                    ↓
                                          FastAPI backend (predict, explain, worklist, alerts)
                                                                    ↓
                                          React dashboard (forms, worklist, overview, alerts)
```

- **Modeling**: Python, pandas, scikit-learn. Baseline logistic regression → `HistGradientBoostingClassifier`, both with `class_weight='balanced'` for the class imbalance (no-show ~80/20, readmission ~89/11). Wrapped with `CalibratedClassifierCV` (sigmoid/Platt scaling) so the risk score is an honest probability, not just a good ranking signal — see [Calibration](#calibration-why-and-how) below.
- **Explainability**: `shap.TreeExplainer` computes per-patient feature attributions at prediction time (on the raw, uncalibrated model — calibration only rescales the final number, it doesn't change which features drove the prediction). A Gemini-powered chatbot (`google-genai`, Interactions API) explains predictions in plain language, grounded directly in the SHAP output via direct context injection — not RAG, since the grounding data is a small, complete, already-computed set of values for one prediction, not a corpus to retrieve from.
- **Backend**: FastAPI. Two prediction endpoints, a chat endpoint, worklist/overview endpoints (batch-scored patients from a reproducible held-out test split), and an Alerts CRUD backed by SQLite.
- **Frontend**: React (Vite), no UI framework — a hand-built design system (CSS custom properties, light/dark theming, a validated categorical/status color palette).

## Features

| Page | What it does |
|---|---|
| **Overview** | Aggregate stats across both models — flagged count, average risk, risk-band distribution, most frequent SHAP factors across a 300-patient sample |
| **No-Show / Readmission Risk** | Single-patient prediction forms. Risk band + recommended action + a chatbot for follow-up questions ("why is this patient high risk?") |
| **Worklists** | Real held-out patients (never seen during training), batch-scored and ranked by risk — sortable, filterable, click a row for full detail (reuses the same risk meter + chatbot as the forms) |
| **Alerts** | Every flagged prediction from the single-patient forms is saved (worklist samples aren't — they're re-drawn demo data, not real decision points). Acknowledge → Resolve workflow |

## Model performance

| | No-show | Readmission |
|---|---|---|
| ROC-AUC | 0.726 | 0.672 |
| Top driver (SHAP / permutation importance) | `wait_days` (days between booking and appointment) | `number_inpatient` (prior inpatient visits) |
| Decision threshold (calibrated scale) | 0.20 | 0.20 |
| Flagged / recall / precision at threshold | ~55% flagged, 83% recall, 30% precision | ~11% flagged, 25% recall, 27% precision |

Both thresholds favor **recall** over precision, but for different reasons: no-show's intervention (an automated reminder) is nearly free to send at any scale, so the threshold stays low. Readmission's intervention (a care coordinator's outreach call) is capacity-constrained, not free — its threshold was set by working backward from a realistic caseload (top ~10% riskiest patients), not a pure cost ratio. See [`plan.md`](plan.md) for the full threshold-derivation writeup.

## Calibration: why and how

Early versions of both models displayed a raw `predict_proba()` percentage as "risk %." A calibration check (`notebooks/05_calibration_check.ipynb`, reliability curves against a genuinely held-out test set) found both models were substantially overconfident — a patient scored "73% no-show risk" by the raw no-show model actually no-showed about 41% of the time; a patient scored "71% readmission risk" actually got readmitted about 28% of the time.

Fix: `CalibratedClassifierCV` (sigmoid/Platt scaling, chosen because gradient-boosted trees are known to produce a specific sigmoid-shaped overconfidence pattern) fit on a held-out calibration slice, verified to bring predicted-vs-actual gaps from as much as ±0.43 down to within ±0.02. This wasn't a one-line model swap — calibration is a monotonic rescaling, so it preserves patient *ranking* but shifts the *number scale*, meaning the old decision thresholds had to be re-derived from scratch against the new scale (reusing them as-is would have silently changed which patients got flagged, verified concretely: the same 0.4 no-show threshold that caught 92% of true no-shows on the raw scale caught only 12% on the calibrated scale). The dashboard now shows a risk band (Low/Moderate/High) rather than the raw percentage — deliberately, since a number invites more precision than the model can currently promise; the underlying score is honest now, but band-only stays simpler for staff to act on.

## Project structure

```
accessiq/
├── data/
│   ├── raw/              # KaggleV2-May-2016.csv, diabetic_data.csv (committed — small, public, anonymized)
│   └── processed/        # cleaned/feature-engineered CSVs
├── notebooks/            # EDA, baseline modeling, calibration check
├── models/
│   ├── no_show/           # preprocess.py, train.py, gradient_boosting_v1.joblib (raw, for SHAP), calibrated_v1.joblib (for scoring)
│   └── readmission/       # same structure
├── backend/               # FastAPI app (main.py, worklist.py, explain.py, alerts_db.py)
├── frontend/              # React (Vite) dashboard
├── progress-log/          # one file per day of work
└── plan.md                # living project plan + decision log
```

## Running locally

**Backend**
```
cd backend
pip install -r requirements.txt
# create a .env file with GEMINI_API_KEY=your-key
uvicorn main:app --port 8000
```

**Frontend**
```
cd frontend
npm install
npm run dev
```

The frontend defaults to `http://localhost:8000` for the API; set `VITE_API_URL` to point elsewhere.

## Known limitations

- **Alerts don't persist long-term on the free-tier deployment** — Render's free web services have no persistent disk, so `alerts.db` resets on restart/spin-down. Would need a hosted database (e.g. Postgres) to fix for real.
- **The two models' populations aren't disclosed in the UI.** No-show is Brazilian outpatient data from 2016; readmission is US inpatient data from 1999–2008 — a deliberate design choice (two independent problems, one dashboard), but currently only documented in `plan.md`, not visible to someone just using the app.
- **Readmission's ROC-AUC (0.672) is a realistic ceiling, not a shortfall** — 30-day readmission is a well-documented hard problem in healthcare ML; published models on this exact dataset commonly land in the 0.65–0.70 range, likely because real readmission risk depends on factors (social support, post-discharge adherence, follow-up access) this dataset doesn't capture.

## Tech stack

Python · pandas · scikit-learn · SHAP · FastAPI · SQLite · Google Gemini API (`google-genai`) · React · Vite · Render · Netlify
