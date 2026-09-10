import {
  getNextIncidentStatus,
  getNextIncidentActionLabel,
} from '../../utils/incidentStatus'


function IncidentDetails({
  incident,
  onClose,
  onUpdateStatus,
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
    <div
      className="incident-modal-backdrop"
      onClick={onClose}
    >

      <div
        className="incident-modal"
        onClick={(event) =>
          event.stopPropagation()
        }
      >

        {/* ====================================================
            HEADER
            ==================================================== */}

        <div className="incident-modal-header">

          <div>

            <span
              className={`severity ${incident.severity}`}
            >
              {incident.severity}
            </span>

            <h2>
              {incident.alert_type}
            </h2>

          </div>

          <button
            className="close-button"
            onClick={onClose}
          >
            ×
          </button>

        </div>


        {/* ====================================================
            MESSAGE
            ==================================================== */}

        <div className="incident-detail-message">

          <strong>
            Message
          </strong>

          <p>
            {incident.message}
          </p>

        </div>


        {/* ====================================================
            INCIDENT DETAILS
            ==================================================== */}

        <div className="incident-detail-grid">

          <div>
            <span>
              Incident ID
            </span>

            <strong>
              {incident.incident_id}
            </strong>
          </div>


          <div>
            <span>
              Camera
            </span>

            <strong>
              {incident.camera_id}
            </strong>
          </div>


          <div>
            <span>
              Status
            </span>

            <strong>
              {incident.status}
            </strong>
          </div>


          <div>
            <span>
              Severity
            </span>

            <strong>
              {incident.severity}
            </strong>
          </div>


          <div>
            <span>
              People
            </span>

            <strong>
              {incident.person_count}
            </strong>
          </div>


          <div>
            <span>
              Threshold
            </span>

            <strong>
              {incident.threshold}
            </strong>
          </div>


          <div>
            <span>
              Event Type
            </span>

            <strong>
              {incident.event_type}
            </strong>
          </div>


          <div>
            <span>
              Alert Type
            </span>

            <strong>
              {incident.alert_type}
            </strong>
          </div>


          <div>
            <span>
              Frame ID
            </span>

            <strong>
              {incident.frame_id || 'N/A'}
            </strong>
          </div>


          <div>
            <span>
              Created At
            </span>

            <strong>
              {incident.created_at}
            </strong>
          </div>


          <div>
            <span>
              Updated At
            </span>

            <strong>
              {incident.updated_at}
            </strong>
          </div>

        </div>


        {/* ====================================================
            TRACK IDS
            ==================================================== */}

        <div className="incident-track-section">

          <h3>
            Track IDs
          </h3>

          {incident.track_ids &&
          incident.track_ids.length > 0 ? (

            <div className="track-list">

              {incident.track_ids.map(
                (trackId) => (
                  <code key={trackId}>
                    {trackId}
                  </code>
                )
              )}

            </div>

          ) : (

            <p>
              No track IDs available.
            </p>

          )}

        </div>


        {/* ====================================================
            ACTIONS
            ==================================================== */}

        <div className="incident-modal-actions">

          {nextStatus && (
            <button
              onClick={handleStatusUpdate}
            >
              {actionLabel}
            </button>
          )}


          <button
            className="secondary-button"
            onClick={onClose}
          >
            Close
          </button>

        </div>

      </div>

    </div>
  )
}


export default IncidentDetails