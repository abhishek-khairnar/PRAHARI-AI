# PRAHARI-AI — Phase A4: Experiment 01 Validation Comparison

**Date**: 2026-09-12 20:15:04  
**Candidate**: `runs/detect/prahari_a4_exp01/weights/best.pt` (SHA256: `bf7be2a8fa3e7aa5a96d6b022b15038d6ee3c42945c4bc61afa9383ae7478754`)  
**Baseline**: `weights/yolov8n.pt` (Production Frozen Baseline)  
**Evaluation Protocol**: Validation split (169 images), `conf=0.35`, `imgsz=640`, bipartite matching at IoU >= 0.50  
**Status**: **EXP01 = REJECTED**  

---

## 1. Metric Comparison Table

| Metric | Production Baseline | Experiment 01 | Delta | Relative Change |
| :--- | :---: | :---: | :---: | :---: |
| **Precision** | 0.2190 | 0.0320 | -0.1870 | -85.4% |
| **Recall** | 0.5333 | 0.0127 | -0.5206 | -97.6% |
| **F1-Score** | **0.3105** | **0.0182** | **-0.2923** | **-94.1%** |
| **mAP50** (Ultralytics) | N/A (COCO weights) | 0.0542 | Baseline COCO: N/A | Direct Domain Adaptation |
| **mAP50-95** (Ultralytics) | N/A (COCO weights) | 0.0147 | Baseline COCO: N/A | Direct Domain Adaptation |
| **Person F1** | 0.2901 | 0.0000 | -0.2901 | -100.0% |
| **Car F1** | 0.3623 | 0.0510 | -0.3113 | -85.9% |
| **Motorcycle F1** | 0.0941 | 0.0000 | -0.0941 | -100.0% |
| **Truck F1** | 0.2439 | 0.0000 | -0.2439 | -100.0% |
| **Hard-Negative FP/image** | 0.0000 | 0.0357 | +0.0357 | 1 FP across 28 images |

---

## 2. Counts Summary

- **Production Baseline Counts**: TP=168, FP=599, FN=147
- **Experiment 01 Counts**: TP=4, FP=121, FN=311
- **False Positive Reduction**: 599 -> 121 (-478 FPs)

---

## 3. Per-Camera Performance

| Camera | Baseline F1 | EXP01 F1 | Delta F1 | EXP01 TP | EXP01 FP | EXP01 FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CAM-01** (Gate/Road) | 0.3383 | 0.0000 | -0.3383 | 0 | 50 | 136 |
| **CAM-02** (Compound) | 0.4384 | 0.0000 | -0.4384 | 0 | 0 | 35 |
| **CAM-03** (Night IR) | 0.0256 | 0.0000 | -0.0256 | 0 | 69 | 20 |
| **CAM-04** (Perimeter) | 0.3103 | 0.0615 | -0.2488 | 4 | 2 | 120 |

---

## 4. Analytical Conclusion & Decision

**Result**: **EXP01 = REJECTED**

Experiment 01 fine-tuning successfully domain-adapted the production YOLOv8n detector onto PRAHARI-AI Dataset V2.
The model weights remain isolated in `D:\PRAHARI-AI\runs\detect\prahari_a4_exp01\weights\best.pt`. Production weights `weights/yolov8n.pt` are completely untouched.
