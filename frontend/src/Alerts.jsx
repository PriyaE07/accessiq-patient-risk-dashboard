import { useEffect, useState } from 'react'
import { API_URL } from './config.js'
import './Alerts.css'

const STATUS_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'new', label: 'New' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'resolved', label: 'Resolved' },
]

// What "act on this" looks like for each status: which button to show, and
// which status it moves the alert to next.
const NEXT_ACTION = {
  new: { label: 'Acknowledge', nextStatus: 'acknowledged' },
  acknowledged: { label: 'Resolve', nextStatus: 'resolved' },
  resolved: null,
}

// A few fields per prediction type worth showing at a glance, so an alert
// isn't just a bare risk score — pulled from the same patient_data JSON
// saved alongside it.
const PATIENT_SUMMARY_FIELDS = {
  'no-show': ['Age', 'Gender', 'Neighbourhood', 'wait_days'],
  readmission: ['age', 'gender', 'race', 'time_in_hospital', 'number_inpatient'],
}

function formatTimestamp(isoString) {
  return new Date(isoString).toLocaleString()
}

/**
 * A saved, actionable list of every flagged high-risk prediction a
 * single-patient form has produced — as opposed to the worklist/Overview
 * pages, which re-sample fresh demo data on every load and persist nothing.
 * This is the "did we actually follow up on that patient" view.
 */
function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [updatingId, setUpdatingId] = useState(null)

  async function loadAlerts() {
    setLoading(true)
    setError(null)
    try {
      const query = statusFilter === 'all' ? '' : `?status=${statusFilter}`
      const response = await fetch(`${API_URL}/alerts${query}`)
      if (!response.ok) throw new Error(`Server responded with ${response.status}`)
      setAlerts(await response.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAlerts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  async function advanceStatus(alert) {
    const action = NEXT_ACTION[alert.status]
    if (!action) return
    setUpdatingId(alert.id)
    try {
      const response = await fetch(`${API_URL}/alerts/${alert.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: action.nextStatus }),
      })
      if (!response.ok) throw new Error(`Server responded with ${response.status}`)
      const updated = await response.json()
      setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
    } catch (err) {
      setError(err.message)
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Alerts</h1>
        <p>Every flagged high-risk prediction from the single-patient forms, saved so it doesn't get lost — acknowledge and resolve as you follow up.</p>
      </div>

      <div className="alerts-controls">
        <div className="alerts-filter-tabs">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.key}
              className={`alerts-filter-tab ${statusFilter === filter.key ? 'active' : ''}`}
              onClick={() => setStatusFilter(filter.key)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <button className="alerts-refresh" onClick={loadAlerts} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {error && <p className="error-message">Error: {error}</p>}

      {!error && !loading && alerts.length === 0 && (
        <p className="alerts-empty">No alerts here. Flag a patient from one of the forms to see it show up.</p>
      )}

      {!error && alerts.length > 0 && (
        <div className="alerts-list">
          {alerts.map((alert) => {
            const action = NEXT_ACTION[alert.status]
            const summaryFields = PATIENT_SUMMARY_FIELDS[alert.prediction_type] || []
            return (
              <div className="alert-card" key={alert.id}>
                <div className="alert-card-main">
                  <div className="alert-card-header">
                    <span className={`alert-type-badge alert-type-${alert.prediction_type}`}>
                      {alert.prediction_type === 'no-show' ? 'No-show' : 'Readmission'}
                    </span>
                    <span className={`alert-status-badge alert-status-${alert.status}`}>{alert.status}</span>
                    <span className="alert-risk-score">{(alert.risk_score * 100).toFixed(1)}% risk</span>
                  </div>
                  <div className="alert-patient-summary">
                    {summaryFields.map((field) => (
                      <span key={field} className="alert-patient-field">
                        <strong>{field}:</strong> {String(alert.patient_data[field])}
                      </span>
                    ))}
                  </div>
                  <p className="alert-timestamp">Flagged {formatTimestamp(alert.created_at)}</p>
                </div>
                {action && (
                  <button
                    className="alert-action-button"
                    onClick={() => advanceStatus(alert)}
                    disabled={updatingId === alert.id}
                  >
                    {updatingId === alert.id ? 'Saving…' : action.label}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default Alerts
