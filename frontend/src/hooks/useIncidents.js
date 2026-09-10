import { useCallback, useEffect, useState } from 'react'

import {
  getIncidents,
  updateIncidentStatus,
} from '../api/incidentsApi'


function useIncidents() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')


  // ============================================================
  // LOAD INCIDENTS
  // ============================================================

  const loadIncidents = useCallback(async () => {
    try {
      setError('')

      const data = await getIncidents()

      setIncidents(data)
    } catch (err) {
      setError(
        err.message ||
          'Unable to connect to backend'
      )
    } finally {
      setLoading(false)
    }
  }, [])


  // ============================================================
  // UPDATE INCIDENT STATUS
  // ============================================================

  const updateStatus = useCallback(
    async (incidentId, status) => {
      try {
        setError('')

        await updateIncidentStatus(
          incidentId,
          status
        )

        await loadIncidents()
      } catch (err) {
        setError(
          err.message ||
            'Unable to update incident'
        )
      }
    },
    [loadIncidents]
  )


  // ============================================================
  // INITIAL LOAD + AUTO REFRESH
  // ============================================================

  useEffect(() => {
    loadIncidents()

    const timer = setInterval(() => {
      loadIncidents()
    }, 5000)

    return () => {
      clearInterval(timer)
    }
  }, [loadIncidents])


  return {
    incidents,
    loading,
    error,
    loadIncidents,
    updateStatus,
  }
}


export default useIncidents