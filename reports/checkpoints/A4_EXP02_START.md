# PRAHARI-AI — Checkpoint: A4_EXP02_START

Experiment: A4_EXP02
Status: STARTED

Base model: weights/yolov8n.pt
Production model SHA256: F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36

Dataset: dataset_v2/data.yaml
Train images: 322
Validation images: 169

Image size: 640
Batch: 16
Epochs: 50
Seed: 42
Patience: 20
Device: 0 (NVIDIA GeForce RTX 3050 6GB Laptop GPU)

Learning rate: lr0=0.001 (substantially lower than EXP01's 0.01)
Freeze configuration: freeze=10 (Freezes all 10 backbone layers: model.0 through model.9 [Conv, C2f, SPPF]; layers 10-22 neck/head trainable)
Optimizer: auto (with standard Ultralytics warmup mechanism)

Output directory: runs/detect/prahari_a4_exp02/

Git commit: cd4b889ddb06604bda3b56fa53efebccb18eb538
Git status: Clean working tree on production modules

Production modified: NO
Production model modified: NO
Training start timestamp: 2026-09-12T20:18:00+05:30
