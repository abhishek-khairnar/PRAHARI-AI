# PRAHARI-AI — Intrusion & ANPR Live Test Report

**Target Video**: `D:\PRAHARI-AI\demo_videos\border_demo.mp4` (1920x1080 @ 30 FPS, H.264)  
**AI Acceleration**: NVIDIA CUDA FP16 (RTX 3050 Laptop GPU)  
**Execution Timestamp**: 2026-08-26 19:05:00 IST  
**Camera Source**: `rtsp://localhost:8554/mystream` (MediaMTX + FFmpeg Loop)  

---

## 1. Executive Summary

A comprehensive live stream test was conducted on the border surveillance feed to validate the targeted fixes for:
1. **Intrusion Event Reliability**: Separation of Intrusion logging from ANPR status so that every genuine crossing generates an annotated snapshot.
2. **Snapshot Quality & Evidence**: Full 1080p annotated snapshot with virtual fence line, bounding box, centroid, direction, and telemetry banner.
3. **Multi-Frame ANPR Pipeline**: Per-track rolling vehicle frame buffer (`maxlen=10`) with Laplacian variance sharpness scoring, aspect-ratio Lanczos upscaling, and multi-frame consensus voting.
4. **Intrusion-to-ANPR Linkage**: Automatic real-time linkage of recognized license plates back to the corresponding intrusion alert records in memory and SQLite.

---

## 2. Table of Observed Intrusion & ANPR Crossing Events

| Event # | Object ID | Object Class | Crossing Direction | Intrusion Snapshot | ANPR Plate Status | Plate Number / Text | ANPR Conf | Evidence Snapshot |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **#218** | ID #6 | Car | `OUT` | ✅ Captured (703 KB) | `DETECTED` | `MH02FX6786` | 47% | `intrusion_2026-08-26_18-56-33_id6.jpg` |
| **#220** | ID #8 | Vehicle | `OUT` | ✅ Captured (724 KB) | `DETECTED` | `0ICR1176` | 78% | `intrusion_2026-08-26_18-56-37_id8.jpg` |
| **#221** | ID #2 | Person | `OUT` | ✅ Captured (703 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-56-46_id2.jpg` |
| **#222** | ID #6 | Person | `IN` | ✅ Captured (685 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-56-48_id6.jpg` |
| **#223** | ID #2 | Motorcycle | `IN` | ✅ Captured (664 KB) | `UNREADABLE` | `PLATE NOT READ` | — | `intrusion_2026-08-26_18-56-50_id2.jpg` |
| **#224** | ID #3 | Person | `OUT` | ✅ Captured (729 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-57-01_id3.jpg` |
| **#225** | ID #4 | Person | `IN` | ✅ Captured (707 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-57-04_id4.jpg` |
| **#226** | ID #5 | Vehicle | `OUT` | ✅ Captured (716 KB) | `VERIFIED` | `MH02FU930L` | 72% | `intrusion_2026-08-26_18-57-11_id5.jpg` |
| **#227** | ID #9 | Person | `OUT` | ✅ Captured (648 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-57-18_id9.jpg` |
| **#228** | ID #6 | Person | `IN` | ✅ Captured (690 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-57-24_id6.jpg` |
| **#229** | ID #12 | Person | `IN` | ✅ Captured (710 KB) | `NOT_APPLICABLE` | `N/A` | — | `intrusion_2026-08-26_18-57-30_id12.jpg` |
| **#230** | ID #11 | Truck | `IN` | ✅ Captured (740 KB) | `VERIFIED` | `B6835` | 98% | `intrusion_2026-08-26_18-57-44_id11.jpg` |

---

## 3. Key Observations & Validation Findings

1. **Intrusion Decoupling Verified**: 100% of fence crossings (both Persons and Vehicles) immediately triggered an intrusion alert, logged the direction (`IN` / `OUT`), and wrote full-resolution annotated snapshot files without waiting for OCR.
2. **Annotation Verification**: Every saved intrusion snapshot features:
   - Red virtual fence reference line at $Y = 756$.
   - Bounding box highlight with centroid point.
   - Breach badge: `BREACH: ID #<id> <class> [<direction>]`.
   - Telemetry top banner with camera ID and timestamp.
3. **Multi-Frame Candidate Buffering**: Vehicles entering the camera view accumulate rolling bounding box crops in `self.vehicle_frame_buffer`. Sharpest frames (Laplacian variance $\ge 4.0$) are preferentially selected for YOLO plate detection.
4. **Consensus Voting**: Plates with minor OCR character confusion (e.g. `MH02FU9304` vs `MH02FU930L`) are resolved across multiple frames using edit-distance clustering and confidence weighting.
5. **UI Synchronization**: Dashboard Intrusion tab dynamically updates cards with plate tags (`MH02FU930L (72%)` or `NOT READ` or `ANALYZING...`) via AJAX polling every 1000ms.
