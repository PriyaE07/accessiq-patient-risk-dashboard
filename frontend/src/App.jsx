import { useState } from 'react'
import NoShowForm from './NoShowForm.jsx'
import ReadmissionForm from './ReadmissionForm.jsx'
import Worklist from './Worklist.jsx'
import Overview from './Overview.jsx'
import Alerts from './Alerts.jsx'
import { OverviewIcon, CalendarIcon, PulseIcon, ListIcon, ClipboardListIcon, BellIcon } from './Icons.jsx'
import { API_URL } from './config.js'
import './App.css'

const NO_SHOW_COLUMNS = [
  { key: 'AppointmentID', label: 'Appointment ID' },
  { key: 'Age', label: 'Age' },
  { key: 'Gender', label: 'Gender' },
  { key: 'Neighbourhood', label: 'Neighbourhood' },
  { key: 'wait_days', label: 'Wait days' },
  { key: 'Scholarship', label: 'Scholarship' },
  { key: 'Hipertension', label: 'Hypertension' },
  { key: 'Diabetes', label: 'Diabetes' },
]

const READMISSION_COLUMNS = [
  { key: 'encounter_id', label: 'Encounter ID' },
  { key: 'age', label: 'Age' },
  { key: 'gender', label: 'Gender' },
  { key: 'race', label: 'Race' },
  { key: 'time_in_hospital', label: 'Days in hospital' },
  { key: 'number_inpatient', label: 'Prior inpatient visits' },
  { key: 'number_diagnoses', label: 'Diagnoses' },
  { key: 'diag_1_cat', label: 'Primary diagnosis' },
]

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', Icon: OverviewIcon },
  { id: 'no-show', label: 'No-Show Risk', Icon: CalendarIcon },
  { id: 'readmission', label: 'Readmission Risk', Icon: PulseIcon },
  { id: 'no-show-worklist', label: 'No-Show Worklist', Icon: ListIcon },
  { id: 'readmission-worklist', label: 'Readmission Worklist', Icon: ClipboardListIcon },
  { id: 'alerts', label: 'Alerts', Icon: BellIcon },
]

function App() {
  const [view, setView] = useState('overview')

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-mark">A</span>
          <span className="sidebar-brand-name">AccessIQ</span>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`sidebar-nav-item ${view === item.id ? 'active' : ''}`}
              onClick={() => setView(item.id)}
            >
              <item.Icon />
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        {view === 'overview' && <Overview />}
        {view === 'alerts' && <Alerts />}
        {view === 'no-show' && <NoShowForm />}
        {view === 'readmission' && <ReadmissionForm />}
        {view === 'no-show-worklist' && (
          <Worklist
            title="No-Show Worklist"
            description="Real held-out patients, scored in a batch and ranked by risk — for triaging who to follow up with, not looking up one patient at a time. Click a row for detail."
            endpoint={`${API_URL}/worklist/no-show`}
            columns={NO_SHOW_COLUMNS}
            riskLabel="No-show risk"
            predictionType="no-show"
            threshold={0.20}
          />
        )}
        {view === 'readmission-worklist' && (
          <Worklist
            title="Readmission Worklist"
            description="Real held-out patients, scored in a batch and ranked by risk — for triaging who to follow up with, not looking up one patient at a time. Click a row for detail."
            endpoint={`${API_URL}/worklist/readmission`}
            columns={READMISSION_COLUMNS}
            riskLabel="Readmission risk"
            predictionType="readmission"
            threshold={0.20}
          />
        )}
      </main>
    </div>
  )
}

export default App
