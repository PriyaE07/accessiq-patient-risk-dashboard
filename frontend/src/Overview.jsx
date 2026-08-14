import { useEffect, useState } from 'react'
import { API_URL } from './config.js'
import './Overview.css'

/**
 * "How is today looking overall" — an aggregate view over the full held-out
 * sample for one model: flagged count, average risk, how patients spread
 * across the Low/Moderate/High bands, and which factors are most often
 * driving risk right now. Contrast with the worklist, which is one row per
 * patient; this is the roll-up across many.
 */
function ModelSummary({ title, endpoint, riskLabel }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(`${endpoint}?n=300`)
      .then((response) => {
        if (!response.ok) throw new Error(`Server responded with ${response.status}`)
        return response.json()
      })
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [endpoint])

  if (loading) return <div className="overview-section"><h2>{title}</h2><p className="overview-loading">Loading…</p></div>
  if (error) return <div className="overview-section"><h2>{title}</h2><p className="error-message">Error: {error}</p></div>

  const { sample_size, flagged_count, flagged_pct, avg_risk, band_counts, top_factors } = summary
  const bandTotal = band_counts.low + band_counts.moderate + band_counts.high
  const maxFactorCount = Math.max(...top_factors.map((f) => f.times_top_factor), 1)

  const bands = [
    { key: 'low', label: 'Low', count: band_counts.low, statusClass: 'status-good' },
    { key: 'moderate', label: 'Moderate', count: band_counts.moderate, statusClass: 'status-warning' },
    { key: 'high', label: 'High', count: band_counts.high, statusClass: 'status-critical' },
  ]

  return (
    <div className="overview-section">
      <h2>{title}</h2>
      <p className="overview-sample-note">Based on a sample of {sample_size} held-out patients.</p>

      <div className="overview-stat-tiles">
        <div className="overview-stat-tile">
          <p className="overview-stat-value">{flagged_count}</p>
          <p className="overview-stat-label">Flagged high risk ({flagged_pct}%)</p>
        </div>
        <div className="overview-stat-tile">
          <p className="overview-stat-value">{(avg_risk * 100).toFixed(1)}%</p>
          <p className="overview-stat-label">Average {riskLabel.toLowerCase()}</p>
        </div>
      </div>

      <div className="overview-chart-block">
        <h3>Risk distribution</h3>
        <div className="overview-band-chart">
          {bands.map((band) => (
            <div className="overview-band-row" key={band.key}>
              <span className="overview-band-label">{band.label}</span>
              <div className="overview-band-track" title={`${band.label}: ${band.count} patients`}>
                <div
                  className={`overview-band-fill ${band.statusClass}`}
                  style={{ width: `${bandTotal ? (band.count / bandTotal) * 100 : 0}%` }}
                />
              </div>
              <span className="overview-band-count">{band.count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="overview-chart-block">
        <h3>Most frequent top risk factors</h3>
        <p className="overview-chart-note">How often each factor showed up as one of a patient's top 3 drivers.</p>
        <div className="overview-factor-chart">
          {top_factors.map((factor) => (
            <div className="overview-factor-row" key={factor.feature}>
              <span className="overview-factor-label" title={factor.feature}>{factor.feature}</span>
              <div className="overview-factor-track" title={`${factor.feature}: top factor for ${factor.pct_of_sample}% of patients`}>
                <div
                  className="overview-factor-fill"
                  style={{ width: `${(factor.times_top_factor / maxFactorCount) * 100}%` }}
                />
              </div>
              <span className="overview-factor-count">{factor.pct_of_sample}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Overview() {
  return (
    <div>
      <div className="page-header">
        <h1>Overview</h1>
        <p>A snapshot across both models — for checking overall load before diving into individual worklists.</p>
      </div>

      <div className="overview-layout">
        <ModelSummary title="No-Show Risk" endpoint={`${API_URL}/summary/no-show`} riskLabel="No-show risk" />
        <ModelSummary title="Readmission Risk" endpoint={`${API_URL}/summary/readmission`} riskLabel="Readmission risk" />
      </div>
    </div>
  )
}

export default Overview
