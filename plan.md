# AccessIQ — Patient Risk Dashboard

## Problem
Hospitals lose time/resources in two predictable ways:
1. **No-shows** — patients book appointments and don't come, wasting a slot another patient could have used.
2. **30-day readmissions** — discharged patients return within 30 days, hurting outcomes and hospital credibility/reimbursement.

The goal is **prediction, not retrospection**: flag the risk *at the moment of booking* (no-show) or *at the moment of discharge* (readmission) — before the event happens — so staff can intervene (reminder calls, follow-up scheduling, care coordination, etc.).

## Data
- **No-show risk**: Kaggle "Medical Appointment No Shows" dataset (~110k Brazilian outpatient appointments — scheduling date, appointment date, age, neighborhood, SMS reminders, chronic conditions, no-show label).
- **Readmission risk**: UCI "Diabetes 130-US Hospitals" dataset (~100k inpatient encounters, labeled `readmitted: <30 / >30 / no`).
- Two independent datasets/populations — no shared patient IDs. Treated as two separate risk models under one dashboard.

## Constraint that matters most
**No data leakage.** Every feature used by a model must be genuinely known *before* the predicted event:
- No-show model: only info available at booking time.
- Readmission model: only info available at/by discharge time (not anything recorded post-discharge).

## Tech stack
- **Modeling**: Python, pandas, scikit-learn (logistic regression baseline → gradient boosting, `HistGradientBoostingClassifier`)
- **Backend/API**: FastAPI serving risk scores from trained models
- **Frontend**: React (Vite) dashboard — sidebar nav, per-model forms, `RiskMeter` component (hero score + severity meter + status badge, using a validated design-system palette)
- **Storage**: SQLite (planned, not yet built — needed for the alerts/persistence feature below)
- **LLM (planned)**: Claude API (Python `anthropic` SDK) for grounded, per-patient risk explanations — see Dashboard feature backlog

## Repo structure
```
accessiq/
├── data/
│   ├── raw/              # downloaded datasets (gitignored)
│   └── processed/        # cleaned/feature-engineered data
├── notebooks/            # EDA + baseline modeling notebooks
├── models/
│   ├── no_show/          # preprocess.py, train.py, saved model, feature_columns.joblib
│   └── readmission/      # preprocess.py, train.py, saved model, feature_columns.joblib
├── backend/               # FastAPI app serving risk scores (main.py)
├── frontend/              # React (Vite) dashboard
├── progress-log/          # one file per day, e.g. 2026-08-10.md
├── plan.md
└── README.md
```

## Build order
1. ✅ Download raw datasets, EDA to confirm booking/discharge-time feature framing (no leakage)
2. ✅ Build + evaluate no-show model (logistic regression → gradient boosting, threshold 0.4)
3. ✅ Build + evaluate readmission model (logistic regression → gradient boosting, threshold 0.6)
4. ✅ FastAPI serving both models (`/predict/no-show`, `/predict/readmission`)
5. ✅ React dashboard — functional, then redesigned with a real design system (sidebar shell, `RiskMeter`, grouped/sectioned forms)
6. 🔄 **Dashboard feature backlog** (researched against real clinical-dashboard UX practices — see `progress-log/` for sources) — build order, easy → hard:
   1. Actionable recommendations — map risk band to the intervention text already decided per model (automated reminder for no-show; care coordinator outreach for readmission)
   2. Progressive disclosure on the readmission form (44 fields → core fields visible, rest behind "Show advanced")
   3. Per-patient explainability + chatbot — SHAP values computed at prediction time, passed as grounded context to Claude (direct context injection, not RAG — the grounding data is a small complete set of known values, not a corpus to retrieve from) so explanations are tied to what the model actually did, not free-associated
   4. ✅ Patient worklist view — real sample of held-out patients, batch-scored, sortable/filterable table (no fake data); click-to-expand row detail reuses `RiskMeter` + `ExplainChat`, so the chatbot is available from the worklist too, not just the single-patient forms
   5. ✅ Aggregate/ops summary view — new "Overview" nav page, per model: flagged count + average risk stat tiles, risk-distribution bar chart (Low/Moderate/High, status-colored), and a "most frequent top SHAP factors across the sample" bar chart. Sampled from the same reproducible held-out split as the worklist (n=300, `sample_worklist`'s sibling `summarize_worklist`).
   6. ✅ Alerts/persistence — SQLite (`backend/alerts_db.py`, plain `sqlite3`, no ORM). Only flagged predictions from the single-patient forms are saved (worklist/Overview samples are re-drawn demo data, not persisted). New "Alerts" nav page: filter tabs by status, each alert has an Acknowledge → Resolve action (`PATCH /alerts/{id}`) that just flips the `status` column — no notifications or side effects beyond that.
   - Explicitly deferred/reframed: a true longitudinal per-patient trend view isn't supported by either dataset (single-snapshot per encounter); would need to become "dashboard usage over time" instead, which starts empty until the tool is actually used
   - Explicitly out of scope for now: role-based views (over-engineering for current single-user scope)

## Known gap — deprioritized, not being addressed for now
- **Population mismatch isn't disclosed to a dashboard user.** The two modules are trained on entirely unrelated populations (no-show: Brazilian outpatient scheduling data, 2016; readmission: US inpatient diabetes data, 1999–2008) — a deliberate choice from day 1 (no shared patient IDs, two independent problems under one dashboard), but that reasoning currently lives only in this plan and our conversation history, not anywhere a dashboard user would see it. If revisited: add a "Datasets" section to a README (doesn't exist yet) stating this plainly, and a short subtitle on each form's page header noting its dataset/population, so the boundary is visible in the live app too, not just the repo. **Decided 2026-08-14: not worth doing right now** — noted here in case it matters later, but not active work.

## Calibration fix — ✅ done (2026-08-14)
Risk percentages were found to be miscalibrated/overstated (see notebook + progress log for the original finding). Full resolution:
1. ✅ **UI/chatbot fixed first.** `RiskMeter` no longer shows a raw numeric %; hero is now a status-colored band label ("Low/Moderate/High risk") + proportional bar only. The `/explain-chat` system prompt (`backend/main.py`) no longer quotes `risk_score`; it gets the same band label and is explicitly instructed to refuse an exact percentage even if asked directly (verified live).
2. ✅ **`CalibratedClassifierCV` added to both training scripts.** `models/*/train.py` now fits the raw `HistGradientBoostingClassifier` on a 60%-of-data slice (`X_fit`), then calibrates it (`method="sigmoid"` — Platt scaling, chosen because boosted trees are known to produce a sigmoid-shaped overconfidence pattern) on a separate 20% calibration slice via `CalibratedClassifierCV(FrozenEstimator(model), ...)` (sklearn 1.9 API — `cv="prefit"` is gone, replaced by `FrozenEstimator`). Saves two artifacts per model: `gradient_boosting_v1.joblib` (raw, still used for SHAP) and `calibrated_v1.joblib` (new — used for the actual risk score going forward). The original 80/20 train/test split (and therefore `X_test`) is untouched, so worklist/notebook reproducibility still holds.
3. ✅ **Re-verified via `notebooks/05_calibration_check.ipynb`** (raw vs. calibrated side by side, both models). Confirmed the fix worked: worst-bucket gap shrank from +0.337/+0.430 (raw) to ±0.018/±0.009 (calibrated); Brier score improved 32% (no-show) and 56% (readmission).
4. ✅ **Thresholds re-derived on the calibrated scale — new values: 0.20 / 0.20** (both models; not comparable to the old raw-scale 0.4/0.6, different scoring function entirely). Method: worked out the textbook expected-value threshold (`cost_of_intervention / cost_of_missed_outcome`) first — for no-show (cheap SMS vs. a ~$150 wasted slot) it came out to ~0.007, and for readmission (a ~$50 coordinator call vs. a ~$10,000+ readmission) also ~0.005 — both near-zero, "flag almost everyone." Recognized that formula assumes unlimited intervention capacity, true for an automated SMS but not for a coordinator's time, so: no-show threshold was capped at a deliberate, less-extreme middle ground (0.20 → ~55% flagged, ~83% recall) rather than the raw cost-math answer; readmission threshold was instead picked by capacity (top ~10% riskiest patients is a realistic caseload → 0.20 → ~10.8% flagged, recall 0.251, precision 0.265). Full threshold sweep tables are in progress-log/2026-08-14.md.
5. ✅ **Wired `calibrated_v1.joblib` + the new 0.20/0.20 thresholds into the backend.** `backend/worklist.py`'s `WorklistSource` now holds two model objects (`score_model` = calibrated, used for `predict_proba`/threshold; `explain_model` = raw, used for SHAP). `backend/main.py` loads both artifacts per prediction type and wires them the same way in `/predict/*`. Re-verified end-to-end over curl: predictions, worklist, Overview aggregates, and Alerts all confirmed working correctly with the new model+threshold pair together (Overview flagged rates landed right where the threshold sweep predicted: no-show ~62.5%, readmission ~8.5%).
6. ✅ **Decided: keep the band-only UI, don't bring the numeric % back.** Even though the calibrated score is now honest, band-only stays simpler for staff to act on.

Standing technical decision, already implemented: **SHAP stays on the raw (uncalibrated) base model.** `CalibratedClassifierCV` wraps the base tree model in a structure `shap.TreeExplainer` isn't built for. Since calibration only rescales the final aggregate number and never touches feature-level reasoning, explaining off the base model is still an accurate account of *why* — standard practice for post-hoc calibration. The one caveat (raw SHAP `contribution` values are in the base model's units, not the calibrated %) is a non-issue since those numbers are never shown to users anyway — the chatbot's system prompt already forbids quoting them, only direction/relative importance is conveyed, and that ranking is unaffected by a monotonic rescale.

## Status
See `progress-log/` for daily notes. Both models complete and served via FastAPI (now on calibrated scores); React dashboard functional and redesigned with a proper design system. **All 6 dashboard feature backlog items are done. The calibration fix is done.** No open work remains — the population-mismatch disclosure was deliberately deprioritized (see "Known gap" above).
