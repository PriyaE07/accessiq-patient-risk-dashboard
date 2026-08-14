import './RiskMeter.css'

/**
 * Displays a risk score as a status-colored meter — band label + proportional
 * bar, deliberately no raw percentage (see plan.md "Known gap to address
 * later": the model's probabilities are currently miscalibrated/overstated,
 * so printing an exact number would overstate precision the model doesn't
 * have).
 *
 * The good/warning/critical bands are derived from the actual decision
 * threshold chosen for this model (see progress-log/2026-08-12.md for the
 * no-show/readmission threshold discussions) — not arbitrary cutoffs:
 *   - below half the threshold: good
 *   - below the threshold: warning (approaching the flagged cutoff)
 *   - at/above the threshold: critical (this is what "flagged" means)
 */
function getStatus(riskScore, threshold) {
  if (riskScore < threshold / 2) {
    return { level: 'good', label: 'Low risk', icon: '✓' }
  }
  if (riskScore < threshold) {
    return { level: 'warning', label: 'Moderate risk', icon: '!' }
  }
  return { level: 'critical', label: 'High risk', icon: '✕' }
}

function RiskMeter({ label, riskScore, threshold, recommendations, children }) {
  const status = getStatus(riskScore, threshold)
  const recommendation = recommendations?.[status.level]

  return (
    <div className="risk-meter-card">
      <p className="risk-meter-label">{label}</p>

      {/* The model's underlying probabilities are known to run overconfident
          (see plan.md "Known gap to address later" — calibration check),
          so we deliberately don't print the raw number here. The band
          label + proportional bar convey relative risk without claiming a
          precision the model doesn't actually have. */}
      <div className={`risk-meter-hero status-${status.level}`}>{status.label}</div>

      <div className={`risk-meter-badge status-${status.level}`}>
        <span className="risk-meter-badge-icon">{status.icon}</span>
        {status.label}
      </div>

      <div className="risk-meter-track">
        <div
          className={`risk-meter-fill status-${status.level}`}
          style={{ width: `${Math.min(riskScore * 100, 100)}%` }}
        />
      </div>

      {recommendation && (
        <p className="risk-meter-recommendation">{recommendation}</p>
      )}

      {children}
    </div>
  )
}

export default RiskMeter
