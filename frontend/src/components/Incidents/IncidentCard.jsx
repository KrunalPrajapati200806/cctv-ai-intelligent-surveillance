import {
  getNextIncidentStatus,
  getNextIncidentActionLabel,
} from '../../utils/incidentStatus'


function IncidentCard({
  incident,
  onUpdateStatus,
  onViewDetails,
}) {
  const nextStatus =
    getNextIncidentStatus(incident.status)

  const actionLabel =
    getNextIncidentActionLabel(incident.status)


  function handleStatusUpdate() {
    if (!nextStatus) {
      return
    }

    onUpdateStatus(
      incident.incident_id,
      nextStatus
    )
  }


  return (
    <article className="incident-card">

      <div className="incident-main">

        <div className="incident-title">

          <span
            className={`severity ${incident.severity}`}
          >
            {incident.severity}
          </span>

          <h3>
            {incident.alert_type}
          </h3>

        </div>

        <p className="message">
          {incident.message}
        </p>

        <div className="incident-meta">

          <span>
            Camera: {incident.camera_id}
          </span>

          <span>
            People: {incident.person_count}
          </span>

          <span>
            Threshold: {incident.threshold}
          </span>

        </div>

      </div>


      <div className="incident-actions">

        <span
          className={`status ${incident.status.toLowerCase()}`}
        >
          {incident.status}
        </span>


        <button
          onClick={() =>
            onViewDetails(incident)
          }
        >
          View Details
        </button>


        {nextStatus && (
          <button
            onClick={handleStatusUpdate}
          >
            {actionLabel}
          </button>
        )}

      </div>

    </article>
  )
}


export default IncidentCard