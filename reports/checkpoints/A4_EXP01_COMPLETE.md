# PRAHARI-AI — Checkpoint: A4_EXP01_COMPLETE

Experiment: A4_EXP01
Status: COMPLETE

Base model: weights/yolov8n.pt
Dataset: dataset_v2/data.yaml

Epochs requested: 50
Epochs completed: 32
Best epoch: 17

Best validation metrics (Ultralytics val @ IoU 0.50):
Precision: 0.3455
Recall: 0.0629
F1: 0.1065
mAP50: 0.0542
mAP50-95: 0.0147

Validation evaluation metrics (Standardized conf=0.35, imgsz=640 bipartite matching):
Precision: 0.0320
Recall: 0.0127
F1: 0.0182
TP: 4 | FP: 121 | FN: 311

Best model: D:\PRAHARI-AI\runs\detect\prahari_a4_exp01\weights\best.pt
Last model: D:\PRAHARI-AI\runs\detect\prahari_a4_exp01\weights\last.pt

Best model SHA256: bf7be2a8fa3e7aa5a96d6b022b15038d6ee3c42945c4bc61afa9383ae7478754

Training duration: 221.46s

Git commit: cd4b889ddb06604bda3b56fa53efebccb18eb538

Production model modified: NO

Next phase:
Validation evaluation and comparison against production baseline
