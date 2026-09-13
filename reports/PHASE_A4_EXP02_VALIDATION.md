# PRAHARI-AI — Phase A4: Experiment 02 Validation Comparison

**Date**: 2026-09-12 20:23:44  
**Candidate**: `D:\PRAHARI-AI\runs\detect\prahari_a4_exp02\weights\best.pt` (SHA256: `21c33958c8c065c3d92fe6fc9e48e1884e4cdd53d459acd9e274e2345ddacff5`)  
**Baseline**: `weights/yolov8n.pt` (Production Frozen Baseline)  
**Configuration**: `lr0=0.001`, `freeze=10` (Backbone layers 0..9 frozen), `batch=16`, `epochs=50`, `seed=42`  
**Evaluation Protocol**: Validation split (169 images), `conf=0.35`, `imgsz=640`, bipartite matching at IoU >= 0.50  
**Status**: **EXP02 = REJECTED**  

---

## 1. Metric Comparison Table (Production vs EXP01 vs EXP02)

| Metric | Production Baseline | Experiment 01 | Experiment 02 | Delta vs Prod | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Precision** | 0.2190 | 0.0320 | 0.1598 | -0.0592 | Degraded |
| **Recall** | 0.5333 | 0.0127 | 0.0857 | -0.4476 | Degraded |
| **F1-Score** | **0.3105** | **0.0182** | **0.1116** | **-0.1989** | **Degraded** |
| **mAP50** (Ultralytics) | N/A | 0.0542 | 0.0999 | N/A | Domain Evaluation |
| **mAP50-95** (Ultralytics) | N/A | 0.0147 | 0.0227 | N/A | Domain Evaluation |
| **Person F1** | 0.2901 | 0.0000 | 0.0000 | -0.2901 | Degraded |
| **Car F1** | 0.3623 | 0.0510 | 0.2727 | -0.0896 | Degraded |
| **Motorcycle F1** | 0.0941 | 0.0000 | 0.0000 | -0.0941 | Degraded |
| **Truck F1** | 0.2439 | 0.0000 | 0.0000 | -0.2439 | Degraded |
| **Hard-Negative FP/image** | 0.0000 | 0.0357 | 0.0000 | +0.0000 | 0 FP across 28 images |

---

## 2. Counts Summary

- **Production Baseline**: TP=168, FP=599, FN=147
- **Experiment 01**: TP=4, FP=121, FN=311
- **Experiment 02**: TP=27, FP=142, FN=288

---

## 3. Per-Camera Performance

| Camera | Baseline F1 | EXP01 F1 | EXP02 F1 | Delta vs Prod | EXP02 TP | EXP02 FP | EXP02 FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CAM-01** (Gate/Road) | 0.3383 | 0.0000 | 0.0000 | -0.3383 | 0 | 76 | 136 |
| **CAM-02** (Compound) | 0.4384 | 0.0000 | 0.4762 | +0.0378 | 15 | 13 | 20 |
| **CAM-03** (Night IR) | 0.0256 | 0.0000 | 0.0000 | -0.0256 | 0 | 44 | 20 |
| **CAM-04** (Perimeter) | 0.3103 | 0.0615 | 0.1655 | -0.1448 | 12 | 9 | 112 |

---

## 4. Analytical Conclusion & Decision

**Result**: **EXP02 = REJECTED**

Experiment 02 tested controlled transfer learning with backbone freezing (`freeze=10`) and reduced learning rate (`lr0=0.001`).
The candidate model weights remain strictly isolated in `D:\PRAHARI-AI\runs\detect\prahari_a4_exp02\weights\best.pt`.
Production weights `weights/yolov8n.pt` are completely untouched.
