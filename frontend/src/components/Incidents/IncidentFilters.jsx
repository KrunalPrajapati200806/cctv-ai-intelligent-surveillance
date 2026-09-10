function IncidentFilters({
  statusFilter,
  cameraFilter,
  severityFilter,
  cameras,
  onStatusChange,
  onCameraChange,
  onSeverityChange,
}) {
  return (
    <div className="incident-filters">
      <div className="filter-group">
        <label>
          Status
        </label>

        <select
          value={statusFilter}
          onChange={(event) =>
            onStatusChange(
              event.target.value
            )
          }
        >
          <option value="ALL">
            All
          </option>

          <option value="OPEN">
            Open
          </option>

          <option value="ACKNOWLEDGED">
            Acknowledged
          </option>

          <option value="RESOLVED">
            Resolved
          </option>
        </select>
      </div>

      <div className="filter-group">
        <label>
          Camera
        </label>

        <select
          value={cameraFilter}
          onChange={(event) =>
            onCameraChange(
              event.target.value
            )
          }
        >
          <option value="ALL">
            All Cameras
          </option>

          {cameras.map((camera) => (
            <option
              key={camera}
              value={camera}
            >
              {camera}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label>
          Severity
        </label>

        <select
          value={severityFilter}
          onChange={(event) =>
            onSeverityChange(
              event.target.value
            )
          }
        >
          <option value="ALL">
            All
          </option>

          <option value="low">
            Low
          </option>

          <option value="medium">
            Medium
          </option>

          <option value="high">
            High
          </option>
        </select>
      </div>
    </div>
  )
}

export default IncidentFilters