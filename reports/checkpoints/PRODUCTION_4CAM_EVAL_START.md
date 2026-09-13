# PRAHARI-AI — Checkpoint: PRODUCTION_4CAM_EVAL_START

Timestamp: 2026-09-12T21:06:30+05:30
Git Commit: cd4b889ddb06604bda3b56fa53efebccb18eb538
Production Model Path: weights/yolov8n.pt
Production Model SHA256: F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36
Hash Match Verified: YES

Python Version: 3.11.9
CUDA Availability: True
GPU Name: NVIDIA GeForce RTX 3050 6GB Laptop GPU
Project Working Directory: D:\PRAHARI-AI
Missing Dependencies: NONE

## Demo Video Registry

| Camera | Channel Name | Source Video File | Resolution | FPS | Frame Count | Duration | File Size | Decode Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CAM-01** | Border Post Alpha | `demo_videos/border_demo.mp4` | 1920x1080 | 30.00 | 401 | 13.37s | 10.30 MB | **PASS** |
| **CAM-02** | Night Surveillance Bravo | `demo_videos/night_demo.mp4` | 720x1280 | 30.00 | 300 | 10.00s | 1.81 MB | **PASS** |
| **CAM-03** | Perimeter Activity Charlie | `demo_videos/activity-demo.mp4` | 1920x1080 | 24.00 | 515 | 21.46s | 2.34 MB | **PASS** |
| **CAM-04** | Urban Facility Delta | `demo_videos/cctv_demo.mp4` | 1280x720 | 29.97 | 271 | 9.04s | 3.33 MB | **PASS** |

Total Frames to Evaluate across 4 Cameras: 1,487 frames
Total Video Duration: 53.87 seconds
Evaluation Mode: Production Pipeline End-to-End Simulation (Detection, Tracking, Intrusion, ANPR, Events, Database)
Production Modified: NO
Production Model Modified: NO
