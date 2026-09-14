"""
PRAHARI-AI — Phase A2 Training Script
Executes reproducible fine-tuning of candidate YOLOv8s on domain-specific surveillance data.
Guarantees:
- Production weights weights/yolov8n.pt remain strictly untouched.
- Candidate weights stored in weights/candidates/yolov8s_prahari_v1.pt.
- Full provenance metadata recorded (hash, seed, params, val metrics).
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

import json
import shutil
import hashlib
from datetime import datetime
from ultralytics import YOLO

from training.config import (
    DATASET_YAML,
    CANDIDATE_WEIGHTS_DIR,
    BASE_MODEL_PATH,
    EXPERIMENT_NAME,
    RANDOM_SEED,
    IMAGE_SIZE,
    BATCH_SIZE,
    EPOCHS,
    LEARNING_RATE_INIT,
    OPTIMIZER,
    WEIGHT_DECAY,
    PATIENCE,
    WORKERS,
    DEVICE,
    CLASS_NAMES,
    AUGMENTATION_CONFIG
)

def compute_sha256(filepath: str) -> str:
    """Computes SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def run_training():
    print("=" * 70)
    print(" PRAHARI-AI PHASE A2 — CANDIDATE MODEL TRAINING PIPELINE")
    print("=" * 70)

    # Safety check: ensure yolov8n.pt exists and record pre-training hash
    prod_model_path = os.path.join("weights", "yolov8n.pt")
    if not os.path.exists(prod_model_path):
        raise FileNotFoundError("Production model weights/yolov8n.pt is missing!")
    prod_hash_pre = compute_sha256(prod_model_path)
    print(f"[*] Production YOLOv8n Hash (Pre-Train): {prod_hash_pre}")

    if not os.path.exists(BASE_MODEL_PATH):
        raise FileNotFoundError(f"Base candidate model not found at {BASE_MODEL_PATH}")
    base_hash = compute_sha256(BASE_MODEL_PATH)
    print(f"[*] Base Candidate Model: {BASE_MODEL_PATH} (SHA256: {base_hash[:16]}...)")

    print(f"[*] Initializing training with Seed={RANDOM_SEED}, Imgsz={IMAGE_SIZE}, Batch={BATCH_SIZE}, Epochs={EPOCHS}...")
    model = YOLO(BASE_MODEL_PATH)

    # Execute training
    runs_dir = os.path.join("training", "runs")
    os.makedirs(runs_dir, exist_ok=True)

    results = model.train(
        data=DATASET_YAML,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        lr0=LEARNING_RATE_INIT,
        optimizer=OPTIMIZER,
        weight_decay=WEIGHT_DECAY,
        patience=PATIENCE,
        seed=RANDOM_SEED,
        workers=WORKERS,
        device=DEVICE,
        project=runs_dir,
        name=EXPERIMENT_NAME,
        exist_ok=True,
        verbose=True,
        **AUGMENTATION_CONFIG
    )

    # Determine weight directory
    save_dir = getattr(results, "save_dir", None)
    candidates = []
    if save_dir:
        candidates.append(os.path.join(str(save_dir), "weights", "best.pt"))
        candidates.append(os.path.join(str(save_dir), "weights", "last.pt"))
    candidates.append(os.path.join(runs_dir, EXPERIMENT_NAME, "weights", "best.pt"))
    candidates.append(os.path.join("runs", "detect", runs_dir, EXPERIMENT_NAME, "weights", "best.pt"))
    candidates.append(os.path.join("runs", "detect", EXPERIMENT_NAME, "weights", "best.pt"))

    best_weights_path = None
    for cand_p in candidates:
        if os.path.exists(cand_p):
            best_weights_path = cand_p
            break

    if not best_weights_path:
        raise RuntimeError(f"Training failed to produce weight artifacts in {candidates}")

    # Store candidate artifact separately
    candidate_out_path = os.path.join(CANDIDATE_WEIGHTS_DIR, f"{EXPERIMENT_NAME}.pt")
    shutil.copyfile(best_weights_path, candidate_out_path)
    candidate_hash = compute_sha256(candidate_out_path)
    candidate_size = os.path.getsize(candidate_out_path)

    print(f"\n[+] Candidate artifact successfully saved -> {candidate_out_path}")
    print(f"    File Size: {candidate_size} bytes ({candidate_size / (1024*1024):.2f} MB)")
    print(f"    SHA256: {candidate_hash}")

    # Safety verification: ensure production model was untouched
    prod_hash_post = compute_sha256(prod_model_path)
    if prod_hash_pre != prod_hash_post:
        raise AssertionError("CRITICAL SAFETY VIOLATION: weights/yolov8n.pt was altered during training!")
    print(f"[+] Safety Verified: Production model weights/yolov8n.pt remained 100% untouched.")

    # Record full metadata
    metadata = {
        "experiment_name": EXPERIMENT_NAME,
        "training_date": datetime.now().isoformat(),
        "candidate_file": candidate_out_path,
        "candidate_sha256": candidate_hash,
        "candidate_size_bytes": candidate_size,
        "base_model": BASE_MODEL_PATH,
        "base_model_sha256": base_hash,
        "model_architecture": "YOLOv8s",
        "dataset_yaml": DATASET_YAML,
        "dataset_version": "v1.0-prahari-surveillance",
        "classes": CLASS_NAMES,
        "hyperparameters": {
            "image_size": IMAGE_SIZE,
            "batch_size": BATCH_SIZE,
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE_INIT,
            "optimizer": OPTIMIZER,
            "weight_decay": WEIGHT_DECAY,
            "random_seed": RANDOM_SEED
        },
        "augmentation": AUGMENTATION_CONFIG,
        "validation_summary": {
            "fitness": float(results.fitness) if hasattr(results, "fitness") and results.fitness is not None else None
        }
    }

    meta_path = os.path.join(CANDIDATE_WEIGHTS_DIR, f"{EXPERIMENT_NAME}_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"[+] Provenance metadata saved -> {meta_path}")

    return metadata

if __name__ == "__main__":
    run_training()
