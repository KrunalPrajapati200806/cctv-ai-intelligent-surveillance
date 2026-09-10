import { API_BASE_URL } from '../config'

export async function getIncidents() {
  const response = await fetch(
    `${API_BASE_URL}/api/incidents`
  )

  if (!response.ok) {
    throw new Error(
      `API returned ${response.status}`
    )
  }

  const data = await response.json()

  return data.incidents || []
}

export async function updateIncidentStatus(
  incidentId,
  status
) {
  const response = await fetch(
    `${API_BASE_URL}/api/incidents/${incidentId}/status`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        status,
      }),
    }
  )

  if (!response.ok) {
    throw new Error(
      `Status update failed: ${response.status}`
    )
  }

  return await response.json()
}

export async function getIncident(
  incidentId
) {
  const response = await fetch(
    `${API_BASE_URL}/api/incidents/${incidentId}`
  )

  if (!response.ok) {
    throw new Error(
      `Incident fetch failed: ${response.status}`
    )
  }

  return await response.json()
}