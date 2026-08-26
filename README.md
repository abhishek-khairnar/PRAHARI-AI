# PRAHARI-AI — Intelligent Border Surveillance & Video Analytics

> **Real-Time Edge AI Surveillance, Virtual Fence Perimeter Defense, Automated ANPR, Face Detection, Loitering Analytics, and Offline-First Resilience.**

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [System Architecture](#3-system-architecture)
4. [Complete Data Flow & Frame Lifecycle](#4-complete-data-flow--frame-lifecycle)
5. [AI Models & Weights](#5-ai-models--weights)
6. [Object Detection & Classification](#6-object-detection--classification)
7. [Centroid & IoU Tracking Engine](#7-centroid--iou-tracking-engine)
8. [Virtual Fence Perimeter Intrusion Detection](#8-virtual-fence-perimeter-intrusion-detection)
9. [Automatic Number Plate Recognition (ANPR)](#9-automatic-number-plate-recognition-anpr)
10. [Face Detection (YuNet ONNX)](#10-face-detection-yunet-onnx)
11. [Suspicious Activity & Loitering Analytics](#11-suspicious-activity--loitering-analytics)
12. [Night Mode & Nocturnal Movement Detection](#12-night-mode--nocturnal-movement-detection)
13. [Database Architecture & Offline Sync](#13-database-architecture--offline-sync)
14. [FastAPI Backend & API Reference](#14-fastapi-backend--api-reference)
15. [Command & Intelligence Dashboard](#15-command--intelligence-dashboard)
16. [Project Structure](#16-project-structure)
17. [Installation & Environment Setup](#17-installation--environment-setup)
18. [GPU Acceleration & CUDA Setup](#18-gpu-acceleration--cuda-setup)
19. [RTSP Ingestion & MediaMTX Infrastructure](#19-rtsp-ingestion--mediamtx-infrastructure)
20. [Run PRAHARI-AI — 3 Commands (Startup Flow)](#20-run-prahari-ai--3-commands-startup-flow)
21. [Troubleshooting Guide](#21-troubleshooting-guide)
22. [Tested Hardware & Performance Benchmarks](#22-tested-hardware--performance-benchmarks)
23. [Security, Privacy & Air-Gap Design](#23-security-privacy--air-gap-design)
24. [GitHub Publishing & Repository Setup](#24-github-publishing--repository-setup)
25. [Team Member Onboarding Guide](#25-team-member-onboarding-guide)
26. [What NOT to Commit (.gitignore Policy)](#26-what-not-to-commit-gitignore-policy)
27. [Large Files Policy & Handling](#27-large-files-policy--handling)
28. [License](#28-license)
29. [Team Roles & Modular Responsibilities](#29-team-roles--modular-responsibilities)
30. [SIH / Evaluator Demonstration Walkthrough](#30-sih--evaluator-demonstration-walkthrough)
31. [Known Limitations](#31-known-limitations)
32. [Future Improvements & Roadmap](#32-future-improvements--roadmap)
33. [Technology Stack & Credits](#33-technology-stack--credits)

---

## 1. Project Overview

Modern border security and perimeter enforcement operations face critical operational bottlenecks: vast geographical sectors, extreme terrain, intermittent network connectivity, human operator fatigue, and high false-alarm rates. 

**PRAHARI-AI** (*Pra-ha-ri* — Sanskrit for *Guardian/Sentinel*) is an integrated, low-latency, offline-first edge video analytics and perimeter surveillance platform engineered for forward operating locations, border checkpoints, and critical infrastructure installations.

### Core Objectives & Value Proposition
- **Automated Perimeter Defense**: Replaces passive CCTV monitoring with an active virtual fence trigger that automatically calculates breach direction (`IN` vs `OUT`) and logs forensic snapshot evidence.
- **Intelligent Vehicle Identification**: Employs a multi-stage ANPR pipeline with temporal consensus voting to extract, enhance, read, and validate vehicle license plates against Indian registration standards.
- **Nocturnal & Behavioral Awareness**: Actively detects loitering behavior via spatial displacement anchors and classifies day/night transitions to flag nocturnal movement in low-light conditions.
- **Air-Gapped Operational Resilience**: All AI inference, object tracking, OCR, snapshot generation, and database storage run 100% locally on-device without cloud API dependencies. An offline synchronization buffer archives events locally until uplink is restored.

---

## 2. Key Features

| Feature Module | Technology / Engine | Description |
| :--- | :--- | :--- |
| **Object Detection** | Ultralytics YOLOv8n (CUDA FP16) | Real-time localization of persons, cars, buses, trucks, motorcycles, and vehicles at ~9–20 ms inference latency. |
| **Object Tracking** | Custom CentroidTracker + IoU | Combined IoU-first and dynamic Euclidean centroid matching with persistent track IDs and occlusion tolerance. |
| **Virtual Fence Defense** | Geometric Centroid State Machine | Configurable tripwire (Y=756 on 1080p) with bidirectional crossing classification (`IN`/`OUT`) and per-track deduplication. |
| **Evidence Snapshot Generation** | OpenCV Multi-Threaded Writer | Generates 1080p annotated evidence snapshots with bounding boxes, breach tags, fence overlay, and telemetry timestamps. |
| **ANPR & License Plate OCR** | YOLO Plate Detector + EasyOCR (CUDA) / PaddleOCR | Multi-frame rolling buffer, Lanczos aspect-ratio upscaling, CLAHE contrast enhancement, Indian format validation, and temporal consensus. |
| **Face Detection** | Local YuNet ONNX (`libfacedetection`) | Amortized face scanning on high-resolution head/upper-body crops of tracked persons (<2 ms amortized latency). |
| **Loitering Detection** | Spatial Dwell Timer Engine | Flags individuals stationary within a 100 px radius for over 20 seconds with automatic cooldowns. |
| **Night Mode Analytics** | Luminance Analysis + Motion Delta | Evaluates frame brightness (<45 low-light threshold, 30-frame confirmation) and alerts on nocturnal movements. |
| **Local Database & Sync** | SQLite WAL + Offline Sync Engine | Thread-safe persistence across 4 relational tables (`intrusion_events`, `anpr_events`, `security_events`, `system_events`) and JSON export. |
| **Streaming & API Backend** | FastAPI + Uvicorn + MJPEG | High-throughput asynchronous HTTP backend serving multipart video feeds and 14 structured RESTful JSON endpoints. |
| **Operator Command UI** | HTML5 / Vanilla CSS / Modern JS | Dark tactical HUD command center with live threat level meter, real-time counters, tabbed incident streams, and telemetry cards. |
| **Multi-Camera Foundation** | `CameraManager` Class | Modular multi-stream foundation supporting independent processing pipelines per registered RTSP camera ID. |

---

## 3. System Architecture

```text
+---------------------------------------------------------------------------------------------------+
|                                      PRAHARI-AI SYSTEM PIPELINE                                   |
+---------------------------------------------------------------------------------------------------+

     [ Video Source: border_demo.mp4 ] (1920x1080 @ 30 FPS H.264)
                   |
                   v
     [ FFmpeg RTSP Loop Publisher ] (-c copy -rtsp_transport tcp)
                   |
                   v
     [ MediaMTX RTSP Server ] (Port :8554 /mystream)
                   |
                   v
     [ RTSPStreamReader Grabber Thread ] (Dedicated high-speed frame ingest buffer)
                   |
                   +-------------------------------------------------------------------+
                   |                                                                   |
                   v                                                                   v
     [ Deep Learning Inference ] (YOLOv8n CUDA)                       [ Scene Luminance & Loop Check ]
                   |                                                                   |
                   v                                                                   v
     [ Centroid & IoU Tracking Engine ]                               [ Night Mode / Loop Discontinuity ]
     (Persistent IDs, Trajectories, Bounding Boxes)
                   |
                   +-----------------------+-----------------------+-------------------+
                   |                       |                       |                   |
                   v                       v                       v                   v
        [ Virtual Fence Alert ]   [ Vehicle Frame Buffer ]   [ YuNet Face Engine ]  [ Loitering State ]
        - Y=756 Crossing Check    - Up to 10 Crops / Track   - Head/Upper Body Crop - 20s Dwell Timer
        - IN / OUT Direction      - Sharpness Ranking        - Periodic Amortized   - 100px Anchor Radius
        - Deduplication Guard              |                           |                   |
                   |                       v                           v                   v
                   |            [ Async ANPR Worker ]         [ Face Bounding Box ] [ Security Event ]
                   |            - YOLO Plate Localization
                   |            - Lanczos Upscale + CLAHE
                   |            - EasyOCR CUDA / Paddle
                   |            - Indian Plate Validation
                   |            - Temporal Consensus
                   |                       |
                   +-----------+-----------+
                               |
                               v
               [ Evidence Snapshot Generator ] (1080p Annotated Snapshots -> static/alerts/, static/anpr/)
                               |
                               v
               [ Thread-Safe SQLite WAL Database ] (prahari_events.db + synced_events.json)
                               |
                               v
               [ FastAPI Asynchronous Backend ] (Port :8001 | 14 REST Endpoints + /video_feed MJPEG)
                               |
                               v
               [ Command & Intelligence Dashboard ] (Browser Operator UI @ http://localhost:8001)
```

---

## 4. Complete Data Flow & Frame Lifecycle

Each video frame processed by PRAHARI-AI follows a deterministic, non-blocking lifecycle:

1. **Ingest & Re-Streaming**: `border_demo.mp4` is published by FFmpeg over TCP to MediaMTX at `rtsp://localhost:8554/mystream`.
2. **Frame Grabber Thread**: An isolated background worker grabs frames via OpenCV `VideoCapture` into a double-buffered shared memory slot, decoupling RTSP network ingestion from AI compute.
3. **Loop & Luminance Assessment**: Computes grayscale frame luminance to determine Day/Night mode (with a 30-frame confirmation buffer) and measures frame diff against previous thumbnail to detect seamless video loop restarts.
4. **Primary Object Detection**: The latest frame is sent to **YOLOv8n** on CUDA GPU (`conf=0.35`, `imgsz=640`). Target classes: `Person (0)`, `Vehicle (1)`, `Car (2)`, `Motorcycle (3)`, `Bus (5)`, `Truck (7)`.
5. **Centroid & IoU Matching**: Detections are correlated with existing tracked objects using a combined metric prioritizing bounding-box IoU overlap when spatial intersection exists, augmented by Euclidean centroid distance.
6. **Virtual Fence Evaluation**: The vertical centroid position of each tracked object is compared with the virtual fence line ($Y = 756$). When an object transitions from $y < 756$ to $y \ge 756$, an `IN` intrusion is triggered; $y \ge 756$ to $y < 756$ triggers an `OUT` event.
7. **Snapshot & Database Commit**: Upon confirmation (`hits >= 2`), an annotated 1080p snapshot is written to `static/alerts/` and logged to SQLite (`intrusion_events`) asynchronously via `ThreadPoolExecutor`.
8. **Vehicle Ring Buffering & ANPR Dispatch**: For vehicles crossing the fence, rolling bounding-box crops are added to a per-track buffer. The top-ranked sharpest crops are enqueued into a bounded queue for background OCR.
9. **ANPR Localization, OCR & Consensus**:
   - YOLO plate detector extracts the plate region with outward expansion padding (+12% width, +18% height).
   - Plate crop is upscaled using Lanczos-4 interpolation and preprocessed through CLAHE and unsharp masking.
   - EasyOCR (CUDA) or PaddleOCR extracts raw text.
   - Text is cleaned using positional alphanumeric heuristics and validated against Indian registration syntax (e.g., `MH02FU9302`).
   - Observations over multiple frames vote toward a temporal consensus string.
   - Unreadable plates are explicitly designated as `PLATE NOT READ` / `UNREADABLE` without artificial fabrication.
10. **Face & Loitering Analytics**:
    - Every 8 frames, YuNet scans high-resolution upper-body/head crops of the largest tracked persons.
    - Tracked individuals stationary within a 100 px radius for $\ge 20$ seconds trigger a loitering security alert.
11. **MJPEG Stream & Dashboard Polling**: Processed frames with HUD overlays are JPEG-encoded and streamed via `/video_feed`. The frontend polls `/api/status`, `/api/alerts`, `/api/anpr_log`, and `/api/security_events` at sub-second intervals.

---

## 5. AI Models & Weights

| Model Name | Task / Role | Framework | Source | Format | Default Location |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **YOLOv8n** (`yolov8n.pt`) | Primary Object Detection | PyTorch / Ultralytics | Local / Ultralytics Hub | `.pt` weights (~6.5 MB) | `weights/yolov8n.pt` & root |
| **YuNet ONNX** (`face_detection_yunet_2023mar.onnx`) | High-Speed Face Detection | OpenCV DNN / ONNX | OpenCV Model Zoo | ONNX format (~232 KB) | `weights/face_detection_yunet_2023mar.onnx` |
| **YOLO License Plate Detector** (`license-plate-finetune-v1n.pt`) | License Plate Region Localization | Ultralytics YOLO | Hugging Face (`morsetechlab/yolov11-license-plate-detection`) | `.pt` weights (~5.5 MB) | HuggingFace cache / Fallback |
| **EasyOCR (CRAFT + CRNN)** | Text & Character Recognition | PyTorch (CUDA Accelerated) | JaidedAI / EasyOCR | PyTorch models (~80 MB) | `~/.EasyOCR/model/` |
| **PaddleOCR (PP-OCRv4)** *(Fallback)* | Fallback Character Recognition | PaddlePaddle / PaddleOCR | PaddlePaddle Model Zoo | Inference Model | `~/.paddleocr/` |

---

## 6. Object Detection & Classification

The primary detection engine runs **Ultralytics YOLOv8n** on CUDA with mixed precision (FP16).

```
Target COCO Classes:
├── Person       (Class 0) -> Emerald Green Bounding Box
├── Bicycle      (Class 1) -> Blue/Cyan Bounding Box
├── Car          (Class 2) -> Blue/Cyan Bounding Box
├── Motorcycle   (Class 3) -> Blue/Cyan Bounding Box
├── Bus          (Class 5) -> Blue/Cyan Bounding Box
└── Truck        (Class 7) -> Blue/Cyan Bounding Box
```

### Auto-Rickshaw Classification Note
> **Important**: Standard COCO pre-trained YOLO models do **not** have a dedicated class for Indian 3-wheeler auto-rickshaws. In standard COCO weights, auto-rickshaws are typically detected under general vehicle classes (`Car`, `Motorcycle`, or generic `Vehicle` if confidence is below the subtype threshold). PRAHARI-AI does not fabricate an artificial auto-rickshaw class on standard COCO weights. Training a custom Indian traffic dataset is planned in the project roadmap.

---

## 7. Centroid & IoU Tracking Engine

The `CentroidTracker` class in `centroid_tracker.py` maintains persistent object identities across consecutive frames:

- **IoU-First Association**: Computes Intersection over Union between existing bounding boxes and new detections. When overlap $\ge 0.20$, the cost metric assigns 75% weight to IoU and 25% to centroid distance.
- **Dynamic Distance Thresholding**: The maximum association distance dynamically adapts to object size ($\max(220\text{ px}, \text{dimension} \times 1.5)$) to handle fast-moving vehicles close to the camera.
- **Class Consistency Penalty**: Penalizes identity swaps across disjoint object categories (e.g. Person vs Vehicle).
- **Disappearance Handling**: Allows up to `max_disappeared = 25` frames of occlusion/absence before deregistering a track ID.
- **Track Confirmation**: Requires `hits >= 2` consecutive detections before validating fence crossings or loitering timers, filtering out single-frame false positives.
- **Loop Discontinuity Guard**: Evaluates structural frame differences; when video loops restart abruptly, the tracker automatically clears stale track IDs to prevent false trajectory jumps.

---

## 8. Virtual Fence Perimeter Intrusion Detection

The virtual perimeter fence is configured as a horizontal tripwire across the surveillance frame.

```
+-----------------------------------------------------------------------------+
| Frame Top (Y=0)                                                             |
|                                                                             |
|                           [ Approaching Vehicle ]                           |
|                                     |                                       |
|                                     v (Moving Downwards)                    |
| ═══════════════════════════════════════════════════════════════════════════ |
| [ VIRTUAL FENCE LINE: Y=756 px (70% Height) ] ───> Direction: IN (Breach!)  |
| ═══════════════════════════════════════════════════════════════════════════ |
|                                     |                                       |
|                                     v                                       |
| Frame Bottom (Y=1080)                                                       |
+-----------------------------------------------------------------------------+
```

### Fence Trigger Logic
- **Directionality**: 
  - Top to bottom ($y_{\text{prev}} < 756 \rightarrow y_{\text{curr}} \ge 756$) $\Rightarrow$ **`IN`** (Entering secured perimeter).
  - Bottom to top ($y_{\text{prev}} \ge 756 \rightarrow y_{\text{curr}} < 756$) $\Rightarrow$ **`OUT`** (Exiting perimeter).
- **Deduplication**: Each track ID is flagged with `crossed_fence = True`. Re-alerting on the same track ID is blocked unless direction reverses.
- **Evidence Snapshot**: The moment a breach is confirmed, an annotated 1920x1080 frame is generated with red fence overlay, target bounding box, breach tag, and top telemetry header, saved to `static/alerts/intrusion_{timestamp}_id{object_id}.jpg`.

---

## 9. Automatic Number Plate Recognition (ANPR)

The ANPR engine (`anpr_engine.py`) operates as an asynchronous multi-stage pipeline:

```
[ Vehicle Bounding Box ]
         │
         ▼
[ Outward Expansion Padding ] (+12% Horizontal, +18% Vertical to preserve edge characters)
         │
         ▼
[ YOLO Plate Detector ] (morsetechlab/yolov11-license-plate-detection)
         │
         ▼
[ Aspect-Ratio Preserving Lanczos-4 Upscaling ] (Min height: 90px, Min width: 320px)
         │
         ▼
[ Multi-Variant Preprocessing ]
   ├── Variant 1: CLAHE Contrast Normalization on LAB L-channel
   ├── Variant 2: Unsharp Mask Sharpening (GaussianBlur sigma=2.0, weight=1.6)
   └── Variant 3: Contrast-Stretched Grayscale Normalization (MinMax 0-255)
         │
         ▼
[ Fast CUDA EasyOCR / PaddleOCR Execution ]
         │
         ▼
[ Positional Character Normalization ] (e.g. 0->O in state prefix; O->0 in registration digits)
         │
         ▼
[ Indian Registration Format Validation ]
   ├── Tier 1 (Strict): Matches ^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$ + Valid State Code
   └── Tier 2 (General): 5-10 alphanumeric characters containing letters and numbers
         │
         ▼
[ Multi-Frame Temporal Consensus Voting ] (Groups observations across rolling buffer)
         │
         ▼
[ Final Resolution ] ───► Valid: "MH02FU9302" (Linked to Intrusion Event)
                     └───► Unreadable: "PLATE NOT READ" (Explicit honest status)
```

---

## 10. Face Detection (YuNet ONNX)

- **Model**: Local OpenCV Zoo YuNet ONNX (`face_detection_yunet_2023mar.onnx`, 232 KB).
- **Execution Strategy**: Amortized execution every 8 frames (`FACE_DETECTION_INTERVAL = 8`).
- **Targeted High-Resolution Crop**: Instead of downscaling the entire 1080p frame, YuNet processes upper-body/head crops of the top 2 largest tracked persons, preserving high facial resolution.
- **Fallback Scan**: If no person is currently tracked, a global downscaled pass (640x360) is executed.
- **Performance**: Amortized latency is under **1.6 ms** per frame.

---

## 11. Suspicious Activity & Loitering Analytics

- **Dwell Time Threshold**: Configured at `LOITERING_TIME_SECONDS = 20`.
- **Spatial Anchor Radius**: Configured at `LOITERING_RADIUS_PIXELS = 100`.
- **Logic**: When a tracked person remains within 100 pixels of their initial anchor point for over 20 seconds, a `suspicious_activity` security alert is generated.
- **Cooldown**: 30-second re-alert cooldown prevents redundant event spamming for the same individual.
- **Logging**: Events are logged to `security_events` table and highlighted on the dashboard security tab.

---

## 12. Night Mode & Nocturnal Movement Detection

- **Luminance Calculation**: Real-time mean pixel intensity of the grayscale frame is computed continuously.
- **Low-Light Threshold**: Frames with mean brightness $\le 45$ are classified as low-light / night.
- **Temporal Confirmation**: Requires 30 consecutive frames (`NIGHT_CONFIRM_FRAMES = 30`) below the threshold to toggle Night Mode, preventing transient lighting fluctuations from triggering state changes.
- **Nocturnal Motion Alert**: When Night Mode is active, any tracked object with displacement $\ge 15\text{ px}$ triggers a `night_movement` security alert logged to the database.

---

## 13. Database Architecture & Offline Sync

PRAHARI-AI uses a local SQLite database (`prahari_events.db`) with **Write-Ahead Logging (WAL)** enabled for non-blocking concurrent reads and writes.

```
prahari_events.db (SQLite WAL Mode)
├── intrusion_events  (id, timestamp, object_type, object_id, direction, plate_text, plate_confidence, anpr_status, snapshot_path, synced)
├── anpr_events       (id, timestamp, object_type, object_id, plate_text, confidence, snapshot_path, synced)
├── security_events   (id, timestamp, camera_id, event_type, object_type, object_id, confidence, snapshot_path, details, synced)
└── system_events     (id, timestamp, event_type, details)
```

### Offline-First Sync Engine
- Every database row includes a `synced` flag (`0 = unsynced`, `1 = synced`).
- A background worker (`_sync_worker_loop`) periodically gathers all records with `synced = 0`, exports them to `synced_events.json`, and updates `synced = 1`.
- This ensures 100% data integrity in remote border environments with zero cloud connectivity.

---

## 14. FastAPI Backend & API Reference

FastAPI runs on `http://localhost:8001` providing high-throughput video streaming and structured JSON endpoints.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the HTML5 Command and Intelligence Web Dashboard. |
| `GET` | `/video_feed` | Multipart MJPEG HTTP live video stream with HUD overlays. |
| `GET` | `/api/status` | Real-time system telemetry: connection state, FPS, device, live and database totals. |
| `GET` | `/api/alerts` | Recent intrusion breach records with snapshot image URLs. |
| `GET` | `/api/anpr_log` | Recent ANPR license plate recognition logs with plate crop URLs. |
| `GET` | `/api/anpr_debug` | Recent candidate debug crops from the license plate localization stage. |
| `GET` | `/api/events/all` | Paginated full historical event log from SQLite (`limit`, `offset`). |
| `GET` | `/api/sync_status` | Offline sync engine statistics (total, synced, and pending records). |
| `GET` | `/api/security_events`| Historical security events with optional `event_type` filter (`suspicious_activity`, `night_movement`). |
| `GET` | `/api/suspicious_alerts`| Recent in-memory loitering and suspicious activity alerts. |
| `GET` | `/api/night_status` | Current night mode classification, scene luminance, and night alert counts. |
| `GET` | `/api/face_stats` | Live face detection statistics and YuNet status. |
| `GET` | `/api/dashboard_stats`| Consolidated telemetry payload for dashboard polling. |
| `GET` | `/api/cameras` | List of registered surveillance cameras and connectivity status. |
| Static | `/alerts/{filename}` | Direct static file access to full-resolution intrusion snapshots. |
| Static | `/anpr/{filename}` | Direct static file access to license plate crop images. |
| Static | `/anpr_debug/{filename}`| Direct static file access to candidate debug plate crops. |

---

## 15. Command & Intelligence Dashboard

The web dashboard (`templates/index.html`) is a dark-themed operational command center:

```
+---------------------------------------------------------------------------------------------------+
|  [SHIELD] PRAHARI AI — Intelligent Border Surveillance & Command Center     CAM-01 [LIVE] [CUDA]  |
+---------------------------------------------------------------------------------------------------+
|                                                 |  [ THREAT LEVEL GAUGE: NORMAL / ELEVATED / CRIT ]
|                                                 +-------------------------------------------------+
|                                                 |  [ PEOPLE: 2 ]  [ VEHICLES: 3 ]  [ FACES: 1 ]   |
|         PRIMARY SURVEILLANCE FEED               +-------------------------------------------------+
|              (1920x1080 MJPEG)                  |  TABS: [Intrusions]  [ANPR Plates]  [Security]  |
|                                                 |  ─────────────────────────────────────────────  |
|   - Real-time YOLO Bounding Boxes               |  🚨 ID #34 Car [IN] - Plate: MH02FU9302         |
|   - Red Virtual Fence Overlay (Y=756)           |  🚨 ID #12 Person [OUT] - Perimeter Cross       |
|   - Live Tactical HUD Chips                     |  🚘 ID #42 Truck - Plate: DL01AB1234            |
|                                                 |  ⚠️ ID #08 Person - Loitering (24s in Zone)     |
|                                                 |  🌙 ID #19 Vehicle - Nocturnal Motion           |
+---------------------------------------------------------------------------------------------------+
| [ AI PERF: 28.4 FPS | 24ms ]  [ INTRUSIONS: 12 ]  [ ANPR PLATES: 8 ]  [ PATROL: NORMAL | SYNCED ] |
+---------------------------------------------------------------------------------------------------+
```

---

## 16. Project Structure

```text
PRAHARI-AI/
├── main.py                     # FastAPI application server, route definitions & lifespan manager
├── rtsp_stream.py              # Core surveillance engine (Grabber, AI Processor, ANPR Worker, Overlay)
├── anpr_engine.py              # License plate detector, multi-variant OCR & Indian format validation
├── centroid_tracker.py         # Centroid & IoU tracking engine with persistent IDs and trajectory history
├── database.py                 # SQLite WAL database manager & offline sync engine
├── camera_manager.py           # Multi-camera stream manager foundation
├── requirements.txt            # Python dependencies
├── README.md                   # Complete system documentation
├── .gitignore                  # Git exclusion rules for runtime databases, snapshots, and binaries
├── templates/
│   └── index.html              # Operator Command & Intelligence Dashboard
├── static/
│   ├── alerts/                 # Intrusion evidence snapshots (.gitkeep tracked)
│   ├── anpr/                   # License plate crop images (.gitkeep tracked)
│   └── anpr_debug/             # ANPR candidate debug crops (.gitkeep tracked)
├── weights/
│   ├── yolov8n.pt              # YOLOv8 Nano object detection weights (~6.5 MB)
│   └── face_detection_yunet_2023mar.onnx # OpenCV YuNet ONNX face detection model (~232 KB)
└── demo_videos/
    └── border_demo.mp4         # 1080p 30 FPS demonstration video clip (~10.3 MB)
```

---

## 17. Installation & Environment Setup

### Prerequisites
- **Operating System**: Windows 10 / 11 (64-bit)
- **Python Version**: Python 3.10 or 3.11 (Recommended)
- **GPU**: NVIDIA GPU with CUDA support (e.g., RTX 3050, RTX 3060, RTX 4060, T4, etc.)
- **External Binaries**: MediaMTX (RTSP server) and FFmpeg

### Step 1: Clone Repository & Create Virtual Environment
```powershell
# Open PowerShell in project directory
cd /d D:\PRAHARI-AI

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate
```

### Step 2: Install Python Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 18. GPU Acceleration & CUDA Setup

Verify that PyTorch recognizes your NVIDIA GPU:

```powershell
python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device Name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

**Expected Output:**
```text
CUDA Available: True
Device Name: NVIDIA GeForce RTX 3050 6GB Laptop GPU
```

> **Note**: If `torch.cuda.is_available()` returns `False`, install the CUDA-enabled PyTorch build for your system:
> ```powershell
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
> ```

---

## 19. RTSP Ingestion & MediaMTX Infrastructure

### Why `-c copy` is Used for RTSP Ingestion
The video publisher uses the FFmpeg `-c copy` stream-copy flag:

```powershell
ffmpeg -re -stream_loop -1 -i "D:\PRAHARI-AI\demo_videos\border_demo.mp4" -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/mystream
```

#### Technical Rationale
1. **Zero Transcoding Overhead**: `-c copy` copies existing H.264 NAL packets directly into the RTSP stream without CPU/GPU transcoding.
2. **GPU Preservation for AI**: Preserves 100% of GPU VRAM and tensor cores for YOLOv8 and EasyOCR inference.
3. **Driver Compatibility**: The installed NVIDIA driver version (537.53) does not match newer NVENC APIs required by FFmpeg 9.x. Using `-c copy` bypasses NVENC dependencies entirely while delivering flawless 30 FPS stream delivery.

---

## 20. Run PRAHARI-AI — 3 Commands (Startup Flow)

Run the system using three separate terminals in the following exact sequence:

### Terminal 1 — MediaMTX RTSP Server
```powershell
cd /d D:\PRAHARI-AI
mediamtx\mediamtx.exe mediamtx\mediamtx.yml
```
*Wait until MediaMTX logs `[RTSP] listener opened on :8554`.*

---

### Terminal 2 — FFmpeg RTSP Video Publisher
```powershell
cd /d D:\PRAHARI-AI
ffmpeg -re -stream_loop -1 -i "D:\PRAHARI-AI\demo_videos\border_demo.mp4" -c copy -f rtsp -rtsp_transport tcp rtsp://localhost:8554/mystream
```
*Wait until FFmpeg logs `fps=30.0` and begins streaming.*

---

### Terminal 3 — PRAHARI-AI Surveillance Server
```powershell
cd /d D:\PRAHARI-AI
python main.py
```

---

### Step 4 — Open Operator Dashboard
Open your web browser and navigate to:
👉 **[http://localhost:8001](http://localhost:8001)**

---

## 21. Troubleshooting Guide

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Port 8554 already occupied** | A previous instance of MediaMTX or another RTSP server is running. | Run `netstat -ano \| findstr :8554` to find PID, then kill via `taskkill /F /PID <PID>`. |
| **Port 8001 already occupied** | A previous FastAPI/Uvicorn process is active. | Run `netstat -ano \| findstr :8001`, then kill via `taskkill /F /PID <PID>`. Or launch with `PORT=8002 python main.py`. |
| **`border_demo.mp4` not found** | Incorrect filename or path. Ensure filename is `border_demo.mp4` (with underscore, not hyphen). | Verify file exists at `D:\PRAHARI-AI\demo_videos\border_demo.mp4`. |
| **FFmpeg connection refused** | MediaMTX was not started before FFmpeg. | Start Terminal 1 (MediaMTX) first, confirm listener on `:8554`, then start FFmpeg. |
| **RTSP feed shows "Connecting..."** | RTSP publisher has not connected or stream name mismatch. | Ensure FFmpeg stream URL is exactly `rtsp://localhost:8554/mystream`. |
| **CUDA returns `False` (CPU Mode)** | PyTorch CPU-only wheel installed. | Reinstall PyTorch with CUDA wheel: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`. |
| **ANPR displays `PLATE NOT READ`** | Plate is heavily blurred, distant, occluded, or unreadable in current video frame. | This is expected honest behavior. PRAHARI-AI does not fabricate plate text when OCR confidence is below threshold. |
| **Browser feed stutters** | Heavy GPU contention or browser hardware acceleration disabled. | Verify `-c copy` is used in FFmpeg. Ensure browser hardware acceleration is enabled in Chrome/Edge settings. |

---

## 22. Tested Hardware & Performance Benchmarks

### Tested System Configuration
- **GPU**: NVIDIA GeForce RTX 3050 6GB Laptop GPU
- **NVIDIA Driver**: 537.53
- **CPU**: Intel Core i5 / AMD Ryzen 5 class (6 Cores / 12 Threads)
- **RAM**: 16 GB DDR4/DDR5
- **OS**: Windows 11 (64-bit)

### Measured Real-Time Performance
- **Video Source**: 1920x1080 @ 30.0 FPS (~6.46 Mbps H.264)
- **RTSP Capture Ingest**: **30.0 FPS** (stable, TCP transport)
- **Full AI Detection Pipeline**: Typically **20–30 FPS** on tested RTX 3050 configuration.
- **MJPEG Web Display Feed**: **25–30 FPS** delivered to browser clients.

### Component Latency Breakdown
- **YOLOv8n Inference**: ~**9–20 ms** (CUDA FP16)
- **Centroid & IoU Tracking**: ~**2–5 ms**
- **YuNet Face Detection**: ~**0.6–1.6 ms** (amortized over 8 frames)
- **EasyOCR Inference (CUDA)**: ~**28–35 ms** per crop (executed asynchronously in background worker)
- **JPEG Compression & Delivery**: ~**2–4 ms**

> **Performance Note**: AI processing throughput depends on the host GPU model, resolution, and concurrent scene object count. Display FPS, RTSP source FPS, and AI inference FPS operate independently through PRAHARI-AI's multi-threaded architecture.

---

## 23. Security, Privacy & Air-Gap Design

- **100% On-Premise Execution**: No video frames, bounding boxes, or metadata are ever transmitted to external cloud endpoints.
- **Zero Hardcoded Secrets**: No hardcoded API keys, tokens, or personal credentials exist in the codebase.
- **Air-Gapped Logging**: Relational data is maintained strictly inside local SQLite WAL tables and local JSON sync buffers.
- **Git Hygiene**: Generated intrusion snapshots, database files, and local logs are excluded via `.gitignore` to prevent leaking operational surveillance data.

---

## 24. GitHub Publishing & Repository Setup

### Safe Git Initialization Commands

```powershell
# 1. Initialize Git repository
git init

# 2. Stage all source files (verifying .gitignore rules)
git add .

# 3. Check staged files to ensure no databases or snapshots are tracked
git status

# 4. Create initial release commit
git commit -m "Initial PRAHARI-AI release: Intelligent Border Surveillance & Video Analytics"

# 5. Set default branch to main
git branch -M main
```

### Remote Publishing Instructions (Run After Creating GitHub Repo)
After creating the repository `PRAHARI-AI` under your GitHub account (`abhishek-khairnar`), connect and push:

```powershell
# Set remote origin URL
git remote add origin https://github.com/abhishek-khairnar/PRAHARI-AI.git

# Push to GitHub
git push -u origin main
```

---

## 25. Team Member Onboarding Guide

To onboard a teammate on a new workstation:

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/abhishek-khairnar/PRAHARI-AI.git
   cd PRAHARI-AI
   ```
2. **Create and activate virtual environment**:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
4. **Obtain External Infrastructure**:
   - Download MediaMTX binary into `mediamtx/` directory (`mediamtx.exe`, `mediamtx.yml`).
   - Download FFmpeg into `ffmpeg/` directory (or add FFmpeg to system PATH).
5. **Verify AI Model Weights**:
   - Ensure `weights/yolov8n.pt` and `weights/face_detection_yunet_2023mar.onnx` are present.
6. **Place Demo Video**:
   - Place `border_demo.mp4` into `demo_videos/border_demo.mp4`.
7. **Start the System**:
   - Launch Terminal 1 (MediaMTX), Terminal 2 (FFmpeg), and Terminal 3 (`python main.py`).
8. **Open Dashboard**:
   - Navigate to `http://localhost:8001`.

---

## 26. What NOT to Commit (.gitignore Policy)

The following runtime artifacts are strictly excluded from version control:

- **Database files**: `*.db`, `*.db-wal`, `*.db-shm`, `*.db-journal` (prevents committing runtime state).
- **Generated Snapshots**: `static/alerts/*`, `static/anpr/*`, `static/anpr_debug/*` (retains `.gitkeep` for directory structure).
- **Offline Sync Archives**: `synced_events.json`.
- **Python Cache & Environments**: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `env/`.
- **Scratch & Test Outputs**: `scratch/`, `.system_generated/`, `*.tmp`.
- **External Binaries**: `mediamtx/`, `ffmpeg/`.
- **Auto-Generated SSL Certificates**: `auto.crt`, `auto.key`, `*.crt`, `*.key`.

---

## 27. Large Files Policy & Handling

- `demo_videos/border_demo.mp4`: **~10.3 MB** — Suitable for Git repository hosting (<25 MB soft limit).
- `weights/yolov8n.pt`: **~6.5 MB** — Stored directly in `weights/` for out-of-the-box execution.
- `weights/face_detection_yunet_2023mar.onnx`: **~232 KB** — Lightweight local ONNX model stored in `weights/`.
- Large external binaries (`ffmpeg.exe`, `mediamtx.exe`) are excluded from Git and downloaded separately during setup.

---

## 28. License

No license has been selected yet.

---

## 29. Team Roles & Modular Responsibilities

| Role / Domain | Focus Areas | Key Code Files |
| :--- | :--- | :--- |
| **AI & Computer Vision Lead** | YOLOv8 inference, custom model training, class tuning | `rtsp_stream.py`, `weights/` |
| **ANPR & OCR Specialist** | License plate localization, CLAHE preprocessing, OCR accuracy | `anpr_engine.py` |
| **Object Tracking Engineer** | CentroidTracker, IoU matching, trajectory & occlusion handling | `centroid_tracker.py` |
| **Backend & API Engineer** | FastAPI routes, MJPEG streaming, thread lifecycle, error handling | `main.py`, `camera_manager.py` |
| **Database & Offline Architect**| SQLite WAL schema, indexing, offline sync, air-gap export | `database.py` |
| **Frontend & UI Developer** | Command dashboard, HUD overlays, responsiveness, Lucide icons | `templates/index.html` |
| **QA, DevOps & Documentation** | Startup scripts, RTSP publisher, benchmarks, GitHub repo hygiene | `README.md`, `requirements.txt` |

---

## 30. SIH / Evaluator Demonstration Walkthrough

During an evaluation or hackathon demonstration, follow this 12-step flow:

1. **Launch MediaMTX** (Terminal 1) and show active RTSP listener on `:8554`.
2. **Launch FFmpeg Video Publisher** (Terminal 2) broadcasting `border_demo.mp4` at 30 FPS.
3. **Launch PRAHARI-AI** (Terminal 3) and highlight CUDA GPU auto-detection output.
4. **Open Browser** at `http://localhost:8001` and showcase the dark command center interface.
5. **Demonstrate Object Detection**: Point out emerald green bounding boxes for persons and blue boxes for vehicles.
6. **Demonstrate Tracking Persistence**: Highlight persistent Track IDs (`ID #1`, `ID #2`) maintained through the scene.
7. **Demonstrate Virtual Fence Crossing**: Observe an incoming vehicle crossing $Y=756$ triggering an instant `[IN]` alert.
8. **Inspect Evidence Snapshots**: Click on the Intrusion tab thumbnail to show the full-resolution annotated snapshot with fence line and timestamp.
9. **Showcase ANPR Processing**: Observe license plate detection, Indian standard validation (e.g. `MH02FU9302`), and temporal consensus linking back to the intrusion record.
10. **Showcase Face Detection**: Highlight YuNet bounding boxes on detected personnel.
11. **Demonstrate Security Analytics**: Show the Loitering counter and Night Mode status pills.
12. **Review Database & Offline Sync**: Open SQLite table records and demonstrate the `synced_events.json` air-gapped export.

---

## 31. Known Limitations

1. **Auto-Rickshaws**: Standard COCO YOLO classifies 3-wheelers under generic vehicle classes (`Car`, `Motorcycle`, `Vehicle`) rather than a dedicated auto-rickshaw label.
2. **Severe Plate Degradation**: Extremely distant, blurred, or heavily angled plates are classified honestly as `PLATE NOT READ` rather than hallucinating false text.
3. **Single Video Clip**: Demonstration is built around `border_demo.mp4` (daytime perimeter road). Night mode is tested via brightness simulation thresholds.
4. **Video Loop Boundary**: When the demo video loops seamlessly, a scene-change detector resets track IDs to prevent artificial velocity anomalies across the loop boundary.

---

## 32. Future Improvements & Roadmap

- [ ] **Custom Indian Traffic YOLO Model**: Train on custom datasets including auto-rickshaws, tractors, and military transport vehicles.
- [ ] **Dedicated Indian License Plate OCR**: Fine-tune CRNN/Transformer models specifically on high-contrast Indian HSRP fonts.
- [ ] **Multi-Camera Grid View**: Expand frontend dashboard to display 4-camera concurrent live matrix with dynamic switching.
- [ ] **Edge Hardware Deployment**: Package containerized deployment for NVIDIA Jetson Orin Nano / Xavier NX edge devices.
- [ ] **Automated Alert Dispatch**: Add webhook notifications for Telegram, SMS, and secure SMTP email dispatch upon critical intrusions.
- [ ] **PTZ Camera Auto-Tracking**: Integrate ONVIF PTZ camera controls to dynamically zoom into intruding vehicles.

---

## 33. Technology Stack & Credits

- **Core Language**: Python 3.10+
- **Deep Learning Framework**: PyTorch, Ultralytics YOLOv8
- **Computer Vision**: OpenCV (`opencv-python`), ONNX Runtime
- **Face Detection**: OpenCV Zoo YuNet ONNX (`libfacedetection`)
- **OCR Engines**: EasyOCR (JaidedAI), PaddleOCR (PaddlePaddle)
- **Web & Streaming Framework**: FastAPI, Uvicorn, Starlette
- **Database Engine**: SQLite3 (WAL Journal Mode)
- **Streaming Infrastructure**: MediaMTX (bluenviron), FFmpeg
- **Frontend Design**: HTML5, Vanilla CSS3 (Glassmorphism & Tactical Dark Theme), Lucide Icons, Google Fonts (Inter & JetBrains Mono)
