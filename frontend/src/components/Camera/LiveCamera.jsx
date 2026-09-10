// import './LiveCamera.css'

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


import './LiveCamera.css'

import { CAMERA_STREAM } from '../../api/cameraApi'

function LiveCamera() {
  return (
    <section className="camera-panel">

      <div className="panel-header">
        <div>
          <h2>Live Camera</h2>
          <span>CAM01</span>
        </div>

        <span className="live-badge">
          ● LIVE
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

          <img
            src={CAMERA_STREAM}
            alt="CAM01 live stream"
            className="camera-stream"
          />

        </div>

      </div>

    </section>
  )
}

export default LiveCamera