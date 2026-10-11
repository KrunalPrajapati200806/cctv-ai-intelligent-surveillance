import { useEffect, useState } from 'react'

import { API_BASE_URL } from '../../config'
import './CameraRuntime.css'

const apiUrl = (path) => `${API_BASE_URL || ''}${path}`

function CameraRuntime() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  async function loadCameras() {
    try {
      const response = await fetch(apiUrl('/api/cameras'))
      if (!response.ok) throw new Error(`Camera API returned ${response.status}`)
      const records = await response.json()
      const health = await Promise.all(
        records.map(async (camera) => {
          const healthResponse = await fetch(
            apiUrl(`/api/cameras/${encodeURIComponent(camera.camera_id)}/health`),
          )
          return healthResponse.ok
            ? { ...camera, ...(await healthResponse.json()) }
            : camera
        }),
      )
      setCameras(health)
      setError('')
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCameras()
    const timer = window.setInterval(loadCameras, 5000)
    return () => window.clearInterval(timer)
  }, [])

  async function runAction(cameraId, action) {
    setBusyId(cameraId)
    try {
      const response = await fetch(
        apiUrl(`/api/cameras/${encodeURIComponent(cameraId)}/${action}`),
        { method: 'POST' },
      )
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Unable to ${action} camera`)
      }
      await loadCameras()
    } catch (actionError) {
      setError(actionError.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="camera-runtime" aria-labelledby="camera-runtime-title">
      <div className="camera-runtime__heading">
        <div>
          <p className="eyebrow">Runtime</p>
          <h2 id="camera-runtime-title">Camera operations</h2>
        </div>
        <button className="camera-runtime__refresh" onClick={loadCameras} title="Refresh camera health">
          Refresh
        </button>
      </div>

      {error && <p className="camera-runtime__error">{error}</p>}
      {loading && <p className="camera-runtime__empty">Loading camera health...</p>}
      {!loading && !cameras.length && <p className="camera-runtime__empty">No cameras registered.</p>}

      <div className="camera-runtime__grid">
        {cameras.map((camera) => {
          const status = camera.status || 'REGISTERED'
          const busy = busyId === camera.camera_id
          return (
            <article className="camera-card" key={camera.camera_id}>
              <div className="camera-card__topline">
                <div>
                  <span className="camera-card__id">{camera.camera_id}</span>
                  <h3>{camera.name}</h3>
                </div>
                <span className={`camera-status camera-status--${status.toLowerCase()}`}>
                  <span aria-hidden="true" />{status}
                </span>
              </div>
              <dl className="camera-card__metrics">
                <div><dt>Source</dt><dd>{camera.source_type || 'unknown'}</dd></div>
                <div><dt>Location</dt><dd>{camera.location}</dd></div>
                <div><dt>Restarts</dt><dd>{camera.restart_count ?? 0}</dd></div>
                <div><dt>Heartbeat</dt><dd>{camera.last_heartbeat ? 'recent' : 'waiting'}</dd></div>
              </dl>
              <div className="camera-card__actions">
                <button disabled={busy} onClick={() => runAction(camera.camera_id, 'start')}>Start</button>
                <button disabled={busy} onClick={() => runAction(camera.camera_id, 'restart')}>Restart</button>
                <button disabled={busy} onClick={() => runAction(camera.camera_id, 'stop')}>Stop</button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export default CameraRuntime
