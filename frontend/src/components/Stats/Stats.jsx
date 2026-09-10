import './Stats.css'

function Stats({ incidents }) {
  const openCount = incidents.filter(
    (incident) =>
      incident.status === 'OPEN'
  ).length

  const acknowledgedCount = incidents.filter(
    (incident) =>
      incident.status === 'ACKNOWLEDGED'
  ).length

  const resolvedCount = incidents.filter(
    (incident) =>
      incident.status === 'RESOLVED'
  ).length

  return (
    <section className="stats">
      <div className="stat-card">
        <span>Total Incidents</span>
        <strong>{incidents.length}</strong>
      </div>

      <div className="stat-card danger">
        <span>Open</span>
        <strong>{openCount}</strong>
      </div>

      <div className="stat-card warning">
        <span>Acknowledged</span>
        <strong>{acknowledgedCount}</strong>
      </div>

      <div className="stat-card success">
        <span>Resolved</span>
        <strong>{resolvedCount}</strong>
      </div>
    </section>
  )
}

export default Stats