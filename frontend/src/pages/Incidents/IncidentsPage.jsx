import IncidentPanel from '../../components/Incidents/IncidentPanel'
import useIncidents from '../../hooks/useIncidents'

function IncidentsPage() {
  const {
    incidents,
    loading,
    error,
    loadIncidents,
    updateStatus,
  } = useIncidents()

  return (
    <main className="page incidents-page">
      <div className="page-header">
        <div>
          <h1>Incidents</h1>
          <p>AI-generated security alerts and incident management</p>
        </div>

        <button
          type="button"
          onClick={loadIncidents}
          disabled={loading}
          className="refresh-button"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

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

export default IncidentsPage
