import { useState } from 'react'
import RiskMeter from './RiskMeter.jsx'
import ExplainChat from './ExplainChat.jsx'
import { GaugeIcon } from './Icons.jsx'
import { API_URL } from './config.js'
import './Form.css'

// Re-derived 2026-08-14 on the calibrated model's score scale — see
// plan.md "Calibration fix" for the full reasoning. Must match
// backend/main.py's NO_SHOW_THRESHOLD exactly, or the band shown here can
// disagree with the backend's actual flagged_high_risk decision.
const NO_SHOW_THRESHOLD = 0.20

// Recommendations tied to the automated-reminder use case we designed the
// no-show threshold around (see progress-log/2026-08-12.md) — cheap
// intervention, so we lean toward flagging generously.
const NO_SHOW_RECOMMENDATIONS = {
  good: 'No action needed — this patient is unlikely to miss the appointment.',
  warning: 'Consider sending a reminder ahead of the appointment.',
  critical: 'Recommended action: send an automated reminder (SMS/email) ahead of this appointment.',
}

const initialFormData = {
  Gender: 'F',
  Age: '',
  Neighbourhood: '',
  Scholarship: false,
  Hipertension: false,
  Diabetes: false,
  Alcoholism: false,
  Handcap: false,
  wait_days: '',
}

function NoShowForm() {
  const [formData, setFormData] = useState(initialFormData)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  function handleChange(event) {
    const { name, value, type, checked } = event.target
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    setResult(null)

    const payload = {
      Gender: formData.Gender,
      Age: Number(formData.Age),
      Neighbourhood: formData.Neighbourhood,
      Scholarship: formData.Scholarship ? 1 : 0,
      Hipertension: formData.Hipertension ? 1 : 0,
      Diabetes: formData.Diabetes ? 1 : 0,
      Alcoholism: formData.Alcoholism ? 1 : 0,
      Handcap: formData.Handcap ? 1 : 0,
      wait_days: Number(formData.wait_days),
    }

    try {
      const response = await fetch(`${API_URL}/predict/no-show`, {
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
        <h1>No-Show Risk</h1>
        <p>Estimate the likelihood a patient misses their appointment, at the moment of booking.</p>
      </div>

      <div className="form-layout">
        <form className="form-card" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label className="field">
              <span className="field-label">Gender</span>
              <select name="Gender" value={formData.Gender} onChange={handleChange}>
                <option value="F">Female</option>
                <option value="M">Male</option>
              </select>
            </label>

            <label className="field">
              <span className="field-label">Age</span>
              <input type="number" name="Age" value={formData.Age} onChange={handleChange} required />
            </label>

            <label className="field">
              <span className="field-label">Neighbourhood</span>
              <input type="text" name="Neighbourhood" value={formData.Neighbourhood} onChange={handleChange} required />
            </label>

            <label className="field">
              <span className="field-label">Days between booking and appointment</span>
              <input type="number" name="wait_days" value={formData.wait_days} onChange={handleChange} required />
            </label>
          </div>

          <div className="field-group">
            <span className="field-group-label">Health & socioeconomic factors</span>
            <div className="checkbox-grid">
              <label className="checkbox-field">
                <input type="checkbox" name="Scholarship" checked={formData.Scholarship} onChange={handleChange} />
                Scholarship (welfare enrollment)
              </label>
              <label className="checkbox-field">
                <input type="checkbox" name="Hipertension" checked={formData.Hipertension} onChange={handleChange} />
                Hypertension
              </label>
              <label className="checkbox-field">
                <input type="checkbox" name="Diabetes" checked={formData.Diabetes} onChange={handleChange} />
                Diabetes
              </label>
              <label className="checkbox-field">
                <input type="checkbox" name="Alcoholism" checked={formData.Alcoholism} onChange={handleChange} />
                Alcoholism
              </label>
              <label className="checkbox-field">
                <input type="checkbox" name="Handcap" checked={formData.Handcap} onChange={handleChange} />
                Has a handicap
              </label>
            </div>
          </div>

          <button type="submit" className="submit-button">Get Risk Prediction</button>
        </form>

        <div className="result-panel">
          {error && <p className="error-message">Error: {error}</p>}
          {result && (
            <RiskMeter
              label="No-show risk"
              riskScore={result.no_show_risk}
              threshold={NO_SHOW_THRESHOLD}
              recommendations={NO_SHOW_RECOMMENDATIONS}
            >
              <ExplainChat
                key={JSON.stringify(result)}
                predictionType="no-show"
                riskScore={result.no_show_risk}
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

export default NoShowForm
