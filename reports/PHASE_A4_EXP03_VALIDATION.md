# PRAHARI-AI — Phase A4: Experiment 03 Validation Comparison

**Date**: 2026-09-12 20:55:04  
**Candidate**: `D:\PRAHARI-AI\runs\detect\prahari_a4_exp03\weights\best.pt` (SHA256: `34e1e73bdb7995023300d78460d8e7af34b60a3288f1b82c52a41d517385d87f`)  
**Baseline**: `weights/yolov8n.pt` (Production Frozen Baseline)  
**Configuration**: `lr0=0.001`, `freeze=5` (Backbone layers 0..4 frozen), `batch=16`, `epochs=50`, `seed=42`  
**Evaluation Protocol**: Validation split (169 images), `conf=0.35`, `imgsz=640`, bipartite matching at IoU >= 0.50  
**Status**: **EXP03 = REJECTED**  

---

## 1. Metric Comparison Table (Production vs EXP01 vs EXP02 vs EXP03)

| Metric | Production Baseline | Experiment 01 | Experiment 02 | Experiment 03 | Delta vs Production | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Precision** | 0.2190 | 0.0320 | 0.1598 | 0.1117 | -0.1073 | Degraded |
| **Recall** | 0.5333 | 0.0127 | 0.0857 | 0.0635 | -0.4698 | Degraded |
| **F1-Score** | **0.3105** | **0.0182** | **0.1116** | **0.0810** | **-0.2295** | **Degraded** |
| **mAP50** (Ultralytics) | N/A | 0.0542 | 0.0999 | 0.0650 | N/A | Domain Evaluation |
| **mAP50-95** (Ultralytics) | N/A | 0.0147 | 0.0227 | 0.0286 | N/A | Domain Evaluation |
| **Person F1** | 0.2901 | 0.0000 | 0.0000 | 0.0000 | -0.2901 | Degraded |
| **Car F1** | 0.3623 | 0.0510 | 0.2727 | 0.2020 | -0.1603 | Degraded |
| **Motorcycle F1** | 0.0941 | 0.0000 | 0.0000 | 0.0000 | -0.0941 | Degraded |
| **Truck F1** | 0.2439 | 0.0000 | 0.0000 | 0.0000 | -0.2439 | Degraded |
| **Hard-Negative FP/image** | 0.0000 | 0.0357 | 0.0000 | 0.0000 | +0.0000 | 0 FP across 28 images |

---

## 2. Counts Summary

- **Production Baseline**: TP=168, FP=599, FN=147
- **Experiment 01**: TP=4, FP=121, FN=311
- **Experiment 02**: TP=27, FP=142, FN=288
- **Experiment 03**: TP=20, FP=159, FN=295

---

## 3. Per-Camera Performance

| Camera | Baseline F1 | EXP01 F1 | EXP02 F1 | EXP03 F1 | Delta vs Production | EXP03 TP | EXP03 FP | EXP03 FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CAM-01** (Gate/Road) | 0.3383 | 0.0000 | 0.0000 | 0.0000 | -0.3383 | 0 | 81 | 136 |
| **CAM-02** (Compound) | 0.4384 | 0.0000 | 0.4762 | 0.4590 | +0.0206 | 14 | 12 | 21 |
| **CAM-03** (Night IR) | 0.0256 | 0.0000 | 0.0000 | 0.0000 | -0.0256 | 0 | 18 | 20 |
| **CAM-04** (Perimeter) | 0.3103 | 0.0615 | 0.1655 | 0.0674 | -0.2429 | 6 | 48 | 118 |

---

## 4. Analytical Conclusion & Decision

**Result**: **EXP03 = REJECTED**

Experiment 03 tested controlled partial-freeze fine-tuning (`freeze=5`, `lr0=0.001`).
Candidate model weights remain strictly isolated in `D:\PRAHARI-AI\runs\detect\prahari_a4_exp03\weights\best.pt`.
Production weights `weights/yolov8n.pt` are completely untouched.
