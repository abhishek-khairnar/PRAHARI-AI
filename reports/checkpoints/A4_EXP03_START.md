# PRAHARI-AI — Checkpoint: A4_EXP03_START

Experiment: A4_EXP03
Status: STARTED

Base model: weights/yolov8n.pt
Production SHA256: F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36

Dataset: dataset_v2/data.yaml
Train images: 322
Validation images: 169

Architecture: YOLOv8n
Image size: 640
Batch: 16
Epochs: 50
Seed: 42
Patience: 20
Learning rate: lr0=0.001
Freeze: freeze=5 (Backbone layers 0..4 frozen [Stem, Conv, C2f]; layers 5..9 [deep backbone] and 10..22 [neck & head] trainable)

Device: 0
GPU: NVIDIA GeForce RTX 3050 6GB Laptop GPU

Output: runs/detect/prahari_a4_exp03/

Git commit: cd4b889ddb06604bda3b56fa53efebccb18eb538
Git status: Clean working tree on production modules

Production modified: NO
Production model modified: NO
Training start timestamp: 2026-09-12T20:48:30+05:30
