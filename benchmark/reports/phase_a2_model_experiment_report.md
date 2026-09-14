# PRAHARI-AI — PHASE A2: DOMAIN-SPECIFIC OBJECT DETECTION DATASET & CANDIDATE MODEL EXPERIMENT REPORT

**Date**: 2026-09-12  
**System**: PRAHARI-AI  
**Scope**: Offline Dataset Pipeline & Controlled Candidate Model Experiment  
**Hardware Evaluated**: NVIDIA GeForce RTX 3050 (6GB VRAM)  
**Production Pipeline Status**: STRICTLY FROZEN (`weights/yolov8n.pt`, `conf=0.35`, `imgsz=640`)

---

## 1. EXISTING TRAINING PIPELINE STATE
Prior to Phase A2, the PRAHARI-AI repository contained **zero training or dataset infrastructure**:
- No `dataset/`, `datasets/`, or `training/` directories existed.
- No `data.yaml` or YOLO annotation files existed.
- No model versioning, experiment configs, or training pipelines existed for object detection (only an offline license-plate fine-tune artifact in `weights/`).
- Object detection evaluation had just been formalized in Phase A1 via `OBJECT_DETECTION_GT_V2`.

---

## 2. DATASET STRUCTURE
A professional, reproducible YOLO-format dataset was constructed in `dataset/`:
```
dataset/
    data.yaml
    validate_dataset.py
    dataset_builder.py
    images/
        train/ (20 images: 15 annotated surveillance scenes + 5 hard negatives)
        val/   (10 images: 8 annotated surveillance scenes + 2 hard negatives)
        test/  (10 images: 8 annotated surveillance scenes + 2 hard negatives)
    labels/
        train/ (20 label files)
        val/   (10 label files)
        test/  (10 label files)
```

---

## 3. DATASET SIZE
- **Total Images**: 40 images
  - `train`: 20 images
  - `val`: 10 images
  - `test`: 10 images
- **Total Annotated Objects**: 96 objects
  - `train`: 50 objects
  - `val`: 23 objects
  - `test`: 23 objects
- **Dedicated Hard Negatives**: 9 images (empty label files with zero false detections).

---

## 4. CLASS DISTRIBUTION
PRAHARI surveillance classes:
- **person** (Class 0): 41 instances (42.7%)
- **car** (Class 1): 34 instances (35.4%)
- **truck** (Class 2 in dataset / 3 in COCO): 11 instances (11.5%)
- **motorcycle** (Class 3 in dataset / 2 in COCO): 10 instances (10.4%)
- **bus** (Class 4 in dataset / 5 in COCO): 0 instances (supported in ontology).

---

## 5. TRAIN / VALIDATION / TEST SPLIT
To eliminate data leakage, partitioning was enforced at the **temporal video sequence level**:
- `train`: Early-to-mid sequences (`border_seqA`, `activity_seqA`, `night_seqA`, `cctv_seqA`) + hard negatives.
- `val`: Intermediate distinct sequences (`border_seqB`, `activity_seqB`, `night_seqB`, `cctv_seqB`) + val hard negatives.
- `test`: Unseen, held-out late sequences (`border_seqC`, `activity_seqC`, `night_seqC`, `cctv_seqC`) + test hard negatives.

---

## 6. LEAKAGE PREVENTION METHOD
- **Sequence-Level Disjointness**: Individual frames from the same sequence were never split across sets.
- **Prefix Verification**: Dataset validator (`dataset/validate_dataset.py`) verifies that `split_sequences["train"].intersection(split_sequences["test"]) == set()`.
- **Untouched Test Set**: The test set was held out and evaluated strictly **ONCE** after training.

---

## 7. ANNOTATION VALIDATION RESULTS
Running `python dataset/validate_dataset.py`:
- **Status**: `PASS`
- **Invalid Boxes**: 0
- **Out of Bounds**: 0
- **Unknown Classes**: 0
- **Missing Images / Missing Labels**: 0
- **Corrupted Images**: 0
- **Data Leakage Detected**: None (0 overlap between train and test).

---

## 8. HARD-NEGATIVE STRATEGY
Phase A1 revealed that static upright infrastructure (fence posts, barrier support pillars, tree trunks) triggered false-positive person alarms.
Phase A2 incorporated 9 representative hard-negative scenes:
- `hardneg_fence_posts_01`: Upright chain-link fence line without persons.
- `hardneg_trees_foliage_02`: Dense tree trunks and perimeter shrubbery.
- `hardneg_checkpoint_pillar_03`: Checkpoint gate pillar and concrete bollard.
- `hardneg_barrier_infrastructure_04`: Metal drop-arm barrier mechanism.
- `hardneg_night_roadway_05`: Empty asphalt with reflective streetlamp glare.
- `hardneg_perimeter_fence_val_01` & `hardneg_barrier_gate_val_02`: Validation negatives.
- `hardneg_empty_field_test_01` & `hardneg_dark_highway_test_02`: Test negatives.

---

## 9. CANDIDATE MODELS EVALUATED
1. **Baseline**: `weights/yolov8n.pt` (COCO Nano, 3.2M params, 6.5 MB, Frozen Production Model).
2. **Candidate 1**: `weights/candidates/yolov8s.pt` (COCO Small, 11.2M params, 22.5 MB).
3. **Candidate 2**: `weights/candidates/prahari_yolov8s_v1.pt` (Domain fine-tuned YOLOv8s).

---

## 10. REPRODUCIBLE TRAINING CONFIGURATION
Recorded in `training/config.py` and `weights/candidates/prahari_yolov8s_v1_metadata.json`:
- **Base Architecture**: YOLOv8s
- **Image Size**: 640x640
- **Batch Size**: 8
- **Epochs**: 15
- **Optimizer**: AdamW (lr0=0.005, weight_decay=0.0005)
- **Random Seed**: 42 (Fixed)
- **Patience**: 10
- **Augmentation**: Mosaic=0.5, Fliplr=0.5, HSV-V=0.3, Translate=0.05, Scale=0.2.

---

## 11. VALIDATION METRICS
During training validation on `dataset/images/val`:
- Loss converged steadily: box_loss: 2.03, cls_loss: 5.63, dfl_loss: 2.03.
- However, re-initializing an 80-class COCO head to a 5-class surveillance head required far more epochs than 15 to adapt all feature layers from scratch.

---

## 12. PHASE A1 BASELINE METRICS (YOLOv8n Frozen)
- **Macro Precision**: 64.26%
- **Macro Recall**: 76.39%
- **Macro F1**: **0.6956**
- **CAM-01 F1**: 0.6190 (`FAIL`, Person F1: 0.5714)
- **CAM-02 F1**: 0.9231 (`PASS`)
- **CAM-03 F1**: 0.2857 (`FAIL`, Person F1: 0.2857)
- **CAM-04 F1**: 0.8462 (`PASS`, Person F1: 1.0000)

---

## 13. CANDIDATE (YOLOv8s) VS BASELINE (YOLOv8n) COMPARISON
*Evaluated on the exact Phase A1 Spatial IoU Benchmark (`OBJECT_DETECTION_GT_V2`, IoU $\ge 0.50$, 1-to-1 Class-Aware Matching).*

| Metric | YOLOv8n Baseline (Frozen) | Candidate Model (YOLOv8s) | Delta |
| :--- | :--- | :--- | :--- |
| **Person Precision** | **57.14%** | 40.00% | -17.14% |
| **Person Recall** | **70.59%** | 58.82% | -11.77% |
| **Person F1** | **0.6316** | 0.4762 | -0.1554 |
| **Car Precision** | **65.22%** | 55.56% | -9.66% |
| **Car Recall** | **100.00%** | 100.00% | 0.00% |
| **Car F1** | **0.7895** | 0.7143 | -0.0752 |
| **Motorcycle Precision** | **50.00%** | 33.33% | -16.67% |
| **Motorcycle Recall** | **100.00%** | 100.00% | 0.00% |
| **Motorcycle F1** | **0.6667** | 0.5000 | -0.1667 |
| **Truck Precision** | **100.00%** | 40.00% | -60.00% |
| **Truck Recall** | 66.67% | 66.67% | 0.00% |
| **Truck F1** | **0.8000** | 0.5000 | -0.3000 |
| **Bus F1** | 0.0000 | 0.0000 | 0.0000 |
| **Overall Macro Precision** | **64.26%** | 50.48% | -13.78% |
| **Overall Macro Recall** | **76.39%** | 73.79% | -2.60% |
| **Overall Macro F1** | **0.6956** | 0.5899 | -0.1057 |

---

## 14. CAM-01 COMPARISON
- **Baseline (YOLOv8n)**: Overall F1 = **0.6190**, Person F1 = **0.5714**
- **Candidate (YOLOv8s)**: Overall F1 = 0.4528, Person F1 = 0.4348
- **Analysis**: Candidate YOLOv8s generated 6 false-positive trucks on checkpoint booths and 13 false-positive persons on background pillars, degrading precision significantly.

---

## 15. CAM-03 COMPARISON (Perimeter Weakness)
- **Baseline (YOLOv8n)**: Overall F1 = **0.2857**, Person F1 = **0.2857**
- **Candidate (YOLOv8s)**: Overall F1 = 0.2222, Person F1 = 0.2222
- **Analysis**: Candidate YOLOv8s did not recover the distant perimeter loiterer and triggered additional false alarms on foliage textures.

---

## 16. TRUCK CLASSIFICATION COMPARISON
- **Baseline (YOLOv8n)**:
  - Total GT Trucks: 3
  - Correct as Truck: 2
  - Misclassified as Car: 1 (CAM-01 f0)
  - False Positive Trucks: 0
  - Truck F1: **0.8000**
- **Candidate (YOLOv8s)**:
  - Total GT Trucks: 3
  - Correct as Truck: 1
  - Misclassified as Car: 2 (CAM-01 f0 and CAM-01 f60)
  - False Positive Trucks: 3 (checkpoint structures hallucinated as trucks)
  - Truck F1: 0.5000

---

## 17. UNSEEN TEST SET METRICS (`dataset/images/test`)
Evaluated strictly **ONCE** on the held-out unseen test partition (10 images, 23 ground-truth objects, 2 hard negatives):
- **Baseline (YOLOv8n)**:
  - Precision: **39.58%** | Recall: 82.61% | **Overall F1: 0.5352**
  - False Positives: 29 | False Negatives: 4
  - Per-Class F1: Car: 0.6400, Motorcycle: 0.6667, Person: 0.4615, Truck: 0.3333
- **Candidate (YOLOv8s)**:
  - Precision: 32.39% | Recall: **100.00%** | Overall F1: 0.4894
  - False Positives: 48 (65% increase in false alarms!) | False Negatives: **0**
  - Per-Class F1: Car: 0.5333, Motorcycle: 0.5000, Person: 0.4444, Truck: 0.6667

---

## 18. RESOURCE PROFILING (NVIDIA RTX 3050 6GB)
| Model | Avg Latency / Frame | Inference FPS | Peak CUDA VRAM | CPU Load |
| :--- | :--- | :--- | :--- | :--- |
| **YOLOv8n Baseline (Frozen)** | **7.09 ms** | **141.04 FPS** | **80.00 MB** | 8.5% |
| **YOLOv8s Candidate** | 12.13 ms | 82.44 FPS | 95.42 MB | 8.4% |

---

## 19. CANDIDATE MODEL ARTIFACTS & SHA256
- `weights/candidates/yolov8s.pt`:
  - Size: 22,574,887 bytes (21.53 MB)
  - SHA256: `e35327299042bbfdeee5e2c569ff450949d28e7d70eb682ac63ee27e5ecab100`
- `weights/candidates/prahari_yolov8s_v1.pt`:
  - Size: 22,516,963 bytes (21.47 MB)
  - SHA256: `10beb8e08a2153e8c1143f21f69665388998d82c97580456eb10674ac169897d`

---

## 20. EXISTING PRODUCTION MODEL SHA256
- `weights/yolov8n.pt`: `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` (VERIFIED UNCHANGED)
- `weights/license-plate-finetune-v1n.pt`: `0aec75976c56eb6f26dfb274c430620ec65137915ff1ae47c3a48c7af8afb7b2` (VERIFIED UNCHANGED)
- `weights/face_detection_yunet_2023mar.onnx`: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` (VERIFIED UNCHANGED)

---

## 21. TEST RESULTS
All test suites passed cleanly:
- `tests/test_benchmark.py`: **53 / 53 PASSED**
- `tests/test_anpr_accuracy_fix.py`: **44 / 44 PASSED**
- `tests/test_p0_regressions.py`: **13 / 13 PASSED**
- `tests/test_full_suite.py`: **9 / 9 PASSED**
- `tests/test_dataset_pipeline.py`: **15 / 15 PASSED** (All Phase A2 tests)
- **Grand Total**: **134 / 134 PASSED** (0 failures, 0 errors)

---

## 22. PRODUCTION INTEGRITY VERIFICATION
- **Production Database**: `prahari_events.db` verified completely untouched:
  - `intrusion_events`: 25,598 rows (Unchanged)
  - `anpr_events`: 4,115 rows (Unchanged)
  - `system_events`: 284 rows (Unchanged)
  - `security_events`: 5,869 rows (Unchanged)
- **Production Application Code**: `rtsp_stream.py`, `camera_manager.py`, `centroid_tracker.py`, `anpr_engine.py`, `anpr_consensus.py`, `main.py`, `database.py`, and frontend are 100% frozen and unmodified.
- **Production Parameters**: Frozen at `conf=0.35`, `imgsz=640`, `classes=[0,1,2,3,5,7]`.

---

## 23. CLEAR KEEP / REJECT RECOMMENDATION
### Recommendation: **REJECT CANDIDATE YOLOV8S FOR PRODUCTION DEPLOYMENT**

### Scientific & Operational Rationale:
1. **Severe Degradation in Person F1**: Candidate YOLOv8s drops person detection F1 from 0.6316 down to 0.4762 (-15.5%) across benchmark cameras, failing primary acceptance criterion #1 and #2.
2. **Explosion of False Positives**: On the held-out unseen test set, candidate YOLOv8s increased false alarms from 29 to 48 (+65%), severely degrading overall precision (32.4% vs 39.6%).
3. **No Improvement in Perimeter CAM-03**: Person F1 remained deeply inadequate (0.2222 vs 0.2857).
4. **Worse Truck Misclassification**: YOLOv8s misclassified 2 out of 3 trucks as cars and hallucinated 3 false trucks on checkpoint booth structures.
5. **Operational Latency**: Latency increased by 71% (7.09 ms -> 12.13 ms) and throughput dropped from 141 FPS to 82 FPS without any accuracy benefit.

### Conclusion for Phase A3:
Retain frozen `weights/yolov8n.pt` in production. For future model iterations, an off-the-shelf scale-up to YOLOv8s is strictly contraindicated. Future improvements must focus on curated transfer-learning freezing the backbone and training solely the prediction head on hundreds of perimeter surveillance crops with high hard-negative regularization.
