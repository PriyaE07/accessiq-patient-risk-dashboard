import { useState } from 'react'
import RiskMeter from './RiskMeter.jsx'
import ExplainChat from './ExplainChat.jsx'
import { GaugeIcon } from './Icons.jsx'
import { API_URL } from './config.js'
import './Form.css'

// Re-derived 2026-08-14 on the calibrated model's score scale — see
// plan.md "Calibration fix" for the full reasoning. Must match
// backend/main.py's READMISSION_THRESHOLD exactly, or the band shown here
// can disagree with the backend's actual flagged_high_risk decision.
const READMISSION_THRESHOLD = 0.20

// Recommendations tied to the costly-intervention use case we designed the
// readmission threshold around (see progress-log/2026-08-12.md) — care
// coordinator time is real cost, so we lean toward being selective.
const READMISSION_RECOMMENDATIONS = {
  good: 'No action needed — low risk of 30-day readmission.',
  warning: 'Monitor at discharge; standard follow-up is likely sufficient.',
  critical: 'Recommended action: schedule a care coordinator follow-up before discharge.',
}

const MED_OPTIONS = ['No', 'Steady', 'Up', 'Down']
const DIAG_CATEGORY_OPTIONS = [
  'Circulatory', 'Respiratory', 'Digestive', 'Diabetes', 'Injury',
  'Musculoskeletal', 'Genitourinary', 'Neoplasms', 'Other', 'Missing',
]

// Fields are grouped so the 44-field form reads as sections of a chart,
// not a flat wall of inputs — each group renders as its own labeled block.
const GROUPS = [
  {
    title: 'Demographics',
    fields: [
      { name: 'race', label: 'Race', type: 'select', options: ['Caucasian', 'AfricanAmerican', 'Hispanic', 'Asian', 'Other', 'Unknown'] },
      { name: 'gender', label: 'Gender', type: 'select', options: ['Female', 'Male'] },
      { name: 'age', label: 'Age bracket', type: 'select', options: ['[0-10)', '[10-20)', '[20-30)', '[30-40)', '[40-50)', '[50-60)', '[60-70)', '[70-80)', '[80-90)', '[90-100)'] },
    ],
  },
  {
    title: 'Admission details',
    advanced: true,
    fields: [
      { name: 'admission_type_id', label: 'Admission type ID', type: 'text' },
      { name: 'discharge_disposition_id', label: 'Discharge disposition ID', type: 'text' },
      { name: 'admission_source_id', label: 'Admission source ID', type: 'text' },
      { name: 'payer_code', label: 'Payer code', type: 'text' },
      { name: 'medical_specialty', label: 'Medical specialty', type: 'text' },
    ],
  },
  {
    title: 'Visit history & counts',
    fields: [
      { name: 'time_in_hospital', label: 'Time in hospital (days)', type: 'number' },
      { name: 'num_lab_procedures', label: 'Number of lab procedures', type: 'number' },
      { name: 'num_procedures', label: 'Number of procedures', type: 'number' },
      { name: 'num_medications', label: 'Number of medications', type: 'number' },
      { name: 'number_outpatient', label: 'Prior outpatient visits', type: 'number' },
      { name: 'number_emergency', label: 'Prior emergency visits', type: 'number' },
      { name: 'number_inpatient', label: 'Prior inpatient visits', type: 'number' },
      { name: 'number_diagnoses', label: 'Number of diagnoses', type: 'number' },
    ],
  },
  {
    title: 'Lab results',
    advanced: true,
    fields: [
      { name: 'max_glu_serum', label: 'Max glucose serum test', type: 'select', options: ['Not_Tested', 'Norm', '>200', '>300'] },
      { name: 'A1Cresult', label: 'A1C result', type: 'select', options: ['Not_Tested', 'Norm', '>7', '>8'] },
    ],
  },
  {
    title: 'Medications',
    advanced: true,
    fields: [
      { name: 'metformin', label: 'Metformin', type: 'select', options: MED_OPTIONS },
      { name: 'repaglinide', label: 'Repaglinide', type: 'select', options: MED_OPTIONS },
      { name: 'nateglinide', label: 'Nateglinide', type: 'select', options: MED_OPTIONS },
      { name: 'chlorpropamide', label: 'Chlorpropamide', type: 'select', options: MED_OPTIONS },
      { name: 'glimepiride', label: 'Glimepiride', type: 'select', options: MED_OPTIONS },
      { name: 'acetohexamide', label: 'Acetohexamide', type: 'select', options: MED_OPTIONS },
      { name: 'glipizide', label: 'Glipizide', type: 'select', options: MED_OPTIONS },
      { name: 'glyburide', label: 'Glyburide', type: 'select', options: MED_OPTIONS },
      { name: 'tolbutamide', label: 'Tolbutamide', type: 'select', options: MED_OPTIONS },
      { name: 'pioglitazone', label: 'Pioglitazone', type: 'select', options: MED_OPTIONS },
      { name: 'rosiglitazone', label: 'Rosiglitazone', type: 'select', options: MED_OPTIONS },
      { name: 'acarbose', label: 'Acarbose', type: 'select', options: MED_OPTIONS },
      { name: 'miglitol', label: 'Miglitol', type: 'select', options: MED_OPTIONS },
      { name: 'troglitazone', label: 'Troglitazone', type: 'select', options: MED_OPTIONS },
      { name: 'tolazamide', label: 'Tolazamide', type: 'select', options: MED_OPTIONS },
      { name: 'insulin', label: 'Insulin', type: 'select', options: MED_OPTIONS },
      { name: 'glyburide_metformin', label: 'Glyburide-metformin', type: 'select', options: MED_OPTIONS },
      { name: 'glipizide_metformin', label: 'Glipizide-metformin', type: 'select', options: MED_OPTIONS },
      { name: 'glimepiride_pioglitazone', label: 'Glimepiride-pioglitazone', type: 'select', options: MED_OPTIONS },
      { name: 'metformin_rosiglitazone', label: 'Metformin-rosiglitazone', type: 'select', options: MED_OPTIONS },
      { name: 'metformin_pioglitazone', label: 'Metformin-pioglitazone', type: 'select', options: MED_OPTIONS },
      { name: 'change', label: 'Medication changed this visit', type: 'select', options: ['No', 'Ch'] },
      { name: 'diabetesMed', label: 'On diabetes medication', type: 'select', options: ['No', 'Yes'] },
    ],
  },
  {
    title: 'Diagnosis categories',
    fields: [
      { name: 'diag_1_cat', label: 'Primary diagnosis category', type: 'select', options: DIAG_CATEGORY_OPTIONS },
      { name: 'diag_2_cat', label: 'Secondary diagnosis category', type: 'select', options: DIAG_CATEGORY_OPTIONS },
      { name: 'diag_3_cat', label: 'Tertiary diagnosis category', type: 'select', options: DIAG_CATEGORY_OPTIONS },
    ],
  },
]

const ALL_FIELDS = GROUPS.flatMap((group) => group.fields)
const NUMBER_FIELD_NAMES = ALL_FIELDS.filter((f) => f.type === 'number').map((f) => f.name)

const initialFormData = Object.fromEntries(
  ALL_FIELDS.map((field) => [
    field.name,
    field.type === 'select' ? field.options[0] : '',
  ])
)

function ReadmissionForm() {
  const [formData, setFormData] = useState(initialFormData)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  function handleChange(event) {
    const { name, value } = event.target
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setResult(null)

    const payload = { ...formData }
    for (const name of NUMBER_FIELD_NAMES) {
      payload[name] = Number(payload[name])
    }

    try {
      const response = await fetch(`${API_URL}/predict/readmission`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Readmission Risk</h1>
        <p>Estimate the likelihood of a 30-day readmission, at the moment of discharge.</p>
      </div>

      <div className="form-layout">
        <form className="form-card" onSubmit={handleSubmit}>
          {GROUPS.filter((group) => !group.advanced || showAdvanced).map((group) => (
            <div className="field-group" key={group.title}>
              <span className="field-group-label">{group.title}</span>
              <div className="form-grid">
                {group.fields.map((field) => (
                  <label className="field" key={field.name}>
                    <span className="field-label">{field.label}</span>
                    {field.type === 'select' ? (
                      <select name={field.name} value={formData[field.name]} onChange={handleChange}>
                        {field.options.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={field.type}
                        name={field.name}
                        value={formData[field.name]}
                        onChange={handleChange}
                        required
                      />
                    )}
                  </label>
                ))}
              </div>
            </div>
          ))}

          <button
            type="button"
            className="advanced-toggle"
            onClick={() => setShowAdvanced((prev) => !prev)}
          >
            {showAdvanced ? '− Hide advanced fields' : '+ Show advanced fields (admission codes, lab results, medications)'}
          </button>

          <button type="submit" className="submit-button">Get Readmission Risk</button>
        </form>

        <div className="result-panel">
          {error && <p className="error-message">Error: {error}</p>}
          {result && (
            <RiskMeter
              label="Readmission risk"
              riskScore={result.readmission_risk}
              threshold={READMISSION_THRESHOLD}
              recommendations={READMISSION_RECOMMENDATIONS}
            >
              <ExplainChat
                key={JSON.stringify(result)}
                predictionType="readmission"
                riskScore={result.readmission_risk}
                topFactors={result.top_factors}
              />
            </RiskMeter>
          )}
          {!error && !result && (
            <div className="result-placeholder">
              <span className="result-placeholder-icon">
                <GaugeIcon />
              </span>
              Fill out the form and submit to see a risk prediction.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ReadmissionForm
