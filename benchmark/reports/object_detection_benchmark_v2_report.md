# PRAHARI-AI — PHASE A1: OBJECT DETECTION BENCHMARK V2 REPORT
**Date**: 2026-09-12  
**System**: PRAHARI-AI  
**Hardware Evaluated**: NVIDIA GeForce RTX 3050 (6GB VRAM)  
**Methodology**: Class-Aware 1-to-1 Spatial IoU Bounding Box Matching (IoU threshold = 0.50)  
**Production Pipeline Status**: Strictly Frozen (imgsz=640, conf=0.35, classes=[0,1,2,3,5,7], model=weights/yolov8n.pt)

---

## 1. EXISTING BENCHMARK METHODOLOGY PROBLEMS FOUND
A deep forensic audit of the legacy benchmark (`benchmark/video_analysis.py` and `benchmark/ground_truth.py`) revealed several critical methodological flaws:
1. **Scalar Count-Difference Matching (No Spatial Localization)**:
   - Detection evaluation was performed using scalar counts: `diff = abs(len(pred_boxes) - gt_count)`.
   - If 3 persons were present, a prediction of 3 background clutter false alarms in opposite corners resulted in `diff = 0`, falsely scoring 100% precision and 100% recall.
   - True spatial detection performance was masked by count cancellations.
2. **Missing Ground-Truth Bounding Boxes**:
   - `CAM-02` (Night highway) had zero bounding-box annotations across all frames (only a coarse scalar integer).
   - `CAM-01`, `CAM-03`, and `CAM-04` had spatial bounding boxes defined for only 3 single frames (f0, f40, and f0 respectively).
   - Vehicles had **0 spatial bounding-box annotations** across the entire repository.
3. **Class-Agnostic Matching Function**:
   - The legacy `match_boxes()` function in `benchmark/metrics.py` matched boxes purely based on spatial IoU overlap without verifying class identity (`pred_class == gt_class`).
   - A predicted car overlapping a pedestrian could be counted as a True Positive for pedestrian detection.
4. **False "PASS" Logic**:
   - Evaluator returned PASS if code ran without exception or counts fell within generous arbitrary bands, regardless of whether spatial overlap was valid.

---

## 2. FILES MODIFIED
All modifications were strictly constrained to the benchmark framework and benchmark tests:
- `benchmark/metrics.py`: Implemented `match_objects_class_aware()` (class compatibility, greedy 1-to-1 matching, disjoint TP/FP/FN assignment), and `compute_ap_from_pr()`.
- `benchmark/ground_truth.py`: Added `OBJECT_DETECTION_GT_V2` containing multi-camera, multi-frame spatial bounding boxes with audited classes (`person`, `car`, `truck`, `motorcycle`, `bus`) and categorization (`large_near`, `small_distant`, `occluded`, `unoccluded`).
- `benchmark/video_analysis.py`: Added `evaluate_object_detection_v2()`, offline `evaluate_confidence_threshold_sweep()`, and offline `evaluate_imgsz_sweep()`.
- `benchmark/run_benchmark.py`: Integrated steps [4B/10], [4C/10], and [4D/10] into the automated benchmark harness.
- `tests/test_benchmark.py`: Added `TestObjectDetectionV2` with 21 focused unit tests (IoU math, zero-area, non-overlap, 1-to-1 matching, class incompatibility, false positive/negative handling, count MAE, AP50, isolation, parameter freeze).
- `benchmark/results/object_detection_v2.json`: Structured evaluation results.
- `benchmark/results/threshold_analysis.json`: Offline confidence sweep results.
- `benchmark/results/imgsz_analysis.json`: Offline resolution sweep results.

---

## 3. FILES INTENTIONALLY FROZEN
The production AI runtime and infrastructure remained untouched:
- `anpr_engine.py` (FROZEN)
- `anpr_consensus.py` (FROZEN)
- `rtsp_stream.py` (FROZEN)
- `camera_manager.py` (FROZEN)
- `centroid_tracker.py` (FROZEN)
- `main.py` (FROZEN)
- `database.py` (FROZEN)
- `prahari_events.db` (FROZEN — Verified row counts identical before and after)
- `weights/yolov8n.pt` (FROZEN — Verified SHA256)
- `weights/license-plate-finetune-v1n.pt` (FROZEN — Verified SHA256)
- `weights/face_detection_yunet_2023mar.onnx` (FROZEN — Verified SHA256)
- Frontend and REST API contracts (FROZEN)
- Production parameters (`imgsz=640`, `conf=0.35`, `classes=[0,1,2,3,5,7]`) (FROZEN)

---

## 4. GROUND-TRUTH COVERAGE (`OBJECT_DETECTION_GT_V2`)
Ground truth was established using verified spatial coordinates `[x1, y1, x2, y2]` across all 4 configured demo cameras:
- **CAM-01 (Border Post Alpha)**:
  - Frame 0 (1920x1080): 5 Persons (booth guard, incoming officer, barrier patrol, distant officers), 3 Cars (sedans at barrier), 1 Truck (military cargo truck).
  - Frame 60 (1920x1080): 4 Persons, 3 Cars, 1 Truck.
- **CAM-02 (Night Surveillance Bravo)**:
  - 5 Temporal Frames (f0, f60, f120, f180, f240) spanning daylight, lighting transition, and full infrared/night:
  - 5 Cars, 1 Heavy Truck.
- **CAM-03 (Perimeter Activity Charlie)**:
  - 3 Temporal Frames (f40, f120, f390) (1920x1080): 3 Loitering Persons across field grass, fence line, and fence approach.
- **CAM-04 (Urban Facility Delta)**:
  - Frame 0 (1280x720): 5 Pedestrians (crosswalk/sidewalk), 4 Passenger Cars, 2 Motorcycles/Scooters.
- **Total Evaluated Annotations**: 37 Ground-Truth Spatial Objects across 11 distinct multi-condition frames.

---

## 5. IoU METHODOLOGY
- **Bounding Box Format**: `[x1, y1, x2, y2]`.
- **Intersection over Union (IoU)**:
  $$\text{IoU} = \frac{\text{Area}(\text{Box}_A \cap \text{Box}_B)}{\text{Area}(\text{Box}_A \cup \text{Box}_B)}$$
  Zero-area boxes and invalid geometries return `0.0`.
- **Class-Aware Constraint**: A prediction $P_j$ and ground truth $G_i$ can match **only if** $\text{class}(P_j) == \text{class}(G_i)$. Cross-class matching is strictly forbidden.
- **One-to-One Matching**: Predictions are sorted by confidence descending. For each prediction, the unassigned ground-truth object of the same class with the highest $\text{IoU} \ge 0.50$ is matched. Remaining predictions are False Positives (FP); unmatched ground truths are False Negatives (FN).

---

## 6. CAM-01 METRICS (Border Post Alpha)
- **Status**: `FAIL`
- **Reason**: Person F1 (`0.5714`) < `0.7000` numerical threshold; Overall F1 (`0.6190`) < `0.7000`.
- **Per-Class Breakdown**:
  | Class | GT Count | Pred Count | TP | FP | FN | Precision | Recall | F1-Score | AP50 |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **person** | 9 | 12 | 6 | 6 | 3 | 0.5000 | 0.6667 | **0.5714** | 0.4213 |
  | **car** | 6 | 11 | 6 | 5 | 0 | 0.5455 | 1.0000 | **0.7059** | 0.8571 |
  | **motorcycle**| 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **bus** | 0 | 1 | 0 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **truck** | 2 | 1 | 1 | 0 | 1 | 1.0000 | 0.5000 | **0.6667** | 0.5000 |
- **Macro Average**: Precision = 0.6818, Recall = 0.7222, **Macro F1 = 0.7015**.
- **Overall**: TP = 13, FP = 12, FN = 4, Precision = 0.5200, Recall = 0.7647, **Overall F1 = 0.6190**, Count MAE = 4.0.

---

## 7. CAM-02 METRICS (Night Surveillance Bravo)
- **Status**: `PASS`
- **Reason**: Overall F1 (`0.9231`) and Macro F1 (`0.9565`) meet acceptance criteria (>0.70).
- **Per-Class Breakdown**:
  | Class | GT Count | Pred Count | TP | FP | FN | Precision | Recall | F1-Score | AP50 |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **person** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **car** | 5 | 6 | 5 | 1 | 0 | 0.8333 | 1.0000 | **0.9091** | 1.0000 |
  | **motorcycle**| 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **bus** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **truck** | 1 | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | **1.0000** | 1.0000 |
- **Macro Average**: Precision = 0.9166, Recall = 1.0000, **Macro F1 = 0.9565**.
- **Overall**: TP = 6, FP = 1, FN = 0, Precision = 0.8571, Recall = 1.0000, **Overall F1 = 0.9231**, Count MAE = 0.2.

---

## 8. CAM-03 METRICS (Perimeter Activity Charlie)
- **Status**: `FAIL`
- **Reason**: Person F1 (`0.2857`) < `0.7000` numerical threshold; Overall F1 (`0.2857`) < `0.7000`.
- **Per-Class Breakdown**:
  | Class | GT Count | Pred Count | TP | FP | FN | Precision | Recall | F1-Score | AP50 |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **person** | 3 | 4 | 1 | 3 | 2 | 0.2500 | 0.3333 | **0.2857** | 0.3333 |
  | **car** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **motorcycle**| 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **bus** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **truck** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
- **Macro Average**: Precision = 0.2500, Recall = 0.3333, **Macro F1 = 0.2857**.
- **Overall**: TP = 1, FP = 3, FN = 2, Precision = 0.2500, Recall = 0.3333, **Overall F1 = 0.2857**, Count MAE = 0.33.

---

## 9. CAM-04 METRICS (Urban Facility Delta)
- **Status**: `PASS`
- **Reason**: Overall F1 (`0.8462`) and Macro F1 (`0.8387`) meet acceptance criteria (>0.70).
- **Per-Class Breakdown**:
  | Class | GT Count | Pred Count | TP | FP | FN | Precision | Recall | F1-Score | AP50 |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **person** | 5 | 5 | 5 | 0 | 0 | 1.0000 | 1.0000 | **1.0000** | 1.0000 |
  | **car** | 4 | 6 | 4 | 2 | 0 | 0.6667 | 1.0000 | **0.8000** | 0.9500 |
  | **motorcycle**| 2 | 4 | 2 | 2 | 0 | 0.5000 | 1.0000 | **0.6667** | 1.0000 |
  | **bus** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
  | **truck** | 0 | 0 | 0 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 | N/A |
- **Macro Average**: Precision = 0.7222, Recall = 1.0000, **Macro F1 = 0.8387**.
- **Overall**: TP = 11, FP = 4, FN = 0, Precision = 0.7333, Recall = 1.0000, **Overall F1 = 0.8462**, Count MAE = 4.0.

---

## 10. PERSON-SPECIFIC ANALYSIS
Person detection is confirmed to be the primary vulnerability of YOLOv8n in the perimeter surveillance environment:
- **Across All Cameras**: Total GT Persons = 17, TP = 12, FP = 9, FN = 5.
- **Precision**: `0.5714`, **Recall**: `0.7059`, **F1-Score**: `0.6316`.
- **Category Breakdown**:
  - `large_near` (10 GT): 6 TP, 4 FN (60% recall). Misses occur when guards are standing static beside infrastructure or guard booths.
  - `small_distant` (7 GT): 6 TP, 1 FN (85.7% recall). Well-contrasted urban pedestrians in CAM-04 are detected cleanly; distant perimeter loiterers in CAM-03 blend into background foliage and fail detection.
  - `occluded` (3 GT): 3 TP, 0 FN (100% recall). Partial occlusions (e.g. waist-down occluded by vehicle) were detected when upper body was distinct.
  - `unoccluded` (14 GT): 9 TP, 5 FN (64.3% recall).
- **False Alarm Profile**: FP persons in CAM-01 and CAM-03 are caused by upright infrastructure elements (fence posts, barrier support pillars, tree trunks) exceeding the 0.35 confidence threshold.

---

## 11. VEHICLE DETECTION RESULTS
Vehicle detection exhibits significantly higher recall and stability than person detection:
- **Cars**: Total GT = 15, TP = 15, FP = 8, FN = 0. **Recall = 100%**, Precision = 65.2%, F1 = 0.7895. (Zero missed cars across all cameras and illumination regimes).
- **Motorcycles**: Total GT = 2, TP = 2, FP = 2, FN = 0. **Recall = 100%**, Precision = 50.0%, F1 = 0.6667.
- **Buses**: Total GT = 0, Pred = 1 (1 FP in CAM-01 where a large van/canopy was misclassified).

---

## 12. TRUCK CLASSIFICATION RESULT & FORENSIC AUDIT
In previous unverified reports, truck classification accuracy was reported as abnormally low (0% to 50%). Under our rigorous class-aware spatial IoU matching, the root cause is now precisely diagnosed:
- **Total Ground-Truth Trucks Evaluated**: 3
- **Predicted as Truck**: 2 (CAM-01 Frame 60, CAM-02 Frame 120).
- **Predicted as Car**: 1 (CAM-01 Frame 0, box `[1255, 391, 1398, 568]`, predicted as `car` with confidence `0.42` and spatial IoU `1.0` with the ground-truth truck).
- **Audit Conclusion**:
  Under class-aware matching, `car != truck`. Therefore, the detector receives **1 False Negative for Truck** and **1 False Positive for Car**.
  YOLOv8n nano feature representations lack the capacity to differentiate medium-distance cargo trucks from SUVs/vans at 640x640 resolution, causing truck recall to drop to 50% in CAM-01.

---

## 13. BENCHMARK-ONLY CONFIDENCE THRESHOLD ANALYSIS
*Evaluated offline on frozen model weights. Production config remains frozen at conf=0.35.*

| Operating Point | Overall Precision | Overall Recall | Overall F1 | Person Precision | Person Recall | Person F1 | False Positives | False Negatives |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **conf = 0.20** | 0.4306 | 0.8378 | 0.5688 | 0.4138 | 0.7059 | 0.5217 | 41 | 6 |
| **conf = 0.25** | 0.4844 | 0.8378 | 0.6139 | 0.4615 | 0.7059 | 0.5581 | 33 | 6 |
| **conf = 0.30** | 0.5345 | 0.8378 | 0.6526 | 0.5217 | 0.7059 | 0.6000 | 27 | 6 |
| **conf = 0.35 (Frozen)** | **0.6078** | **0.8378** | **0.7045** | **0.5714** | **0.7059** | **0.6316** | **20** | **6** |
| **conf = 0.40** | 0.6000 | 0.7297 | 0.6585 | 0.4706 | 0.4706 | 0.4706 | 18 | 10 |

### Key Insight:
`conf = 0.35` is empirically the optimal threshold for `yolov8n.pt`. Lowering confidence to 0.20–0.30 produces zero additional true positives (recall remains capped at 0.8378), but doubles false alarms (FP rises from 20 to 41). Raising confidence to 0.40 severely degrades person recall (from 70.6% down to 47.1%).

---

## 14. BENCHMARK-ONLY IMAGE SIZE RESOLUTION ANALYSIS
*Evaluated offline on NVIDIA RTX 3050 (6GB VRAM). Production config remains frozen at imgsz=640.*

| Resolution | Overall F1 | Person F1 | Macro F1 | Avg Latency / Frame | FPS | CUDA VRAM Allocated |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **640x640 (Frozen)** | **0.7045** | **0.6316** | **0.6956** | 124.87 ms | 8.01 FPS | 12.10 MB |
| **768x768** | 0.6452 | 0.5500 | 0.6589 | 116.49 ms | 8.58 FPS | 12.12 MB |
| **960x960** | 0.5895 | 0.5714 | 0.4602 | 112.38 ms | 8.90 FPS | 12.16 MB |

### Key Insight:
Increasing image resolution on the raw COCO-trained `yolov8n.pt` without retraining degrades detection performance (F1 drops from 0.70 to 0.59). The increased resolution introduces anchor scale mismatches and amplifies background texture clutter, generating 50% more false positives (FP rises from 20 to 30) without improving true recall.

---

## 15. ANNOTATION LIMITATIONS
1. Video inventory relies on 4 short synthetic/demo clips (`border_demo.mp4`, `night_demo.mp4`, `activity-demo.mp4`, `cctv_demo.mp4`).
2. Two cameras (`CAM-02` and `CAM-03`) contain zero motorcycles or buses in their ground-truth scenes.
3. Distant perimeter figures in `CAM-03` have subtle pixel signatures (~25px height) against natural grassland, where even human annotators require multi-frame temporal motion cues.

---

## 16. OLD VS NEW METRICS COMPARISON
| Dimension | Legacy Benchmark V1 | Benchmark V2 (Phase A1) |
| :--- | :--- | :--- |
| **Matching Scheme** | Scalar Count Difference (`\|pred - gt\|`) | Class-Aware 1-to-1 Spatial IoU ($\ge 0.50$) |
| **Spatial Ground Truth** | 3 single frames across repo; 0 vehicle boxes | 11 multi-camera frames; 37 verified spatial boxes |
| **Class Isolation** | Class-agnostic (Car could match Person) | Strict class compatibility ($P_{class} == G_{class}$) |
| **CAM-01 Reported** | Precision: 0.88, Recall: 0.88 (Flawed) | Overall F1: **0.6190** (`FAIL`), Person F1: **0.5714** |
| **CAM-02 Reported** | Not Evaluated (Count = 0) | Overall F1: **0.9231** (`PASS`), Car/Truck AP50: **1.00** |
| **CAM-03 Reported** | Precision: 0.75, Recall: 0.75 (Flawed) | Overall F1: **0.2857** (`FAIL`), Person F1: **0.2857** |
| **CAM-04 Reported** | Precision: 0.92, Recall: 0.92 (Flawed) | Overall F1: **0.8462** (`PASS`), Person F1: **1.0000** |
| **Pass/Fail Criteria**| Implicit / Code Execution Success | Explicit numerical thresholds ($F1 \ge 0.70$) |

---

## 17. TEST RESULTS & VERIFICATION
All four test suites passed without a single failure or regression:
- `tests/test_benchmark.py`: **53 / 53 PASSED** (includes 21 new Phase A1 tests)
- `tests/test_anpr_accuracy_fix.py`: **44 / 44 PASSED**
- `tests/test_p0_regressions.py`: **13 / 13 PASSED**
- `tests/test_full_suite.py`: **9 / 9 PASSED**
- **Grand Total**: **119 / 119 PASSED** (0 failures, 0 errors)

---

## 18. PRODUCTION INTEGRITY VERIFICATION
- **Production Database**: `prahari_events.db` verified completely unmodified.
  - `intrusion_events`: 25,598 rows (Unchanged)
  - `anpr_events`: 4,115 rows (Unchanged)
  - `system_events`: 284 rows (Unchanged)
  - `security_events`: 5,869 rows (Unchanged)
- **Model Weights SHA256 Hashes**:
  - `weights/yolov8n.pt`: `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` (VERIFIED)
  - `weights/license-plate-finetune-v1n.pt`: `0aec75976c56eb6f26dfb274c430620ec65137915ff1ae47c3a48c7af8afb7b2` (VERIFIED)
  - `weights/face_detection_yunet_2023mar.onnx`: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` (VERIFIED)
- **Production Runtime Parameters**: Strictly frozen at `conf=0.35`, `imgsz=640`, `classes=[0,1,2,3,5,7]`.

---

## 19. EXACT NEXT ENGINEERING RECOMMENDATION (PHASE A2)
With our trustworthy, class-aware spatial IoU benchmark now established, the empirical evidence demonstrates:
1. **DO NOT simply change confidence threshold in production**: `0.35` is already the optimal operating point for `yolov8n.pt`.
2. **DO NOT arbitrarily increase `imgsz` to 768 or 960 on the base model**: It degrades precision and increases false positives.
3. **DO NOT replace the entire tracker or pipeline logic**: The tracker functions correctly when provided reliable detections.
4. **RECOMMENDED PHASE A2 ACTION**:
   - The primary bottleneck is model feature capacity and domain specificity on distant perimeter surveillance (`CAM-01` Person F1=0.57, `CAM-03` Person F1=0.29) and truck vs car confusion (`CAM-01` f0).
   - Evaluate a targeted fine-tune or higher-capacity detector (e.g. `yolov8s.pt` or a perimeter-security fine-tuned checkpoint) evaluated against this exact `OBJECT_DETECTION_GT_V2` spatial benchmark harness before touching production configurations.
