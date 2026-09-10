import Stats from '../../components/Stats/Stats'
import LiveCamera from '../../components/Camera/LiveCamera'
import IncidentPanel from '../../components/Incidents/IncidentPanel'

import useIncidents from '../../hooks/useIncidents'

import './Dashboard.css'

function Dashboard() {
  const {
    incidents,
    loading,
    error,
    loadIncidents,
    updateStatus,
  } = useIncidents()

  return (
    <main className="dashboard">
      <Stats incidents={incidents} />

      <LiveCamera />

      <IncidentPanel
        incidents={incidents}
        loading={loading}
        error={error}
        onRefresh={loadIncidents}
        onUpdateStatus={updateStatus}
      />
    </main>
  )
}

export default Dashboard
