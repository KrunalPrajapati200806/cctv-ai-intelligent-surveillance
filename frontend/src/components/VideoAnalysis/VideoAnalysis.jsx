// // import { useState } from 'react'
// // import './VideoAnalysis.css'

// // const API_BASE_URL = 'http://127.0.0.1:8000'

// // function VideoAnalysis() {
// //   const [file, setFile] = useState(null)
// //   const [uploading, setUploading] = useState(false)
// //   const [result, setResult] = useState(null)
// //   const [error, setError] = useState('')

// //   function handleFileChange(event) {
// //     const selectedFile = event.target.files?.[0]

// //     if (!selectedFile) {
// //       return
// //     }

// //     setFile(selectedFile)
// //     setResult(null)
// //     setError('')
// //   }

// //   async function handleUpload() {
// //     if (!file) {
// //       setError('Please select a video first.')
// //       return
// //     }

// //     try {
// //       setUploading(true)
// //       setError('')
// //       setResult(null)

// //       const formData = new FormData()
// //       formData.append('file', file)

// //       const response = await fetch(
// //         `${API_BASE_URL}/api/video-analysis/upload`,
// //         {
// //           method: 'POST',
// //           body: formData,
// //         }
// //       )

// //       if (!response.ok) {
// //         throw new Error(
// //           `Upload failed: ${response.status}`
// //         )
// //       }

// //       const data = await response.json()

// //       setResult(data)
// //     } catch (err) {
// //       setError(
// //         err.message || 'Unable to upload video.'
// //       )
// //     } finally {
// //       setUploading(false)
// //     }
// //   }

// //   return (
// //     <section className="video-analysis">
// //       <div className="video-analysis-header">
// //         <div>
// //           <h2>Recorded Video Analysis</h2>
// //           <span>
// //             Upload recorded CCTV footage for AI analysis
// //           </span>
// //         </div>
// //       </div>

// //       <div className="video-upload-card">
// //         <input
// //           type="file"
// //           accept="video/*"
// //           onChange={handleFileChange}
// //         />

// //         {file && (
// //           <div className="selected-video">
// //             <strong>Selected video:</strong>{' '}
// //             {file.name}
// //           </div>
// //         )}

// //         <button
// //           onClick={handleUpload}
// //           disabled={!file || uploading}
// //         >
// //           {uploading
// //             ? 'Uploading...'
// //             : 'Upload Video'}
// //         </button>

// //         {error && (
// //           <div className="video-error">
// //             {error}
// //           </div>
// //         )}

// //         {result && (
// //           <div className="upload-success">
// //             <strong>Video uploaded successfully</strong>

// //             <div>
// //               Video ID: {result.video_id}
// //             </div>

// //             <div>
// //               Status: {result.status}
// //             </div>

// //             <div>
// //               Filename: {result.filename}
// //             </div>
// //           </div>
// //         )}
// //       </div>
// //     </section>
// //   )
// // }

// // export default VideoAnalysis























// // import { useEffect, useRef, useState } from 'react'

// // import {
// //   uploadRecordedVideo,
// //   analyzeRecordedVideo,
// //   getAnalysisStatus,
// //   getProofVideoUrl,
// // } from '../../api/videoAnalysisApi'

// // import './VideoAnalysis.css'

// // function VideoAnalysis() {
// //   const [file, setFile] = useState(null)
// //   const [uploading, setUploading] = useState(false)
// //   const [analyzing, setAnalyzing] = useState(false)
// //   const [result, setResult] = useState(null)
// //   const [analysis, setAnalysis] = useState(null)
// //   const [error, setError] = useState('')

// //   const pollRef = useRef(null)

// //   function handleFileChange(event) {
// //     const selectedFile = event.target.files?.[0]

// //     if (!selectedFile) {
// //       return
// //     }

// //     setFile(selectedFile)
// //     setResult(null)
// //     setAnalysis(null)
// //     setError('')
// //     setAnalyzing(false)
// //   }

// //   async function handleUpload() {
// //     if (!file) {
// //       setError('Please select a video first.')
// //       return
// //     }

// //     try {
// //       setUploading(true)
// //       setError('')
// //       setResult(null)
// //       setAnalysis(null)
// //       setAnalyzing(false)

// //       const data = await uploadRecordedVideo(file)

// //       setResult(data)
// //     } catch (err) {
// //       setError(
// //         err.message || 'Unable to upload video.'
// //       )
// //     } finally {
// //       setUploading(false)
// //     }
// //   }

// //   async function handleAnalyze() {
// //     if (!result?.video_id) {
// //       setError('Please upload a video first.')
// //       return
// //     }

// //     try {
// //       setAnalyzing(true)
// //       setError('')
// //       setAnalysis(null)

// //       await analyzeRecordedVideo(result.video_id)

// //       await checkAnalysisStatus(result.video_id)
// //     } catch (err) {
// //       setAnalyzing(false)

// //       setError(
// //         err.message || 'Unable to start video analysis.'
// //       )
// //     }
// //   }

// //   async function checkAnalysisStatus(videoId) {
// //     try {
// //       const data = await getAnalysisStatus(videoId)

// //       setAnalysis(data)

// //       if (data.status === 'COMPLETED') {
// //         setAnalyzing(false)
// //         return
// //       }

// //       if (data.status === 'FAILED') {
// //         setAnalyzing(false)

// //         setError(
// //           data.message || 'Video analysis failed.'
// //         )

// //         return
// //       }

// //       pollRef.current = setTimeout(() => {
// //         checkAnalysisStatus(videoId)
// //       }, 2000)
// //     } catch (err) {
// //       setAnalyzing(false)

// //       setError(
// //         err.message || 'Unable to check analysis status.'
// //       )
// //     }
// //   }

// //   useEffect(() => {
// //     return () => {
// //       if (pollRef.current) {
// //         clearTimeout(pollRef.current)
// //       }
// //     }
// //   }, [])

// //   return (
// //     <section className="video-analysis">
// //       <div className="video-analysis-header">
// //         <div>
// //           <h1>Recorded Video Analysis</h1>

// //           <p>
// //             Upload recorded CCTV footage
// //             for AI-powered analysis.
// //           </p>
// //         </div>
// //       </div>

// //       <div className="video-upload-card">
// //         <input
// //           type="file"
// //           accept="video/*"
// //           onChange={handleFileChange}
// //         />

// //         {file && (
// //           <div className="selected-video">
// //             <strong>Selected video:</strong>{' '}
// //             {file.name}
// //           </div>
// //         )}

// //         <button
// //           onClick={handleUpload}
// //           disabled={!file || uploading}
// //         >
// //           {uploading
// //             ? 'Uploading...'
// //             : 'Upload Video'}
// //         </button>

// //         {error && (
// //           <div className="video-error">
// //             {error}
// //           </div>
// //         )}

// //         {result && (
// //           <div className="upload-success">
// //             <h3>
// //               Video uploaded successfully
// //             </h3>

// //             <div>
// //               <strong>Video ID:</strong>{' '}
// //               {result.video_id}
// //             </div>

// //             <div>
// //               <strong>Status:</strong>{' '}
// //               {result.status}
// //             </div>

// //             <div>
// //               <strong>Filename:</strong>{' '}
// //               {result.filename}
// //             </div>

// //             <button
// //               onClick={handleAnalyze}
// //               disabled={analyzing}
// //             >
// //               {analyzing
// //                 ? 'Analysis Running...'
// //                 : 'Start AI Analysis'}
// //             </button>
// //           </div>
// //         )}
// //       </div>

// //       {analysis && (
// //         <div className="analysis-result">
// //           <h2>Analysis Result</h2>

// //           <div className="analysis-status">
// //             <strong>Status:</strong>{' '}
// //             {analysis.status}
// //           </div>

// //           <div className="analysis-progress">
// //             <strong>Progress:</strong>{' '}
// //             {analysis.progress ?? 0}%
// //           </div>

// //           {analysis.message && (
// //             <p>{analysis.message}</p>
// //           )}

// //           {analysis.status === 'COMPLETED' && (
// //             <>
// //               <div className="analysis-stats">
// //                 <div>
// //                   <strong>
// //                     Total Frames
// //                   </strong>

// //                   <span>
// //                     {analysis.total_frames}
// //                   </span>
// //                 </div>

// //                 <div>
// //                   <strong>
// //                     Processed Frames
// //                   </strong>

// //                   <span>
// //                     {analysis.processed_frames}
// //                   </span>
// //                 </div>

// //                 <div>
// //                   <strong>
// //                     Frames With People
// //                   </strong>

// //                   <span>
// //                     {analysis.frames_with_people}
// //                   </span>
// //                 </div>

// //                 <div>
// //                   <strong>
// //                     Person Detections
// //                   </strong>

// //                   <span>
// //                     {analysis.total_person_detections}
// //                   </span>
// //                 </div>
// //               </div>

// //               {analysis.event && (
// //                 <div className="detected-event">
// //                   <h3>
// //                     Detected Event
// //                   </h3>

// //                   <div>
// //                     <strong>Event:</strong>{' '}
// //                     {analysis.event.type}
// //                   </div>

// //                   <div>
// //                     <strong>Time:</strong>{' '}
// //                     {analysis.event.time}s
// //                   </div>

// //                   <div>
// //                     <strong>Score:</strong>{' '}
// //                     {analysis.event.score}
// //                   </div>

// //                   <div>
// //                     <strong>Before:</strong>{' '}
// //                     {analysis.event.before_person_count}{' '}
// //                     people
// //                   </div>

// //                   <div>
// //                     <strong>After:</strong>{' '}
// //                     {analysis.event.after_person_count}{' '}
// //                     people
// //                   </div>

// //                   {analysis.event.change !== undefined && (
// //                     <div>
// //                       <strong>Change:</strong>{' '}
// //                       {analysis.event.change}
// //                     </div>
// //                   )}
// //                 </div>
// //               )}

// //               <div className="proof-video">
// //                 <h3>
// //                   Proof Video
// //                 </h3>

// //                 <video
// //                   controls
// //                   src={getProofVideoUrl(
// //                     result.video_id
// //                   )}
// //                   width="100%"
// //                 />

// //                 <a
// //                   href={getProofVideoUrl(
// //                     result.video_id
// //                   )}
// //                   target="_blank"
// //                   rel="noreferrer"
// //                 >
// //                   Open Proof Video
// //                 </a>
// //               </div>
// //             </>
// //           )}
// //         </div>
// //       )}
// //     </section>
// //   )
// // }

// // export default VideoAnalysis















// import {
//   useEffect,
//   useRef,
//   useState,
// } from 'react'

// import {
//   uploadRecordedVideo,
//   analyzeRecordedVideo,
//   getAnalysisStatus,
//   fetchProofVideo,
//   getProofVideoUrl,
// } from '../../api/videoAnalysisApi'

// import './VideoAnalysis.css'

// function VideoAnalysis() {
//   const [file, setFile] = useState(null)

//   const [uploading, setUploading] =
//     useState(false)

//   const [analyzing, setAnalyzing] =
//     useState(false)

//   const [result, setResult] =
//     useState(null)

//   const [analysis, setAnalysis] =
//     useState(null)

//   const [proofVideoUrl, setProofVideoUrl] =
//     useState('')

//   const [videoLoading, setVideoLoading] =
//     useState(false)

//   const [error, setError] =
//     useState('')

//   const pollRef = useRef(null)

//   // --------------------------------
//   // File selection
//   // --------------------------------

//   function handleFileChange(event) {
//     const selectedFile =
//       event.target.files?.[0]

//     if (!selectedFile) {
//       return
//     }

//     setFile(selectedFile)
//     setResult(null)
//     setAnalysis(null)
//     setError('')

//     if (proofVideoUrl) {
//       URL.revokeObjectURL(proofVideoUrl)
//       setProofVideoUrl('')
//     }
//   }

//   // --------------------------------
//   // Upload
//   // --------------------------------

//   async function handleUpload() {
//     if (!file) {
//       setError(
//         'Please select a video first.'
//       )
//       return
//     }

//     try {
//       setUploading(true)
//       setError('')
//       setResult(null)
//       setAnalysis(null)

//       const data =
//         await uploadRecordedVideo(file)

//       setResult(data)

//     } catch (err) {
//       setError(
//         err.message ||
//           'Unable to upload video.'
//       )
//     } finally {
//       setUploading(false)
//     }
//   }

//   // --------------------------------
//   // Start analysis
//   // --------------------------------

//   async function handleAnalyze() {
//     if (!result?.video_id) {
//       setError(
//         'Please upload a video first.'
//       )
//       return
//     }

//     try {
//       setAnalyzing(true)
//       setError('')
//       setAnalysis(null)

//       await analyzeRecordedVideo(
//         result.video_id
//       )

//       await checkAnalysisStatus(
//         result.video_id
//       )

//     } catch (err) {
//       setAnalyzing(false)

//       setError(
//         err.message ||
//           'Unable to start video analysis.'
//       )
//     }
//   }

//   // --------------------------------
//   // Poll analysis status
//   // --------------------------------

//   async function checkAnalysisStatus(
//     videoId
//   ) {
//     try {
//       const data =
//         await getAnalysisStatus(
//           videoId
//         )

//       setAnalysis(data)

//       if (data.status === 'COMPLETED') {
//         setAnalyzing(false)

//         await loadProofVideo(
//           videoId
//         )

//         return
//       }

//       if (data.status === 'FAILED') {
//         setAnalyzing(false)

//         setError(
//           data.message ||
//             'Video analysis failed.'
//         )

//         return
//       }

//       pollRef.current =
//         setTimeout(() => {
//           checkAnalysisStatus(videoId)
//         }, 2000)

//     } catch (err) {
//       setAnalyzing(false)

//       setError(
//         err.message ||
//           'Unable to check analysis status.'
//       )
//     }
//   }

//   // --------------------------------
//   // Load proof video
//   // --------------------------------

//   async function loadProofVideo(
//     videoId
//   ) {
//     try {
//       setVideoLoading(true)
//       setError('')

//       const objectUrl =
//         await fetchProofVideo(
//           videoId
//         )

//       setProofVideoUrl(objectUrl)

//     } catch (err) {
//       setError(
//         err.message ||
//           'Unable to load proof video.'
//       )
//     } finally {
//       setVideoLoading(false)
//     }
//   }

//   // --------------------------------
//   // Cleanup
//   // --------------------------------

//   useEffect(() => {
//     return () => {
//       if (pollRef.current) {
//         clearTimeout(
//           pollRef.current
//         )
//       }

//       if (proofVideoUrl) {
//         URL.revokeObjectURL(
//           proofVideoUrl
//         )
//       }
//     }
//   }, [proofVideoUrl])

//   // --------------------------------
//   // UI
//   // --------------------------------

//   return (
//     <section className="video-analysis-page">

//       {/* Header */}

//       <div className="video-page-header">

//         <div>
//           <span className="eyebrow">
//             AI SECURITY
//           </span>

//           <h1>
//             Recorded Video Analysis
//           </h1>

//           <p>
//             Upload recorded CCTV footage
//             and let AI detect unusual
//             activity.
//           </p>
//         </div>

//         {analysis?.status ===
//           'COMPLETED' && (
//           <div className="analysis-complete-badge">
//             ● ANALYSIS COMPLETE
//           </div>
//         )}

//       </div>


//       {/* Upload Card */}

//       <div className="video-upload-card">

//         <div className="card-header">

//           <div>
//             <h2>
//               Upload CCTV Footage
//             </h2>

//             <p>
//               MP4, MOV or other supported
//               video formats
//             </p>
//           </div>

//         </div>


//         {/* File input */}

//         <label className="file-drop-zone">

//           <input
//             type="file"
//             accept="video/*"
//             onChange={handleFileChange}
//           />

//           <div className="upload-icon">
//             ↑
//           </div>

//           <strong>
//             {file
//               ? file.name
//               : 'Choose a CCTV video'}
//           </strong>

//           <span>
//             Click to browse files
//           </span>

//         </label>


//         {/* Selected file */}

//         {file && (
//           <div className="selected-file">

//             <div className="file-icon">
//               MP4
//             </div>

//             <div className="file-info">

//               <strong>
//                 {file.name}
//               </strong>

//               <span>
//                 {(
//                   file.size /
//                   1024 /
//                   1024
//                 ).toFixed(2)} MB
//               </span>

//             </div>

//             <span className="file-ready">
//               READY
//             </span>

//           </div>
//         )}


//         {/* Upload button */}

//         <button
//           className="primary-button"
//           onClick={handleUpload}
//           disabled={
//             !file || uploading
//           }
//         >
//           {uploading
//             ? 'Uploading...'
//             : 'Upload Video'}
//         </button>


//         {/* Upload success */}

//         {result && (
//           <div className="upload-result">

//             <div className="success-icon">
//               ✓
//             </div>

//             <div>

//               <strong>
//                 Video uploaded successfully
//               </strong>

//               <span>
//                 {result.filename}
//               </span>

//             </div>

//             <span className="status-pill">
//               {result.status}
//             </span>

//           </div>
//         )}

//       </div>


//       {/* Start Analysis */}

//       {result && !analysis && (
//         <div className="start-analysis-card">

//           <div>
//             <span className="eyebrow">
//               NEXT STEP
//             </span>

//             <h2>
//               Run AI Detection
//             </h2>

//             <p>
//               Analyze the uploaded footage
//               for unusual movement and
//               security events.
//             </p>
//           </div>

//           <button
//             className="analyze-button"
//             onClick={handleAnalyze}
//             disabled={analyzing}
//           >

//             {analyzing ? (
//               <>
//                 <span className="spinner" />
//                 Analysis Running...
//               </>
//             ) : (
//               <>
//                 ▶ Start AI Analysis
//               </>
//             )}

//           </button>

//         </div>
//       )}


//       {/* Error */}

//       {error && (
//         <div className="video-error">
//           <strong>
//             Analysis Error
//           </strong>

//           <span>
//             {error}
//           </span>
//         </div>
//       )}


//       {/* Analysis Result */}

//       {analysis && (
//         <div className="analysis-result">

//           {/* Result header */}

//           <div className="result-header">

//             <div>
//               <span className="eyebrow">
//                 AI ANALYSIS
//               </span>

//               <h2>
//                 Analysis Result
//               </h2>
//             </div>

//             <div
//               className={`result-status ${
//                 analysis.status?.toLowerCase()
//               }`}
//             >
//               {analysis.status}
//             </div>

//           </div>


//           {/* Progress */}

//           {analysis.status !==
//             'COMPLETED' && (

//             <div className="progress-section">

//               <div className="progress-label">

//                 <span>
//                   Processing video
//                 </span>

//                 <strong>
//                   {analysis.progress ?? 0}%
//                 </strong>

//               </div>

//               <div className="progress-bar">

//                 <div
//                   className="progress-fill"
//                   style={{
//                     width: `${
//                       analysis.progress ??
//                       0
//                     }%`,
//                   }}
//                 />

//               </div>

//             </div>
//           )}


//           {/* Completed stats */}

//           {analysis.status ===
//             'COMPLETED' && (

//             <>

//               <div className="analysis-stats">

//                 <div className="metric-card">

//                   <span>
//                     TOTAL FRAMES
//                   </span>

//                   <strong>
//                     {analysis.total_frames}
//                   </strong>

//                 </div>


//                 <div className="metric-card">

//                   <span>
//                     PROCESSED
//                   </span>

//                   <strong>
//                     {analysis.processed_frames}
//                   </strong>

//                 </div>


//                 <div className="metric-card">

//                   <span>
//                     FRAMES WITH PEOPLE
//                   </span>

//                   <strong>
//                     {analysis.frames_with_people}
//                   </strong>

//                 </div>


//                 <div className="metric-card">

//                   <span>
//                     PERSON DETECTIONS
//                   </span>

//                   <strong>
//                     {
//                       analysis.total_person_detections
//                     }
//                   </strong>

//                 </div>

//               </div>


//               {/* Detected event */}

//               {analysis.event && (

//                 <div className="detected-event">

//                   <div className="event-header">

//                     <div>
//                       <span className="eyebrow">
//                         DETECTION
//                       </span>

//                       <h3>
//                         Suspicious Event
//                       </h3>
//                     </div>

//                     <span className="event-score">
//                       SCORE {analysis.event.score}
//                     </span>

//                   </div>


//                   <div className="event-type">

//                     {analysis.event.type}

//                   </div>


//                   <div className="event-grid">

//                     <div>
//                       <span>
//                         DETECTION TIME
//                       </span>

//                       <strong>
//                         {analysis.event.time}s
//                       </strong>
//                     </div>


//                     <div>
//                       <span>
//                         BEFORE
//                       </span>

//                       <strong>
//                         {
//                           analysis.event
//                             .before_person_count
//                         } people
//                       </strong>
//                     </div>


//                     <div>
//                       <span>
//                         AFTER
//                       </span>

//                       <strong>
//                         {
//                           analysis.event
//                             .after_person_count
//                         } people
//                       </strong>
//                     </div>


//                     <div>
//                       <span>
//                         CHANGE
//                       </span>

//                       <strong className="change-negative">
//                         {analysis.event.change}
//                       </strong>
//                     </div>

//                   </div>

//                 </div>

//               )}


//               {/* Proof video */}

//               <div className="proof-video-card">

//                 <div className="proof-header">

//                   <div>

//                     <span className="eyebrow">
//                       EVIDENCE
//                     </span>

//                     <h3>
//                       Proof Video
//                     </h3>

//                     <p>
//                       AI-generated clip around
//                       the detected event.
//                     </p>

//                   </div>

//                   {analysis.proof_duration && (
//                     <span className="duration-pill">
//                       {analysis.proof_duration}s clip
//                     </span>
//                   )}

//                 </div>


//                 {/* Video */}

//                 <div className="video-player">

//                   {videoLoading ? (

//                     <div className="video-loading">

//                       <div className="large-spinner" />

//                       <strong>
//                         Loading proof video...
//                       </strong>

//                       <span>
//                         Preparing evidence for playback
//                       </span>

//                     </div>

//                   ) : proofVideoUrl ? (

//                     <video
//                       controls
//                       preload="metadata"
//                       playsInline
//                       src={proofVideoUrl}
//                       onError={() =>
//                         setError(
//                           'The proof video could not be played in the browser.'
//                         )
//                       }
//                     >
//                       Your browser does not
//                       support video playback.
//                     </video>

//                   ) : (

//                     <div className="video-empty">

//                       <span>
//                         No proof video loaded
//                       </span>

//                     </div>

//                   )}

//                 </div>


//                 {/* Video actions */}

//                 {proofVideoUrl && (

//                   <div className="video-actions">

//                     <a
//                       className="secondary-button"
//                       href={proofVideoUrl}
//                       download={`${result?.filename || 'proof'}_proof.mp4`}
//                     >
//                       ↓ Download Evidence
//                     </a>

//                     <a
//                       className="secondary-button"
//                       href={getProofVideoUrl(
//                         result.video_id
//                       )}
//                       target="_blank"
//                       rel="noreferrer"
//                     >
//                       ↗ Open Original
//                     </a>

//                   </div>

//                 )}

//               </div>

//             </>
//           )}

//         </div>
//       )}

//     </section>
//   )
// }

// export default VideoAnalysis


















import {
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  uploadRecordedVideo,
  analyzeRecordedVideo,
  getAnalysisStatus,
  fetchProofVideo,
  getProofVideoUrl,
} from '../../api/videoAnalysisApi'

import './VideoAnalysis.css'

function VideoAnalysis() {
  const [file, setFile] = useState(null)

  const [uploading, setUploading] =
    useState(false)

  const [analyzing, setAnalyzing] =
    useState(false)

  const [result, setResult] =
    useState(null)

  const [analysis, setAnalysis] =
    useState(null)

  const [proofVideoUrl, setProofVideoUrl] =
    useState('')

  const [videoLoading, setVideoLoading] =
    useState(false)

  const [videoError, setVideoError] =
    useState('')

  const [error, setError] =
    useState('')

  const pollRef = useRef(null)

  // --------------------------------------------------
  // File selection
  // --------------------------------------------------

  function handleFileChange(event) {
    const selectedFile =
      event.target.files?.[0]

    if (!selectedFile) {
      return
    }

    // Clear previous polling
    if (pollRef.current) {
      clearTimeout(pollRef.current)
      pollRef.current = null
    }

    // Revoke old blob URL
    if (proofVideoUrl) {
      URL.revokeObjectURL(proofVideoUrl)
    }

    setFile(selectedFile)
    setResult(null)
    setAnalysis(null)
    setProofVideoUrl('')
    setVideoError('')
    setError('')
    setAnalyzing(false)
  }

  // --------------------------------------------------
  // Upload
  // --------------------------------------------------

  async function handleUpload() {
    if (!file) {
      setError('Please select a video first.')
      return
    }

    try {
      setUploading(true)
      setError('')
      setVideoError('')
      setResult(null)
      setAnalysis(null)

      const data =
        await uploadRecordedVideo(file)

      setResult(data)
    } catch (err) {
      setError(
        err.message ||
          'Unable to upload video.'
      )
    } finally {
      setUploading(false)
    }
  }

  // --------------------------------------------------
  // Start AI analysis
  // --------------------------------------------------

  async function handleAnalyze() {
    if (!result?.video_id) {
      setError(
        'Please upload a video first.'
      )
      return
    }

    try {
      setAnalyzing(true)
      setError('')
      setVideoError('')
      setAnalysis(null)

      await analyzeRecordedVideo(
        result.video_id
      )

      await checkAnalysisStatus(
        result.video_id
      )
    } catch (err) {
      setAnalyzing(false)

      setError(
        err.message ||
          'Unable to start video analysis.'
      )
    }
  }

  // --------------------------------------------------
  // Poll analysis status
  // --------------------------------------------------

  async function checkAnalysisStatus(videoId) {
    try {
      const data =
        await getAnalysisStatus(videoId)

      setAnalysis(data)

      if (data.status === 'COMPLETED') {
        setAnalyzing(false)

        await loadProofVideo(videoId)

        return
      }

      if (data.status === 'FAILED') {
        setAnalyzing(false)

        setError(
          data.message ||
            'Video analysis failed.'
        )

        return
      }

      pollRef.current =
        setTimeout(() => {
          checkAnalysisStatus(videoId)
        }, 2000)
    } catch (err) {
      setAnalyzing(false)

      setError(
        err.message ||
          'Unable to check analysis status.'
      )
    }
  }

  // --------------------------------------------------
  // Load proof video
  // --------------------------------------------------

  async function loadProofVideo(videoId) {
    try {
      setVideoLoading(true)
      setVideoError('')
      setError('')

      const objectUrl =
        await fetchProofVideo(videoId)

      setProofVideoUrl(objectUrl)
    } catch (err) {
      setVideoError(
        err.message ||
          'Unable to load proof video.'
      )
    } finally {
      setVideoLoading(false)
    }
  }

  // --------------------------------------------------
  // Cleanup
  // --------------------------------------------------

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearTimeout(pollRef.current)
      }

      if (proofVideoUrl) {
        URL.revokeObjectURL(
          proofVideoUrl
        )
      }
    }
  }, [proofVideoUrl])

  // --------------------------------------------------
  // UI
  // --------------------------------------------------

  return (
    <section className="video-analysis-page">

      {/* HEADER */}

      <div className="video-page-header">
        <div>
          <span className="eyebrow">
            AI SECURITY
          </span>

          <h1>
            Recorded Video Analysis
          </h1>

          <p>
            Upload recorded CCTV footage
            and let AI detect unusual
            activity.
          </p>
        </div>

        {analysis?.status ===
          'COMPLETED' && (
          <div className="analysis-complete-badge">
            ● ANALYSIS COMPLETE
          </div>
        )}
      </div>

      {/* UPLOAD */}

      <div className="video-upload-card">

        <div className="card-header">
          <div>
            <h2>
              Upload CCTV Footage
            </h2>

            <p>
              MP4, MOV or other supported
              video formats
            </p>
          </div>
        </div>

        <label className="file-drop-zone">

          <input
            type="file"
            accept="video/*"
            onChange={handleFileChange}
          />

          <div className="upload-icon">
            ↑
          </div>

          <strong>
            {file
              ? file.name
              : 'Choose a CCTV video'}
          </strong>

          <span>
            Click to browse files
          </span>

        </label>

        {file && (
          <div className="selected-file">

            <div className="file-icon">
              MP4
            </div>

            <div className="file-info">
              <strong>
                {file.name}
              </strong>

              <span>
                {(
                  file.size /
                  1024 /
                  1024
                ).toFixed(2)} MB
              </span>
            </div>

            <span className="file-ready">
              READY
            </span>

          </div>
        )}

        <button
          className="primary-button"
          onClick={handleUpload}
          disabled={
            !file || uploading
          }
        >
          {uploading
            ? 'Uploading...'
            : 'Upload Video'}
        </button>

        {result && (
          <div className="upload-result">

            <div className="success-icon">
              ✓
            </div>

            <div>
              <strong>
                Video uploaded successfully
              </strong>

              <span>
                {result.filename}
              </span>
            </div>

            <span className="status-pill">
              {result.status}
            </span>

          </div>
        )}

      </div>

      {/* START ANALYSIS */}

      {result && !analysis && (
        <div className="start-analysis-card">

          <div>
            <span className="eyebrow">
              NEXT STEP
            </span>

            <h2>
              Run AI Detection
            </h2>

            <p>
              Analyze the uploaded footage
              for unusual movement and
              security events.
            </p>
          </div>

          <button
            className="analyze-button"
            onClick={handleAnalyze}
            disabled={analyzing}
          >
            {analyzing ? (
              <>
                <span className="spinner" />
                Analysis Running...
              </>
            ) : (
              <>
                ▶ Start AI Analysis
              </>
            )}
          </button>

        </div>
      )}

      {/* GENERAL ERROR */}

      {error && (
        <div className="video-error">
          <strong>
            Analysis Error
          </strong>

          <span>
            {error}
          </span>
        </div>
      )}

      {/* ANALYSIS */}

      {analysis && (
        <div className="analysis-result">

          <div className="result-header">

            <div>
              <span className="eyebrow">
                AI ANALYSIS
              </span>

              <h2>
                Analysis Result
              </h2>
            </div>

            <div
              className={`result-status ${
                analysis.status?.toLowerCase()
              }`}
            >
              {analysis.status}
            </div>

          </div>

          {/* PROGRESS */}

          {analysis.status !==
            'COMPLETED' && (

            <div className="progress-section">

              <div className="progress-label">
                <span>
                  Processing video
                </span>

                <strong>
                  {analysis.progress ?? 0}%
                </strong>
              </div>

              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${
                      analysis.progress ??
                      0
                    }%`,
                  }}
                />
              </div>

            </div>
          )}

          {/* COMPLETED */}

          {analysis.status ===
            'COMPLETED' && (

            <>

              {/* STATS */}

              <div className="analysis-stats">

                <div className="metric-card">
                  <span>
                    TOTAL FRAMES
                  </span>

                  <strong>
                    {analysis.total_frames}
                  </strong>
                </div>

                <div className="metric-card">
                  <span>
                    PROCESSED
                  </span>

                  <strong>
                    {analysis.processed_frames}
                  </strong>
                </div>

                <div className="metric-card">
                  <span>
                    FRAMES WITH PEOPLE
                  </span>

                  <strong>
                    {analysis.frames_with_people}
                  </strong>
                </div>

                <div className="metric-card">
                  <span>
                    PERSON DETECTIONS
                  </span>

                  <strong>
                    {
                      analysis.total_person_detections
                    }
                  </strong>
                </div>

              </div>

              {/* EVENT */}

              {analysis.event && (

                <div className="detected-event">

                  <div className="event-header">

                    <div>
                      <span className="eyebrow">
                        DETECTION
                      </span>

                      <h3>
                        Suspicious Event
                      </h3>
                    </div>

                    <span className="event-score">
                      SCORE {analysis.event.score}
                    </span>

                  </div>

                  <div className="event-type">
                    {analysis.event.type}
                  </div>

                  <div className="event-grid">

                    <div>
                      <span>
                        DETECTION TIME
                      </span>

                      <strong>
                        {analysis.event.time}s
                      </strong>
                    </div>

                    <div>
                      <span>
                        BEFORE
                      </span>

                      <strong>
                        {
                          analysis.event
                            .before_person_count
                        }{' '}
                        people
                      </strong>
                    </div>

                    <div>
                      <span>
                        AFTER
                      </span>

                      <strong>
                        {
                          analysis.event
                            .after_person_count
                        }{' '}
                        people
                      </strong>
                    </div>

                    <div>
                      <span>
                        CHANGE
                      </span>

                      <strong className="change-negative">
                        {analysis.event.change}
                      </strong>
                    </div>

                  </div>

                </div>
              )}

              {/* PROOF VIDEO */}

              <div className="proof-video-card">

                <div className="proof-header">

                  <div>
                    <span className="eyebrow">
                      EVIDENCE
                    </span>

                    <h3>
                      Proof Video
                    </h3>

                    <p>
                      AI-generated clip around
                      the detected event.
                    </p>
                  </div>

                  {analysis.proof_duration && (
                    <span className="duration-pill">
                      {analysis.proof_duration}s clip
                    </span>
                  )}

                </div>

                {/* PLAYER */}

                <div className="video-player">

                  {videoLoading ? (

                    <div className="video-loading">

                      <div className="large-spinner" />

                      <strong>
                        Loading proof video...
                      </strong>

                      <span>
                        Preparing evidence
                        for playback
                      </span>

                    </div>

                  ) : proofVideoUrl ? (

                    <video
                      key={proofVideoUrl}
                      controls
                      preload="metadata"
                      playsInline
                      src={proofVideoUrl}
                      onLoadedMetadata={() => {
                        setVideoError('')
                      }}
                      onCanPlay={() => {
                        setVideoError('')
                      }}
                      onError={() => {
                        setVideoError(
                          'The browser cannot decode this proof video. The generated MP4 may use an unsupported video codec.'
                        )
                      }}
                    >
                      Your browser does not
                      support HTML5 video.
                    </video>

                  ) : (

                    <div className="video-empty">
                      <span>
                        No proof video loaded
                      </span>
                    </div>

                  )}

                </div>

                {/* VIDEO ERROR */}

                {videoError && (
                  <div className="video-error">
                    <strong>
                      Video Playback Error
                    </strong>

                    <span>
                      {videoError}
                    </span>
                  </div>
                )}

                {/* ACTIONS */}

                {proofVideoUrl && (

                  <div className="video-actions">

                    <a
                      className="secondary-button"
                      href={proofVideoUrl}
                      download={
                        `${
                          result?.filename ||
                          'proof'
                        }_proof.mp4`
                      }
                    >
                      ↓ Download Evidence
                    </a>

                    <a
                      className="secondary-button"
                      href={getProofVideoUrl(
                        result.video_id
                      )}
                      target="_blank"
                      rel="noreferrer"
                    >
                      ↗ Open Original
                    </a>

                  </div>

                )}

              </div>

            </>
          )}

        </div>
      )}

    </section>
  )
}

export default VideoAnalysis