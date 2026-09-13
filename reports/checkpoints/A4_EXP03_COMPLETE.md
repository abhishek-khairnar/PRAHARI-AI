# PRAHARI-AI — Checkpoint: A4_EXP03_COMPLETE

Experiment: A4_EXP03
Status: COMPLETE

Training:
Epochs completed: 41
Best epoch: 21
Training duration: 362.47s

Learning rate: lr0=0.001
Freeze configuration: freeze=5 (Backbone layers 0..4 frozen)
Image size: 640
Batch: 16

Validation:

Production Precision: 0.2190
EXP03 Precision: 0.1117

Production Recall: 0.5333
EXP03 Recall: 0.0635

Production F1: 0.3105
EXP03 F1: 0.0810

Person F1: 0.0000
Car F1: 0.2020
Motorcycle F1: 0.0000
Truck F1: 0.0000

Hard-negative FP: 0 (0.0 FP/image)

CAM-01 F1: 0.0000
CAM-02 F1: 0.4590
CAM-03 F1: 0.0000
CAM-04 F1: 0.0674

Candidate path: D:\PRAHARI-AI\runs\detect\prahari_a4_exp03\weights\best.pt
Candidate SHA256: 34e1e73bdb7995023300d78460d8e7af34b60a3288f1b82c52a41d517385d87f

Decision: REJECTED

Production modified: NO

Next recommended action:
Evaluate whether small-object resolution (imgsz=800) or architecture capacity (YOLOv8s) is the limiting factor.
