// import { API_BASE_URL } from '../config'

// export const CAMERA_STREAM =
//   `${API_BASE_URL}/api/camera/stream`


import { API_BASE_URL } from '../config'

export const getCameraStreamUrl = (cameraId = 'CAM01') =>
  `${API_BASE_URL}/api/cameras/${encodeURIComponent(cameraId)}/stream`

export const CAMERA_STREAM = getCameraStreamUrl('CAM01')