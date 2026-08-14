import { useEffect, useState } from 'react'
import RiskMeter from './RiskMeter.jsx'
import ExplainChat from './ExplainChat.jsx'
import './Worklist.css'

/**
 * Sortable, filterable table of real held-out patients, scored in a batch.
 * This is the "who should I be worried about" triage view — contrast with
 * the single-patient forms, which only answer "what's the risk for this
 * one patient." Clicking a row drills into that patient's full detail
 * (risk meter + chat), reusing the same components the single-patient
 * forms use.
 */
function Worklist({ title, description, endpoint, columns, riskLabel, predictionType, threshold }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortKey, setSortKey] = useState('risk_score')
  const [sortDir, setSortDir] = useState('desc')
  const [onlyFlagged, setOnlyFlagged] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(null)

  async function loadWorklist() {
    setLoading(true)
    setError(null)
    setSelectedIndex(null)
    try {
      const response = await fetch(`${endpoint}?n=20`)
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`)
      }
      const data = await response.json()
      setRows(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWorklist()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint])

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const visibleRows = rows
    .filter((row) => !onlyFlagged || row.flagged_high_risk)
    .slice()
    .sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      if (aVal === bVal) return 0
      const direction = sortDir === 'asc' ? 1 : -1
      return aVal > bVal ? direction : -direction
    })

  const selectedRow = selectedIndex != null ? visibleRows[selectedIndex] : null

  return (
    <div>
      <div className="page-header">
        <h1>{title}</h1>
        <p>{description}</p>
      </div>

      <div className="worklist-controls">
        <label className="worklist-filter">
          <input
            type="checkbox"
            checked={onlyFlagged}
            onChange={(e) => setOnlyFlagged(e.target.checked)}
          />
          Show only flagged patients
        </label>
        <button className="worklist-refresh" onClick={loadWorklist} disabled={loading}>
          {loading ? 'Loading…' : 'New sample'}
        </button>
      </div>

      {error && <p className="error-message">Error: {error}</p>}

      {!error && (
        <div className="worklist-layout">
          <div className="worklist-table-wrapper">
            <table className="worklist-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col.key} onClick={() => handleSort(col.key)}>
                      {col.label}
                      {sortKey === col.key && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                    </th>
                  ))}
                  <th onClick={() => handleSort('risk_score')}>
                    {riskLabel}
                    {sortKey === 'risk_score' && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                  </th>
                  <th onClick={() => handleSort('flagged_high_risk')}>
                    Flagged
                    {sortKey === 'flagged_high_risk' && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row, i) => (
                  <tr
                    key={i}
                    className={`${row.flagged_high_risk ? 'flagged' : ''} ${i === selectedIndex ? 'selected' : ''}`}
                    onClick={() => setSelectedIndex(i)}
                  >
                    {columns.map((col) => (
                      <td key={col.key}>{String(row[col.key])}</td>
                    ))}
                    <td>{(row.risk_score * 100).toFixed(1)}%</td>
                    <td>{row.flagged_high_risk ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {visibleRows.length === 0 && !loading && (
              <p className="worklist-empty">No patients match the current filter.</p>
            )}
          </div>

          {selectedRow && (
            <div className="worklist-detail">
              <RiskMeter
                label={riskLabel}
                riskScore={selectedRow.risk_score}
                threshold={threshold}
              >
                <ExplainChat
                  key={JSON.stringify(selectedRow)}
                  predictionType={predictionType}
                  riskScore={selectedRow.risk_score}
                  topFactors={selectedRow.top_factors}
                />
              </RiskMeter>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Worklist
