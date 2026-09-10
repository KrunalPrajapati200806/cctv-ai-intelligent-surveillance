import { useMemo, useState } from 'react'
import './Incidents.css'

import IncidentCard from './IncidentCard'
import IncidentFilters from './IncidentFilters'
import IncidentDetails from './IncidentDetails'

function IncidentPanel({
  incidents,
  loading,
  error,
  onRefresh,
  onUpdateStatus,
}) {
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [cameraFilter, setCameraFilter] = useState('ALL')
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [selectedIncident, setSelectedIncident] = useState(null)

  const cameras = useMemo(() => {
    return [
      ...new Set(
        incidents.map(
          (incident) => incident.camera_id
        )
      ),
    ]
  }, [incidents])

  const filteredIncidents = useMemo(() => {
    return incidents.filter((incident) => {
      const statusMatch =
        statusFilter === 'ALL' ||
        incident.status === statusFilter

      const cameraMatch =
        cameraFilter === 'ALL' ||
        incident.camera_id === cameraFilter

      const severityMatch =
        severityFilter === 'ALL' ||
        incident.severity === severityFilter

      return (
        statusMatch &&
        cameraMatch &&
        severityMatch
      )
    })
  }, [
    incidents,
    statusFilter,
    cameraFilter,
    severityFilter,
  ])

  function handleStatusUpdate(
    incidentId,
    status
  ) {
    onUpdateStatus(
      incidentId,
      status
    )

    if (
      selectedIncident &&
      selectedIncident.incident_id === incidentId
    ) {
      setSelectedIncident(null)
    }
  }

  return (
    <section className="incidents-panel">
      <div className="panel-header">
        <div>
          <h2>Incidents</h2>

          <span>
            AI-generated security alerts
          </span>
        </div>

        <button
          className="refresh-button"
          onClick={onRefresh}
        >
          Refresh
        </button>
      </div>

      <IncidentFilters
        statusFilter={statusFilter}
        cameraFilter={cameraFilter}
        severityFilter={severityFilter}
        cameras={cameras}
        onStatusChange={setStatusFilter}
        onCameraChange={setCameraFilter}
        onSeverityChange={setSeverityFilter}
      />

      {loading && (
        <div className="empty">
          Loading incidents...
        </div>
      )}

      {error && (
        <div className="error">
          {error}
        </div>
      )}

      {!loading &&
        !error &&
        filteredIncidents.length === 0 && (
          <div className="empty">
            No incidents found.
          </div>
        )}

      {!loading &&
        !error &&
        filteredIncidents.length > 0 && (
          <div className="incident-list">
            {filteredIncidents.map(
              (incident) => (
                <IncidentCard
                  key={incident.incident_id}
                  incident={incident}
                  onUpdateStatus={
                    handleStatusUpdate
                  }
                  onViewDetails={
                    setSelectedIncident
                  }
                />
              )
            )}
          </div>
        )}

      {selectedIncident && (
        <IncidentDetails
          incident={selectedIncident}
          onClose={() =>
            setSelectedIncident(null)
          }
          onUpdateStatus={
            handleStatusUpdate
          }
        />
      )}
    </section>
  )
}

export default IncidentPanel