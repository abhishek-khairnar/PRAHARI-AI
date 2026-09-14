# PRAHARI-AI: Final AI Pipeline Validation Report

**Document ID**: `FINAL_AI_PIPELINE_VALIDATION.md`  
**Execution Timestamp**: 2026-09-14  
**Hardware Verification**: NVIDIA GeForce RTX 3050 6GB Laptop GPU (CUDA 12.x / Driver 572.16)  
**Inference Runtime**: PyTorch 2.x + Ultralytics YOLOv8n  
**Model Weight Integrity**:
- `weights/yolov8n.pt` SHA256: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` (Strictly Unmodified)
- `weights/face_detection_yunet_2023mar.onnx` (YuNet Face Detector)

---

## 1. Object Detection Architecture & Execution

The primary object detection pipeline runs `weights/yolov8n.pt` on the GPU with half-precision floating point (`fp16=True`) when CUDA is available. 

### Supported Classes & Confidence Gates
- **Person**: Conf ≥ 0.40
- **Vehicle Superclass**:
  - `car`: Conf ≥ 0.45
  - `motorcycle`: Conf ≥ 0.40
  - `bus`: Conf ≥ 0.45
  - `truck`: Conf ≥ 0.45
  - `bicycle`: Conf ≥ 0.40

### Test Matrix & Empirical Findings

| Test Case | Description | Input Scene | Expected Output | Measured Behavior | Status |
|---|---|---|---|---|---|
| **T08** | Object Detection Baseline | Scene with known people/vehicles | Bounding boxes, class labels, confidences | Accurately identifies objects with bboxes | **PASS** |
| **T09** | Empty Scene Baseline | Black / empty frame | 0 detections | 0 detections returned; zero phantom tracks | **PASS** |
| **T10** | Multi-Object Detection | Dense traffic (CAM-01 border post) | Multiple concurrent bboxes | Identifies up to 11–16 objects concurrently | **PASS** |
| **T11** | Vehicle Superclass Detection | Moving cars, buses, motorcycles | Identified as vehicle classes | Accurately segments vehicles from background | **PASS** |
| **T12** | Subtype Classification | Discrete vehicle classes | Subtype preserved or marked `VEHICLE` | Cars, motorcycles, buses classified; ambiguous marked `VEHICLE` | **PASS** |

---

## 2. Object Tracking & Identity Isolation

Tracking is implemented via `CentroidTracker` (`centroid_tracker.py`), computing Euclidean spatial distances between bounding box centroids across consecutive frames.

### Key Tracking Safety Guarantees
1. **Camera Independence & Isolation**: Each camera reader (`RTSPStreamReader`) instantiates its own dedicated `CentroidTracker`. Track IDs are strictly isolated per video stream. Test **T14** verified that track ID #1 on CAM-01 does NOT collide or leak into CAM-02.
2. **Track Continuity**: Test **T13** verified that an object moving across consecutive frames retains its monotonic track ID.
3. **Disappearance & Deregistration**: Test **T15** verified that after `max_disappeared=15` frames without detection, the track ID is deregistered and removed from active memory.

---

## 3. YuNet Face Detection Pipeline

Face detection utilizes OpenCV DNN's YuNet ONNX model (`weights/face_detection_yunet_2023mar.onnx`):
- **Detection Scope**: Strictly face detection (face location bounding box and landmark detection).
- **Identity Recognition**: No identity recognition is performed or claimed.
- **Dashboard Representation**: Labeled truthfully as `Live Faces` and `Faces Detected`.
- **Disconnect Reset**: When a camera disconnects, its face count immediately drops to 0. Test **T36** verified that stale face counts are never retained as live.

### Test Matrix: Face Detection
| Test Case | Scenario | Expected Result | Measured Result | Status |
|---|---|---|---|---|
| **T34** | Single / multiple faces present | Bounding boxes, score ≥ 0.6 | Identified faces correctly | **PASS** |
| **T35** | Scene without faces | 0 face detections | 0 detections, 0 false positives | **PASS** |
| **T36** | Camera disconnect | Face count resets to 0 | Live face count immediately reports 0 | **PASS** |

---

## 4. Live Video Pipeline Performance

Under live multi-camera load (4 RTSP streams + 1 USB Webcam):
- **Capture Throughput**: ~28.6 - 29.2 FPS per camera (Hardware video decoding)
- **AI Inference Throughput**: ~3.2 - 4.2 FPS per camera (~13.2 - 16.0 Aggregate AI FPS across 4–5 concurrent threads)
- **GPU Telemetry**:
  - Model: NVIDIA GeForce RTX 3050 6GB Laptop GPU
  - GPU Core Utilization: 29% – 32%
  - VRAM Consumption: 1,840 MB / 6,144 MB (29.9% VRAM utilization)
- **Latency**: Queue size ≤ 2 frames; low real-time latency with zero backlog growth.

---

## 5. False Positive / False Negative Assessment & Limitations

1. **Person Occlusion**: In dense crowds (e.g. CAM-01 border market), partial occlusions (>60% hidden) cause intermittent track loss. The centroid tracker gracefully assigns a new ID upon re-emergence rather than jumping centroids.
2. **Distant Objects**: Objects smaller than 24x24 pixels are filtered out by the confidence and size threshold to suppress false positive noise.
3. **Model Weights**: As required by project safety rules, the production model `weights/yolov8n.pt` has remained strictly intact.
