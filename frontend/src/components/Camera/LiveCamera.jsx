// import { useState } from 'react'

// const API = 'http://127.0.0.1:8000'

// const CAMERA_STREAM =
//   `${API}/api/camera/stream`

// function LiveCamera() {
//   return (
//     <section className="camera-panel">
//       <div className="panel-header">
//         <div>
//           <h2>Live Camera</h2>
//           <span>CAM01</span>
//         </div>

//         <span className="live-badge">
//           ● LIVE
//         </span>
//       </div>

//       <div className="camera-view">
//         <div className="camera-overlay">
//           <span>CAM01</span>

//           <span>
//             AI MONITORING ACTIVE
//           </span>
//         </div>

//         <div className="camera-placeholder">
//           <img
//             src={CAMERA_STREAM}
//             alt="CAM01 live stream"
//             className="camera-stream"
//           />
//         </div>
//       </div>
//     </section>
//   )
// }

// export default LiveCamera





import { useState } from 'react'
import './LiveCamera.css'

import { CAMERA_STREAM } from '../../api/cameraApi'

function LiveCamera() {
  const [streamError, setStreamError] = useState(false)

  return (
    <section className="camera-panel">

      <div className="panel-header">
        <div>
          <h2>Live Camera</h2>
          <span>CAM01</span>
        </div>

        <span className={`live-badge ${streamError ? 'live-badge--offline' : ''}`}>
          {streamError ? '● OFFLINE' : '● LIVE'}
        </span>
      </div>

      <div className="camera-view">

        <div className="camera-overlay">
          <span>CAM01</span>

          <span>
            AI MONITORING ACTIVE
          </span>
        </div>

        <div className="camera-placeholder">

          {streamError ? (
            <div className="camera-stream-placeholder">
              <strong>CAM01 frame unavailable</strong>
              <span>Start the camera runtime to publish a fresh frame.</span>
            </div>
          ) : (
            <img
              src={CAMERA_STREAM}
              alt="CAM01 live stream"
              className="camera-stream"
              onError={() => setStreamError(true)}
            />
          )}

        </div>

      </div>

    </section>
  )
}

export default LiveCamera
















// import { useState } from 'react'
// import './LiveCamera.css'
// import { CAMERA_STREAM } from '../../api/cameraApi'

// function LiveCamera() {
//   const [streamError, setStreamError] = useState(false)

//   return (
//     <section className="camera-panel">
//       <div className="panel-header">
//         <div>
//           <h2>Live Camera</h2>
//           <span>CAM01</span>
//         </div>

//         <span
//           className={`live-badge ${
//             streamError ? 'live-badge--offline' : ''
//           }`}
//         >
//           {streamError ? '● OFFLINE' : '● LIVE'}
//         </span>
//       </div>

//       <div className="camera-view">
//         <div className="camera-overlay">
//           <span>CAM01</span>
//           <span>AI MONITORING ACTIVE</span>
//         </div>

//         <div className="camera-placeholder">
//           {streamError ? (
//             <div className="camera-stream-placeholder">
//               <strong>CAM01 frame unavailable</strong>
//               <span>
//                 Check the camera stream endpoint and confirm
//                 the detection agent is publishing fresh frames.
//               </span>
//             </div>
//           ) : (
//             <img
//               src={CAMERA_STREAM}
//               alt="CAM01 live stream"
//               className="camera-stream"
//               onError={() => setStreamError(true)}
//             />
//           )}
//         </div>
//       </div>
//     </section>
//   )
// }

// export default LiveCamera
