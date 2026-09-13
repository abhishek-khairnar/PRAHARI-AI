# PRAHARI-AI — Phase A4: Production Baseline Error Analysis

**Date**: 2026-09-12T20:07:00  
**Evaluated Model**: `weights/yolov8n.pt` (Production Frozen Baseline, SHA256: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`)  
**Evaluation Split**: Dataset V2 Validation Split (169 images, 315 ground-truth objects, 28 dedicated hard negatives)  
**Inference Configuration**: `conf=0.35`, `imgsz=640`, COCO target classes mapped to Dataset V2 schema:
- COCO `0 (person)` $\rightarrow$ `0: person`
- COCO `2 (car)` $\rightarrow$ `1: car`
- COCO `3 (motorcycle)` $\rightarrow$ `2: motorcycle`
- COCO `7 (truck)` $\rightarrow$ `3: truck`

> [!NOTE]
> All quantitative failure metrics in this report are strictly derived from the **Validation split** to prevent test set leakage, in accordance with Section 10 of the Phase A4 Specification.

---

## 1. Executive Summary & Core Findings

| Metric | Measured Baseline (Validation) | Operational Impact |
| :--- | :---: | :--- |
| **Overall Precision** | **21.90%** (168 TP / 599 FP) | Excessive false alarms (78.1% of all detections are false alarms) |
| **Overall Recall** | **53.33%** (168 TP / 147 FN) | Nearly half (46.7%) of ground-truth security targets are completely missed |
| **Overall F1-Score** | **0.3105** | Production detector is severely misaligned with site-specific surveillance camera streams |
| **CAM-03 (Night) F1** | **0.0256** (1 TP / 57 FP / 19 FN) | **Catastrophic failure** under infrared/night perimeter conditions (Recall = 5.0%) |
| **Motorcycle F1** | **0.0941** (4 TP / 50 FP / 27 FN) | Near-total failure on two-wheelers (Recall = 12.90%) |
| **Truck F1** | **0.2439** (5 TP / 18 FP / 13 FN) | Severe misclassification (frequent confusion with cars/SUVs) |
| **Hard Negatives** | **0.0 FP/image** (0 FP / 28 images) | Hard negatives at `conf=0.35` do not trigger false alarms |

---

## 2. Quantitative Per-Class Error Breakdown

```
================================================================================
CLASS-LEVEL PRODUCTION BASELINE DISPARITY (VALIDATION SET @ conf=0.35, imgsz=640)
================================================================================
Class         GroundTruth  Detections     TP     FP     FN   Precision   Recall      F1
--------------------------------------------------------------------------------
person                115         278     57    221     58     0.2050    0.4957  0.2901
car                   151         412    102    310     49     0.2476    0.6755  0.3623
motorcycle             31          54      4     50     27     0.0741    0.1290  0.0941
truck                  18          23      5     18     13     0.2174    0.2778  0.2439
--------------------------------------------------------------------------------
TOTAL                 315         767    168    599    147     0.2190    0.5333  0.3105
================================================================================
```

---

## 3. Priority Class Deep-Dive Failure Analysis

### 3.1 Class 0: PERSON (Perimeter & Intrusion Priority)
- **Ground Truth Count**: 115 objects | **Detections**: 278 | **TP**: 57 | **FP**: 221 | **FN**: 58
- **Precision**: 20.50% | **Recall**: 49.57% | **F1**: 0.2901
- **Key Failure Modes**:
  1. **Background Clutter Hallucinations (221 False Positives)**:
     - Off-the-shelf COCO weights trigger on vertical fence posts, light poles, tree trunks, and roadside signage shadows under fixed surveillance geometry.
  2. **Distant & Small Persons Missed (Size Attenuation)**:
     - 58 false negatives occur predominantly when persons are in the upper two-thirds of CAM-01 and CAM-04 or patrolling along distant fence lines ($area < 0.02$).
  3. **Occluded Persons Near Virtual Fences**:
     - Partially occluded guards or intruders crouched behind railings fail the 0.35 confidence threshold.
  4. **Motorcycle Rider Confusion**:
     - Standalone riders are frequently broken down into independent false `person` predictions rather than being detected as the combined rider-vehicle entity.

### 3.2 Class 3: TRUCK (Heavy Transport Priority)
- **Ground Truth Count**: 18 objects | **Detections**: 23 | **TP**: 5 | **FP**: 18 | **FN**: 13
- **Precision**: 21.74% | **Recall**: 27.78% | **F1**: 0.2439
- **Key Failure Modes**:
  1. **Truck-to-Car Confusion**:
     - In 6 out of 15 audited cross-class confusion samples (e.g., `cam01_seqB_val_f0240.jpg`, `cam01_seqB_val_f0246.jpg`, `cam02_seqB_val_f0169.jpg`), large cargo trucks and military utility transports are predicted as `car` with high confidence ($0.40 - 0.71$).
  2. **Truncation at Frame Boundaries**:
     - Trucks entering or exiting the camera FOV (large objects $area > 0.10$) have only partial cabins visible, causing the baseline COCO model to fail detection completely (FN).
  3. **Low Sample Representation**:
     - With only 74 train instances and 18 validation instances in Dataset V2, the baseline model has zero domain adaptation for regional Indian truck configurations (e.g., Ashok Leyland/Tata open-bed cargo carriers).

### 3.3 Class 1: CAR (Traffic & Perimeter Flow)
- **Ground Truth Count**: 151 objects | **Detections**: 412 | **TP**: 102 | **FP**: 310 | **FN**: 49
- **Precision**: 24.76% | **Recall**: 67.55% | **F1**: 0.3623
- **Key Failure Modes**:
  1. **Massive Over-Detection (310 False Positives)**:
     - The COCO baseline generates multiple overlapping bounding boxes for individual vehicles in slow-moving traffic queues. Non-Maximum Suppression (NMS) fails to collapse double-detections when bounding box proposals disagree on vehicle boundaries.
  2. **Highway Flow Reflections**:
     - Sunlight glares on asphalt, guardrails, and metallic road barriers in CAM-01 and CAM-04 are predicted as low-to-medium confidence cars.

### 3.4 Class 2: MOTORCYCLE (Two-Wheeler & High-Mobility Targets)
- **Ground Truth Count**: 31 objects | **Detections**: 54 | **TP**: 4 | **FP**: 50 | **FN**: 27
- **Precision**: 7.41% | **Recall**: 12.90% | **F1**: 0.0941
- **Key Failure Modes**:
  1. **Severe Miss Rate (87.1% Missed)**:
     - Only 4 out of 31 motorcycles in the validation set are detected. 27 two-wheelers completely evade the production model.
  2. **Rider vs. Vehicle Ambiguity**:
     - COCO models are trained on distinct `person` and `motorcycle` classes. In real-world surveillance, a rider seated on a motorcycle is routinely detected as a `person` (e.g., `cam04_seqB_val_f0136.jpg`, `cam04_seqB_val_f0138.jpg`, IoU $0.55 - 0.69$) while the motorcycle body is ignored.
  3. **Low Spatial Profile**:
     - In head-on and rear viewpoints, two-wheelers present an exceptionally narrow horizontal profile that falls below detection feature maps at 640 resolution.

---

## 4. Per-Camera Performance Breakdown

```
================================================================================
CAMERA-SPECIFIC PERFORMANCE BREAKDOWN (VALIDATION SET)
================================================================================
Camera      Type / Environment       GT  Pred   TP    FP   FN  Precision  Recall      F1
--------------------------------------------------------------------------------
CAM-01      Main Gate / Dense Flow  136   331   79   252   57     0.2387  0.5809  0.3383
CAM-02      Compound Overview        35    38   16    22   19     0.4211  0.4571  0.4384
CAM-03      Night / IR Loitering     20    58    1    57   19     0.0172  0.0500  0.0256
CAM-04      Highway Perimeter       124   340   72   268   52     0.2118  0.5806  0.3103
================================================================================
```

### Critical Camera Findings:
1. **CAM-03 Night Surveillance Blindspot**:
   - CAM-03 exhibits an alarming **F1 score of 0.0256**. Out of 20 real objects (primarily loiterers in the compound at night), only 1 is detected ($R = 5.0\%$). Simultaneously, it triggers 57 false alarms on infrared grain, ground lighting patterns, and perimeter walls.
   - **Root Cause**: Generic COCO pretraining has zero infrared/greyscale nighttime representation.
2. **CAM-01 & CAM-04 Traffic Cameras**:
   - Both cameras suffer massive FP bloat (252 and 268 FPs respectively). At `conf=0.35`, the detector is overly eager, generating spurious predictions on road textures, fences, and distant static vehicles.

---

## 5. Object Size Stratification

```
================================================================================
SIZE STRATIFICATION ON VALIDATION GROUND TRUTH
================================================================================
Size Bucket   Criteria (Area)         GT Objects   TP   FN   Recall (Miss Rate)
--------------------------------------------------------------------------------
Small         area < 0.02 (e.g. distant)      93   47   46   50.54% (49.46% miss)
Medium        0.02 <= area < 0.10            143   85   58   59.44% (40.56% miss)
Large         area >= 0.10 (close-up)         79   36   43   45.57% (54.43% miss)
================================================================================
```

- **Small Objects**: Approximately half of small targets (distant guards, two-wheelers) are completely missed.
- **Large Objects**: Interestingly, large objects have the lowest recall (45.57%) due to boundary truncation—when a large truck or car fills the foreground or passes close to the camera, the COCO anchor boxes fail on incomplete aspect ratios.

---

## 6. Actionable Fine-Tuning Strategy for Candidate Models

Based on these empirical findings, the training progression must address these exact failure modes:

1. **Domain Adaptation on Surveillance Views (Experiment B — Conservative Baseline)**:
   - Fine-tune YOLOv8n specifically on Dataset V2 (322 train images, 821 annotated instances).
   - Expected impact: Suppress non-relevant COCO background activations, align anchor priors with fixed camera angles, and teach the network the composite motorcycle/rider representation.
2. **Data Augmentation for Illumination & Contrast (Experiment C — Augmentation Enhanced)**:
   - Integrate photometric jitter (HSV-V / brightness scaling) and mild scale variations to address the CAM-03 night deficit and CAM-01 distance attenuation.
   - Constrain mosaic and perspective distortion to avoid corrupting fixed-camera geometry.
3. **Resolution Scaling (Experiment D — Higher Resolution `imgsz=800`)**:
   - Increase image resolution from 640 to 800 to recover the 46 missed small targets (small persons and distant motorcycles).
4. **Model Capacity (Experiment E — YOLOv8s)**:
   - Evaluate whether YOLOv8s provides the capacity required to separate the subtle boundary differences between trucks and cars and resolve nighttime noise.
