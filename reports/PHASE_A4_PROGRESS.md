# PRAHARI-AI — Phase A4 Execution Progress Tracker

Current Phase: Production Model Reality Check (Completed)
Current Status: Production Model Evaluated Across 4 Clean Demo Videos (DECISION: GO)
Last Completed Phase: Production Model 4-Camera Reality Check
Last Successful Command: python scratch/run_production_4cam_reality_check.py
Last Successful Artifact: reports/PRODUCTION_4CAM_EVALUATION.md
Next Action: DO NOT TRAIN EXP03/EXP04. Focus on ANPR regex post-processing rules and live demonstration reliability.
Production Modified: NO
Production Model Modified: NO

---

## Phase A4 Progress Checklist

- [x] **Phase 1: Repository audit**
  - Git working tree inspected, external infrastructure locks honored.
  - Production model `weights/yolov8n.pt` verified intact (SHA256: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`).
- [x] **Phase 2: Dataset validation**
  - 621 images (322 train, 169 val, 130 test), 1,347 objects, 113 hard negatives.
  - Validation report: `dataset_v2/PRETRAINING_VALIDATION_REPORT.md` (Status: PASS — 100% READY FOR TRAINING).
- [x] **Phase 3: Production baseline benchmark**
  - Validation Split: F1=0.3105 (Precision=0.2190, Recall=0.5333, TP=168, FP=599, FN=147).
  - Test Split: F1=0.2105 (Precision=0.1472, Recall=0.3697, TP=78, FP=452, FN=133).
  - Artifacts: `reports/production_baseline_benchmark_val.json`, `reports/production_baseline_benchmark.json`.
- [x] **Phase 4: Baseline error analysis**
  - Completed: `reports/PHASE_A4_ERROR_ANALYSIS.md`.
  - Identified major failure modes: CAM-03 night blindspot (F1=0.0256, R=5.0%), Motorcycle severe miss rate (R=12.90%), Truck-to-car confusion (33.3% of sample confusions), and 599 background/overlapping false positives.
- [x] **Phase 5: Experiment 01 Training & Validation**
  - Configuration: `lr0=0.01`, `freeze=0`, `batch=16`, `epochs=50`, `seed=42`.
  - Duration: 221.46s on RTX 3050. Candidate: `runs/detect/prahari_a4_exp01/weights/best.pt` (SHA256: `bf7be2a8fa3e7aa5a96d6b022b15038d6ee3c42945c4bc61afa9383ae7478754`).
  - Validation: Overall F1=0.0182 (TP=4, FP=121, FN=311).
  - Result: **EXP01 = REJECTED** (Unconstrained fine-tuning on 322 images caused catastrophic forgetting).
  - Artifacts: `reports/checkpoints/A4_EXP01_COMPLETE.md`, `reports/PHASE_A4_EXP01_VALIDATION.md`.
- [x] **Phase 5: Experiment 02 Training & Validation**
  - Configuration: `lr0=0.001`, `freeze=10` (Backbone layers 0..9 frozen), `batch=16`, `epochs=50`, `seed=42`.
  - Duration: 306.25s on RTX 3050. Candidate: `runs/detect/prahari_a4_exp02/weights/best.pt` (SHA256: `21c33958c8c065c3d92fe6fc9e48e1884e4cdd53d459acd9e274e2345ddacff5`).
  - Validation: Overall F1=0.1116 (TP=27, FP=142, FN=288). CAM-02 F1: 0.4762 (+0.0378 over baseline); 0 hard-neg FP.
  - Result: **EXP02 = REJECTED** (Overall F1 0.1116 < baseline 0.3105; person, motorcycle, truck missed at conf=0.35).
  - Artifacts: `reports/checkpoints/A4_EXP02_COMPLETE.md`, `reports/PHASE_A4_EXP02_VALIDATION.md`.
- [x] **Phase 5: Experiment 03 Training & Validation**
  - Configuration: `lr0=0.001`, `freeze=5` (Backbone layers 0..4 frozen, 5..9 trainable), `batch=16`, `epochs=50`, `seed=42`.
  - Duration: 362.47s on RTX 3050. Candidate: `runs/detect/prahari_a4_exp03/weights/best.pt` (SHA256: `34e1e73bdb7995023300d78460d8e7af34b60a3288f1b82c52a41d517385d87f`).
  - Validation: Overall F1=0.0810 (TP=20, FP=159, FN=295).
  - Finding: Unfreezing layers 5..9 degraded performance compared to freeze=10 (F1 dropped from 0.1116 to 0.0810).
  - Result: **EXP03 = REJECTED** (Overall F1 0.0810 < baseline 0.3105).
  - Artifacts: `reports/checkpoints/A4_EXP03_COMPLETE.md`, `reports/PHASE_A4_EXP03_VALIDATION.md`.
- [x] **PRODUCTION MODEL REALITY CHECK (4 Clean Demo Videos)**
  - Audited and verified `weights/yolov8n.pt` across all 4 production demo videos (1,487 frames total).
  - Performance: 71.2 to 123.2 FPS per stream on RTX 3050 GPU (avg 95.1 FPS).
  - Detections: 9,047 total detections; 100% target coverage on CAM-01 & CAM-04, 98% on CAM-02, 63% on CAM-03.
  - Tracking & Intrusion: 112 unique tracks, 65 virtual fence crossings, 3 loitering alerts, 0 crashes.
  - Benchmark Discrepancy Resolved: Static Dataset V2 benchmark was pessimistic due to unannotated background objects.
  - Decision: **GO** (Do NOT retrain models; existing model is sufficient for the demo).
  - Artifacts: `reports/PRODUCTION_4CAM_EVALUATION.md`, `reports/checkpoints/PRODUCTION_4CAM_EVAL_COMPLETE.md`.
- [ ] **ANPR Post-Processing Optimization (Targeted regex / character substitution fix)**
- [ ] **Command Center Live Demo Dry Run & Deployment**

