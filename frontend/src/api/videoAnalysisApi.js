// // const API_BASE_URL = 'http://127.0.0.1:8000'

// // export async function uploadRecordedVideo(file) {
// //   const formData = new FormData()

// //   formData.append('file', file)

// //   const response = await fetch(
// //     `${API_BASE_URL}/api/video-analysis/upload`,
// //     {
// //       method: 'POST',
// //       body: formData,
// //     }
// //   )

// //   if (!response.ok) {
// //     throw new Error(
// //       `Video upload failed: ${response.status}`
// //     )
// //   }

// //   return response.json()
// // }

// const API_BASE_URL = 'http://127.0.0.1:8000'

// export async function uploadRecordedVideo(file) {
//   const formData = new FormData()

//   formData.append('file', file)

//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/upload`,
//     {
//       method: 'POST',
//       body: formData,
//     }
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Video upload failed: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export async function analyzeRecordedVideo(
//   videoId
// ) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analyze`,
//     {
//       method: 'POST',
//     }
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Video analysis failed: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export async function getAnalysisStatus(
//   videoId
// ) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analysis`
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Unable to get analysis status: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export function getProofVideoUrl(videoId) {
//   return (
//     `${API_BASE_URL}` +
//     `/api/video-analysis/${videoId}/proof`
//   )
// }











// const API_BASE_URL = 'http://127.0.0.1:8000'

// export async function uploadRecordedVideo(file) {
//   const formData = new FormData()

//   formData.append('file', file)

//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/upload`,
//     {
//       method: 'POST',
//       body: formData,
//     }
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Video upload failed: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export async function analyzeRecordedVideo(videoId) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analyze`,
//     {
//       method: 'POST',
//     }
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Video analysis failed: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export async function getAnalysisStatus(videoId) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analysis`
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Unable to get analysis status: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export function getProofVideoUrl(videoId) {
//   return `${API_BASE_URL}/api/video-analysis/${videoId}/proof`
// }











// const API_BASE_URL = 'http://127.0.0.1:8000'

// export async function uploadRecordedVideo(file) {
//   const formData = new FormData()

//   formData.append('file', file)

//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/upload`,
//     {
//       method: 'POST',
//       body: formData,
//     }
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Video upload failed: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export async function analyzeRecordedVideo(videoId) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analyze`,
//     {
//       method: 'POST',
//     }
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Video analysis failed: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export async function getAnalysisStatus(videoId) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analysis`
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Unable to get analysis status: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export function getProofVideoUrl(videoId) {
//   return `${API_BASE_URL}/api/video-analysis/${videoId}/proof`
// }

// export async function fetchProofVideo(videoId) {
//   const response = await fetch(
//     getProofVideoUrl(videoId)
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Unable to load proof video: ${response.status}`
//     )
//   }

//   const blob = await response.blob()

//   return URL.createObjectURL(blob)
// }






// const API_BASE_URL = 'http://127.0.0.1:8000'

// export async function uploadRecordedVideo(file) {
//   const formData = new FormData()
//   formData.append('file', file)

//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/upload`,
//     {
//       method: 'POST',
//       body: formData,
//     }
//   )

//   if (!response.ok) {
//     throw new Error(`Video upload failed: ${response.status}`)
//   }

//   return response.json()
// }

// export async function analyzeRecordedVideo(videoId) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analyze`,
//     {
//       method: 'POST',
//     }
//   )

//   if (!response.ok) {
//     throw new Error(`Video analysis failed: ${response.status}`)
//   }

//   return response.json()
// }

// export async function getAnalysisStatus(videoId) {
//   const response = await fetch(
//     `${API_BASE_URL}/api/video-analysis/${videoId}/analysis`
//   )

//   if (!response.ok) {
//     throw new Error(
//       `Unable to get analysis status: ${response.status}`
//     )
//   }

//   return response.json()
// }

// export function getProofVideoUrl(videoId) {
//   return `${API_BASE_URL}/api/video-analysis/${videoId}/proof`
// }







const API_BASE_URL = 'http://127.0.0.1:8000'

export async function uploadRecordedVideo(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(
    `${API_BASE_URL}/api/video-analysis/upload`,
    {
      method: 'POST',
      body: formData,
    }
  )

  if (!response.ok) {
    throw new Error(
      `Video upload failed: ${response.status}`
    )
  }

  return response.json()
}

export async function analyzeRecordedVideo(videoId) {
  const response = await fetch(
    `${API_BASE_URL}/api/video-analysis/${videoId}/analyze`,
    {
      method: 'POST',
    }
  )

  if (!response.ok) {
    throw new Error(
      `Video analysis failed: ${response.status}`
    )
  }

  return response.json()
}

export async function getAnalysisStatus(videoId) {
  const response = await fetch(
    `${API_BASE_URL}/api/video-analysis/${videoId}/analysis`
  )

  if (!response.ok) {
    throw new Error(
      `Unable to get analysis status: ${response.status}`
    )
  }

  return response.json()
}

/*
 * Returns the direct backend URL.
 *
 * Useful for:
 * - Open Original
 * - fallback playback
 */
export function getProofVideoUrl(videoId) {
  return `${API_BASE_URL}/api/video-analysis/${videoId}/proof`
}

/*
 * Download the proof video from FastAPI
 * and convert it to a browser Blob URL.
 */
export async function fetchProofVideo(videoId) {
  const response = await fetch(
    `${API_BASE_URL}/api/video-analysis/${videoId}/proof`,
    {
      method: 'GET',
    }
  )

  if (!response.ok) {
    throw new Error(
      `Unable to download proof video: ${response.status}`
    )
  }

  const contentType =
    response.headers.get('content-type') || ''

  if (!contentType.includes('video')) {
    throw new Error(
      'The server did not return a video file.'
    )
  }

  const blob = await response.blob()

  if (!blob.size) {
    throw new Error(
      'The proof video returned by the server is empty.'
    )
  }

  return URL.createObjectURL(blob)
}