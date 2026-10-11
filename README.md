# Multi-Camera AI Video Intelligence & Investigation Platform

An AI-powered video surveillance and investigation platform designed to analyze live camera streams and recorded CCTV footage using computer vision, object detection, and object tracking.

**Developed by:** Krunal Prajapati  
**College:** L.D. College of Engineering, Ahmedabad, Gujarat  
**Department:** Artificial Intelligence and Machine Learning  
**Project Domain:** Artificial Intelligence, Computer Vision, Video Analytics, Full-Stack Development

---

## 📌 Overview

Traditional CCTV systems primarily record video and depend on humans to monitor screens and review footage manually. This process can be time-consuming, especially when multiple cameras and large amounts of recorded video are involved.

The **Multi-Camera AI Video Intelligence & Investigation Platform** aims to make surveillance more intelligent by integrating AI-powered video analysis into a centralized application.

The platform is designed to process video from live camera sources and recorded footage, detect objects, track their movement, and provide a foundation for event monitoring and investigation.

By combining computer vision with a web-based interface, the project explores how AI can improve surveillance workflows, reduce repetitive manual monitoring, and help users review important events more efficiently.

## 🎯 Objectives

- Develop an AI-powered video surveillance and analysis platform.
- Integrate object detection into live and recorded video workflows.
- Explore object tracking across consecutive video frames.
- Support a multi-camera surveillance architecture.
- Provide a web-based interface for accessing video intelligence features.
- Establish a foundation for incident investigation and evidence review.
- Build a modular application that can be extended with additional AI capabilities.

## ✨ Key Features

### 1. AI-Powered Object Detection
Uses the YOLO object detection model to identify supported object classes in video frames.

### 2. Live Video Analysis
Designed to process video from supported live camera sources, depending on the available camera configuration and implementation.

### 3. Recorded Video Analysis
Supports the analysis of prerecorded video footage, enabling investigation beyond live monitoring.

### 4. Object Tracking
Integrates computer vision tracking concepts to follow detected objects across frames when tracking is enabled.

### 5. Multi-Camera Architecture
Designed with multi-camera monitoring in mind, allowing the application to be extended to manage multiple video sources.

### 6. Web-Based Interface
Uses a React-based frontend to provide a user interface for interacting with the platform.

### 7. Backend API
Uses FastAPI to support communication between the frontend and backend and to organize application functionality.

### 8. Extensible Investigation Workflow
Provides a foundation for future capabilities such as event classification, configurable detection zones, incident timelines, evidence management, and investigation reports.

> **Note:** The availability of individual features depends on the current implementation. Only claim features as completed when they are working in your demo.

## 🏗️ System Architecture

The platform follows a frontend-backend architecture.

```text
                ┌───────────────────────────┐
                │       User / Operator     │
                └─────────────┬─────────────┘
                              │
                              ▼
                ┌───────────────────────────┐
                │     React Frontend        │
                │  Dashboard and Interface  │
                └─────────────┬─────────────┘
                              │
                       HTTP / REST API
                              │
                              ▼
                ┌───────────────────────────┐
                │       FastAPI Backend     │
                │   API and Application     │
                │         Logic             │
                └─────────────┬─────────────┘
                              │
                              ▼
                ┌───────────────────────────┐
                │   Video Processing Layer  │
                │       OpenCV              │
                └─────────────┬─────────────┘
                              │
                              ▼
                ┌───────────────────────────┐
                │   YOLO Object Detection   │
                │  ByteTrack Integration*   │
                └─────────────┬─────────────┘
                              │
                              ▼
                ┌───────────────────────────┐
                │ Detection and Tracking    │
                │       Results             │
                └───────────────────────────┘
```

\*ByteTrack is part of the intended technology stack where integrated into the current version.

### Architecture Components

- **Frontend:** Displays the user interface and communicates with backend APIs.
- **Backend:** Handles API requests and coordinates application functionality.
- **Video Processing:** Reads and processes video frames using OpenCV.
- **Object Detection:** Uses YOLO to detect supported objects.
- **Object Tracking:** Uses a tracking component, such as ByteTrack, when configured.
- **Investigation Layer:** Can be extended to store and review incidents, timestamps, and related evidence.

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Frontend | React | Web interface |
| Frontend Tooling | Vite | Development server and build tooling |
| Backend | Python, FastAPI | Backend APIs and application logic |
| Computer Vision | OpenCV | Video capture and frame processing |
| Object Detection | YOLO | AI-based object detection |
| Object Tracking | ByteTrack | Object tracking when integrated |
| API Communication | HTTP / REST | Frontend-backend communication |
| Model Weights | `yolo11n.pt` | YOLO model weights, if used by the application |

## 📂 Project Structure

```text
cctv-ai-intelligent-surveillance/
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── other_modules/
│
├── models/
│   └── yolo11n.pt
│
├── README.md
├── .gitignore
└── .env.example
```

**Important:** Keep only folders and filenames that actually exist in your project. If the model file is stored somewhere else, document its real location instead.

## 💻 System Requirements

Recommended development environment:

- Windows, Linux, or macOS
- Python 3.10 or another Python version supported by the installed dependencies
- Node.js and npm
- A modern web browser
- A webcam or compatible video source for live testing
- Sufficient RAM and CPU resources for video processing
- Optional compatible GPU for accelerated inference

Performance depends on the hardware, video resolution, number of active streams, model settings, and processing configuration.

## ⚙️ Installation and Setup

### Step 1: Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd cctv-ai-intelligent-surveillance
```

Replace `<YOUR_GITHUB_REPOSITORY_URL>` with your actual repository URL.

Alternatively, download the repository as a ZIP file and extract it.

### Step 2: Set Up the Backend

Open a terminal in the project directory.

Create a Python virtual environment:

```bash
py -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies using the actual requirements file in your project:

```bash
py -m pip install -r backend/requirements.txt
```

If your `requirements.txt` is located in the project root, use:

```bash
py -m pip install -r requirements.txt
```

If neither file exists, create a dependency list based on the packages your project actually imports.

### Step 3: Configure Environment Variables

If the backend uses environment variables, create a local `.env` file based on `.env.example`.

Example:

```env
HOST=127.0.0.1
PORT=8000
```

These are illustrative settings only. Use the variable names and values expected by your application.

Never commit passwords, API keys, secret keys, or other sensitive configuration values to a public repository.

### Step 4: Start the Backend

If the FastAPI application is defined in `backend/main.py` as `app`, run:

```bash
py -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

If your application uses a different module path, update the command accordingly.

Once started, open:

- Backend: `http://127.0.0.1:8000`
- API documentation: `http://127.0.0.1:8000/docs`

The root URL may not display a webpage if no root endpoint has been implemented.

### Step 5: Set Up the Frontend

Open a second terminal and navigate to the frontend folder:

```bash
cd frontend
```

Install the dependencies:

```bash
npm install
```

Start the Vite development server:

```bash
npm run dev
```

Open the local URL displayed in the terminal, commonly:

```text
http://localhost:5173
```

Configure the frontend API base URL according to the backend configuration used by your application.

## 🎥 Using the Platform

The following workflow describes the intended usage. Available options depend on the current implementation.

1. Start the backend API.
2. Start the frontend development server.
3. Open the application in a browser.
4. Select an available live camera or recorded video source.
5. Start video processing.
6. Review the detection results displayed by the application.
7. If object tracking is enabled, review the tracked objects and their identifiers.
8. Use any implemented investigation or reporting features to review relevant results.

For live camera testing, ensure the camera is connected and available to the application. Camera permissions and device access may affect operation.

## 🧠 AI and Computer Vision Workflow

The core video-analysis workflow can be represented as:

```text
Video Source
     |
     v
Frame Capture
     |
     v
Frame Preprocessing
     |
     v
YOLO Object Detection
     |
     v
Detection Filtering
     |
     v
Object Tracking (if enabled)
     |
     v
Visualization and Results
     |
     v
Investigation and Review
```

### Object Detection

YOLO processes video frames and predicts supported object classes, bounding boxes, and confidence scores.

### Object Tracking

A tracker such as ByteTrack can associate detections across frames to help maintain object identities over time.

### Video Processing

OpenCV provides tools for reading video streams, processing frames, and preparing visual output.

### Investigation

Detection and tracking results can support later analysis. Persistent incident storage, evidence export, and searchable event history require the corresponding application components to be implemented.

## 🧪 Testing and Validation

Testing should be performed against the actual running application.

Suggested test cases include:

| Test Case | Expected Result |
|---|---|
| Start the backend | FastAPI server starts without errors |
| Open API documentation | API documentation is accessible if enabled |
| Start the frontend | Web interface loads successfully |
| Connect a supported camera | Video is available to the application |
| Load a recorded video | Video frames can be processed |
| Run object detection | Supported objects are detected where visible |
| Enable object tracking | Tracking results appear when supported |
| Use multiple camera sources | Configured sources operate within system limits |

Record actual results before submitting a formal project report. Do not describe a test as successful until it has been performed.

## 🌍 Potential Applications

The platform's computer vision approach may be useful in:

- Campus and institutional surveillance
- Office and commercial building monitoring
- Warehouse and facility observation
- Parking-area monitoring
- Industrial safety monitoring
- Review of recorded CCTV footage
- Video-based investigation workflows

These are potential applications, not claims of deployment or certification.

## 🔒 Privacy and Responsible Use

Video surveillance systems can process sensitive personal information. Responsible deployment should include:

- Authorization to access cameras and footage
- Appropriate access controls
- Secure handling of video and investigation records
- Retention policies that match applicable requirements
- Protection of credentials and configuration files
- Compliance with applicable privacy and surveillance laws
- Human review of important AI-generated findings

Object detection and tracking may produce false positives, missed detections, or identity switches. AI-generated results should not be treated as conclusive evidence without appropriate verification.

## ⚠️ Current Limitations

Actual limitations depend on the implemented version. Areas that may require further development include:

- Detection accuracy under low-light or crowded conditions
- Processing speed with multiple simultaneous video streams
- Hardware and memory constraints
- Compatibility with different camera protocols
- Long-duration video processing
- Persistent incident storage and evidence retention
- False positives and missed detections
- Secure deployment and user access management

Scalability to hundreds of cameras requires performance testing, resource management, and appropriate infrastructure; it should not be assumed based only on the architecture.

## 🚀 Future Enhancements

Potential future improvements include:

- Scalable camera registration and management
- Support for additional camera protocols
- Configurable detection zones and event rules
- Searchable incident timelines
- Evidence snapshots and report generation
- Role-based access control
- Notifications for configured events
- Optimized inference and stream scheduling
- Database-backed incident history
- Docker-based deployment
- Performance monitoring and load testing

These enhancements can be prioritized according to project requirements and testing results.

## 🎓 Academic Information

**Project Title:** Multi-Camera AI Video Intelligence & Investigation Platform  
**Student:** Krunal Prajapati  
**Department:** Artificial Intelligence and Machine Learning  
**Institution:** L.D. College of Engineering, Ahmedabad, Gujarat, India

This project demonstrates the application of computer vision, AI model integration, backend API development, and frontend engineering to a real-world surveillance problem.

## 📸 Screenshots and Live Demo

Add screenshots of your actual application to a folder such as `docs/screenshots/` and link them here.

Example:

```markdown
![Application Dashboard](docs/screenshots/dashboard.png)

![Object Detection Demo](docs/screenshots/detection-demo.png)
```

Replace the example paths with the real screenshot paths in your repository.

**Live Demo:** Add your publicly accessible demo URL here, if available.

**GitHub Repository:** Add your repository URL here.

## 🤝 Contributions

Suggestions and constructive feedback are welcome. If you wish to contribute, create a branch for your proposed changes and submit a pull request with a clear explanation of the improvement.

## 📄 License

Choose and add an appropriate open-source license before distributing the project publicly. If no license has been added, all rights remain with the copyright holder by default; public visibility alone does not grant permission to reuse the code.

## 🙏 Acknowledgements

I acknowledge the open-source communities and developers behind the technologies used in this project, including Python, React, FastAPI, OpenCV, YOLO, and related computer vision tools.

---

**Built as an AI and Computer Vision project at L.D. College of Engineering, Ahmedabad.**
