export function getNextIncidentStatus(status) {
  if (status === 'OPEN') {
    return 'ACKNOWLEDGED'
  }

  if (status === 'ACKNOWLEDGED') {
    return 'RESOLVED'
  }

  return null
}


export function getNextIncidentActionLabel(status) {
  if (status === 'OPEN') {
    return 'Acknowledge'
  }

  if (status === 'ACKNOWLEDGED') {
    return 'Resolve'
  }

  return null
}