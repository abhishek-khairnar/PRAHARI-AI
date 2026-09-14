"""
PRAHARI-AI — Phase 5: Experiment 03 (Controlled Partial-Freeze Fine-Tuning)
Safe, isolated execution script.

Configuration:
- Base model: weights/yolov8n.pt (Frozen production model - read only)
- Dataset: dataset_v2/data.yaml (322 train, 169 val)
- Image size: 640
- Batch: 16
- Epochs: 50
- Learning rate: lr0=0.001
- Freeze: 5 (Freezes early backbone layers 0..4; layers 5..9 [deep backbone] and 10..22 [neck & head] trainable)
- Seed: 42
- Patience: 20
- Device: 0 (RTX 3050 Laptop GPU)
- Output: runs/detect/prahari_a4_exp03/
"""

import os
import sys
import time
import json
import hashlib
import cv2
import pandas as pd
import numpy as np
from datetime import datetime
from ultralytics import YOLO

PROD_MODEL_PATH = "weights/yolov8n.pt"
DATA_YAML = os.path.abspath("dataset_v2/data.yaml")
VAL_IMG_DIR = os.path.abspath("dataset_v2/images/val")
VAL_LBL_DIR = os.path.abspath("dataset_v2/labels/val")
PROJECT_DIR = os.path.abspath("runs/detect")
EXP_NAME = "prahari_a4_exp03"
OUTPUT_DIR = os.path.join(PROJECT_DIR, EXP_NAME)

CLASS_NAMES = {0: "person", 1: "car", 2: "motorcycle", 3: "truck"}

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = inter_w * inter_h
    areaA = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    areaB = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    union_area = areaA + areaB - inter_area
    return inter_area / float(union_area) if union_area > 0 else 0.0

def match_boxes_class_aware(pred_boxes, gt_boxes, iou_threshold=0.50):
    pairs = []
    for p_idx, (p_cls, p_box, p_conf) in enumerate(pred_boxes):
        for g_idx, (g_cls, g_box, _) in enumerate(gt_boxes):
            if p_cls == g_cls:
                iou = compute_iou(p_box, g_box)
                if iou >= iou_threshold:
                    pairs.append((iou, p_idx, g_idx, p_cls))

    pairs.sort(key=lambda x: x[0], reverse=True)
    matched_preds = set()
    matched_gts = set()
    matches = []

    for iou, p_idx, g_idx, cls_id in pairs:
        if p_idx not in matched_preds and g_idx not in matched_gts:
            matched_preds.add(p_idx)
            matched_gts.add(g_idx)
            matches.append((p_idx, g_idx, cls_id, iou))

    tp_indices = [p_idx for _, p_idx, _, _ in matches]
    fp_indices = [i for i in range(len(pred_boxes)) if i not in matched_preds]
    fn_indices = [i for i in range(len(gt_boxes)) if i not in matched_gts]

    return matches, fp_indices, fn_indices

def evaluate_candidate_on_val(model_path, conf=0.35, imgsz=640):
    """Evaluates fine-tuned model (0:person, 1:car, 2:motorcycle, 3:truck) on val split."""
    print(f"[*] Evaluating EXP03 candidate model on validation split: {model_path} (conf={conf}, imgsz={imgsz})")
    model = YOLO(model_path)

    class_metrics = {c: {"tp": 0, "fp": 0, "fn": 0} for c in range(4)}
    cameras = ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]
    cam_metrics = {c: {"tp": 0, "fp": 0, "fn": 0} for c in cameras}
    size_metrics = {"small": {"tp": 0, "fp": 0, "fn": 0}, "medium": {"tp": 0, "fp": 0, "fn": 0}, "large": {"tp": 0, "fp": 0, "fn": 0}}
    
    hn_images_count = 0
    hn_false_positives = 0
    hn_fp_details = []

    val_files = sorted(os.listdir(VAL_IMG_DIR))
    for fname in val_files:
        if not fname.endswith(".jpg"):
            continue
        base = os.path.splitext(fname)[0]
        img_path = os.path.join(VAL_IMG_DIR, fname)
        lbl_path = os.path.join(VAL_LBL_DIR, f"{base}.txt")

        img = cv2.imread(img_path)
        h_img, w_img = img.shape[:2]
        is_hard_neg = "hardneg" in fname
        if is_hard_neg:
            hn_images_count += 1

        cam_id = "UNKNOWN"
        for c in cameras:
            if c.lower().replace("-", "") in fname.lower():
                cam_id = c
                break

        gt_boxes = []
        if os.path.exists(lbl_path):
            with open(lbl_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cid = int(parts[0])
                        if cid < 4:
                            xc, yc, bw, bh = [float(v) for v in parts[1:]]
                            x1 = int((xc - bw / 2.0) * w_img)
                            y1 = int((yc - bh / 2.0) * h_img)
                            x2 = int((xc + bw / 2.0) * w_img)
                            y2 = int((yc + bh / 2.0) * h_img)
                            gt_boxes.append((cid, [x1, y1, x2, y2], bw * bh))

        # Run inference: classes 0..3
        results = model(source=img, conf=conf, imgsz=imgsz, classes=[0, 1, 2, 3], verbose=False)[0]

        pred_boxes = []
        for b in results.boxes:
            c_id = int(b.cls[0].item())
            c_conf = float(b.conf[0].item())
            if c_id < 4:
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                pred_boxes.append((c_id, [x1, y1, x2, y2], c_conf))

        matches, fp_idx, fn_idx = match_boxes_class_aware(pred_boxes, gt_boxes, iou_threshold=0.50)

        for _, g_idx, cls_id, iou in matches:
            class_metrics[cls_id]["tp"] += 1
            if cam_id in cam_metrics:
                cam_metrics[cam_id]["tp"] += 1
            area = gt_boxes[g_idx][2]
            s_cat = "small" if area < 0.02 else ("medium" if area < 0.10 else "large")
            size_metrics[s_cat]["tp"] += 1

        for idx in fp_idx:
            p_cls, p_box, p_conf = pred_boxes[idx]
            class_metrics[p_cls]["fp"] += 1
            if cam_id in cam_metrics:
                cam_metrics[cam_id]["fp"] += 1
            if is_hard_neg:
                hn_false_positives += 1
                hn_fp_details.append({"file": fname, "class": CLASS_NAMES[p_cls], "conf": p_conf, "box": p_box})

        for idx in fn_idx:
            g_cls, g_box, area = gt_boxes[idx]
            class_metrics[g_cls]["fn"] += 1
            if cam_id in cam_metrics:
                cam_metrics[cam_id]["fn"] += 1
            s_cat = "small" if area < 0.02 else ("medium" if area < 0.10 else "large")
            size_metrics[s_cat]["fn"] += 1

    def calc_prf(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return round(p, 4), round(r, 4), round(f1, 4)

    total_tp = sum(c["tp"] for c in class_metrics.values())
    total_fp = sum(c["fp"] for c in class_metrics.values())
    total_fn = sum(c["fn"] for c in class_metrics.values())
    overall_p, overall_r, overall_f1 = calc_prf(total_tp, total_fp, total_fn)

    per_class = {}
    for cid in range(4):
        cname = CLASS_NAMES[cid]
        m = class_metrics[cid]
        p, r, f1 = calc_prf(m["tp"], m["fp"], m["fn"])
        per_class[cname] = {"precision": p, "recall": r, "f1": f1, "tp": m["tp"], "fp": m["fp"], "fn": m["fn"]}

    per_camera = {}
    for cam in cameras:
        m = cam_metrics[cam]
        p, r, f1 = calc_prf(m["tp"], m["fp"], m["fn"])
        per_camera[cam] = {"precision": p, "recall": r, "f1": f1, "tp": m["tp"], "fp": m["fp"], "fn": m["fn"]}

    per_size = {}
    for s_cat in ["small", "medium", "large"]:
        m = size_metrics[s_cat]
        p, r, f1 = calc_prf(m["tp"], m["fp"], m["fn"])
        per_size[s_cat] = {"precision": p, "recall": r, "f1": f1, "tp": m["tp"], "fn": m["fn"]}

    return {
        "overall": {"precision": overall_p, "recall": overall_r, "f1": overall_f1, "tp": total_tp, "fp": total_fp, "fn": total_fn},
        "per_class": per_class,
        "per_camera": per_camera,
        "per_size": per_size,
        "hard_negatives": {
            "audited_images": hn_images_count,
            "false_positives": hn_false_positives,
            "fp_per_image": round(hn_false_positives / hn_images_count, 4) if hn_images_count > 0 else 0.0,
            "details": hn_fp_details
        }
    }

def main():
    print("=" * 80)
    print("PRAHARI-AI — PHASE 5: EXPERIMENT 03 (PARTIAL-FREEZE FINE-TUNING freeze=5)")
    print("=" * 80)

    # 1. Pre-flight checks
    if not os.path.exists(PROD_MODEL_PATH):
        print(f"[!] ERROR: Production model {PROD_MODEL_PATH} not found!")
        sys.exit(1)

    pre_sha = compute_sha256(PROD_MODEL_PATH)
    print(f"[*] Pre-training Production Hash: {pre_sha}")
    EXPECTED_HASH = "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"
    if pre_sha.lower() != EXPECTED_HASH.lower():
        print(f"[!] CRITICAL ERROR: Production hash mismatch! Expected {EXPECTED_HASH}, got {pre_sha}")
        sys.exit(1)

    if not os.path.exists(DATA_YAML):
        print(f"[!] ERROR: Dataset config {DATA_YAML} not found!")
        sys.exit(1)

    # 2. Train model with freeze=5 and lr0=0.001
    print(f"[*] Starting Partial-Freeze Training: epochs=50, imgsz=640, batch=16, lr0=0.001, freeze=5, seed=42, patience=20...")
    t0 = time.time()
    try:
        model = YOLO(PROD_MODEL_PATH)
        results = model.train(
            data=DATA_YAML,
            epochs=50,
            imgsz=640,
            batch=16,
            lr0=0.001,
            freeze=5,
            seed=42,
            patience=20,
            device=0,
            workers=2,
            project=PROJECT_DIR,
            name=EXP_NAME,
            exist_ok=True,
            verbose=True
        )
    except Exception as e:
        print(f"[!] TRAINING EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        os.makedirs("reports/checkpoints", exist_ok=True)
        with open("reports/checkpoints/A4_EXP03_FAILED.md", "w") as f:
            f.write(f"# PRAHARI-AI — Checkpoint: A4_EXP03_FAILED\n\nError: {e}\nTraceback:\n{traceback.format_exc()}\n")
        sys.exit(1)

    duration = round(time.time() - t0, 2)
    print(f"[+] Training finished in {duration} seconds.")

    # 3. Post-training safety check on production weights
    post_sha = compute_sha256(PROD_MODEL_PATH)
    print(f"[*] Post-training Production Hash: {post_sha}")
    if pre_sha != post_sha:
        print("[!] CRITICAL SAFETY ERROR: Production model was modified during training!")
        sys.exit(1)
    print("[+] Production model safety check: 100% UNTOUCHED.")

    # 4. Verify output artifacts
    save_dir = getattr(results, "save_dir", None)
    if save_dir and os.path.exists(os.path.join(str(save_dir), "weights", "best.pt")):
        actual_output_dir = str(save_dir)
    else:
        actual_output_dir = OUTPUT_DIR

    best_pt = os.path.join(actual_output_dir, "weights", "best.pt")
    last_pt = os.path.join(actual_output_dir, "weights", "last.pt")
    results_csv = os.path.join(actual_output_dir, "results.csv")
    args_yaml = os.path.join(actual_output_dir, "args.yaml")

    if not os.path.exists(best_pt):
        print(f"[!] ERROR: best.pt not found at {best_pt}")
        sys.exit(1)

    best_sha = compute_sha256(best_pt)
    print(f"[+] Candidate best.pt created: {best_pt}")
    print(f"[+] Candidate SHA256: {best_sha}")

    # Parse results.csv
    df_results = pd.read_csv(results_csv)
    df_results.columns = df_results.columns.str.strip()
    epochs_completed = len(df_results)
    
    map50_col = [c for c in df_results.columns if "mAP50" in c and "95" not in c]
    map50_95_col = [c for c in df_results.columns if "mAP50-95" in c]
    p_col = [c for c in df_results.columns if c.startswith("metrics/precision")]
    r_col = [c for c in df_results.columns if c.startswith("metrics/recall")]

    best_epoch_idx = df_results[map50_col[0]].idxmax() if map50_col else epochs_completed - 1
    best_epoch = int(df_results.iloc[best_epoch_idx]["epoch"]) if "epoch" in df_results.columns else int(best_epoch_idx + 1)
    
    ultralytics_p = float(df_results.iloc[best_epoch_idx][p_col[0]]) if p_col else 0.0
    ultralytics_r = float(df_results.iloc[best_epoch_idx][r_col[0]]) if r_col else 0.0
    ultralytics_map50 = float(df_results.iloc[best_epoch_idx][map50_col[0]]) if map50_col else 0.0
    ultralytics_map50_95 = float(df_results.iloc[best_epoch_idx][map50_95_col[0]]) if map50_95_col else 0.0

    print(f"[+] Epochs completed: {epochs_completed} | Best epoch: {best_epoch}")
    print(f"[+] Ultralytics best epoch metrics: P={ultralytics_p:.4f}, R={ultralytics_r:.4f}, mAP50={ultralytics_map50:.4f}, mAP50-95={ultralytics_map50_95:.4f}")

    # 5. Write training completion checkpoint
    os.makedirs("reports/checkpoints", exist_ok=True)
    training_complete_md = f"""# PRAHARI-AI — Checkpoint: A4_EXP03_TRAINING_COMPLETE

Experiment: A4_EXP03
Status: TRAINING_COMPLETE

Epochs requested: 50
Epochs completed: {epochs_completed}
Best epoch: {best_epoch}

Learning rate: lr0=0.001
Freeze: freeze=5 (Backbone layers 0..4 frozen)
Image size: 640
Batch: 16

Training duration: {duration}s

Best model: {best_pt}
Last model: {last_pt}

Best model SHA256: {best_sha}

Production modified: NO

Next step:
Validation evaluation
"""
    with open("reports/checkpoints/A4_EXP03_TRAINING_COMPLETE.md", "w", encoding="utf-8") as f:
        f.write(training_complete_md)
    print("[+] Checkpoint written to reports/checkpoints/A4_EXP03_TRAINING_COMPLETE.md")

    # 6. Run validation evaluation matching standardized PRAHARI protocol (conf=0.35, imgsz=640)
    val_eval = evaluate_candidate_on_val(best_pt, conf=0.35, imgsz=640)
    print("\n" + "=" * 70)
    print("EXPERIMENT 03 VALIDATION EVALUATION (conf=0.35, imgsz=640):")
    ov = val_eval["overall"]
    print(f"Overall: P={ov['precision']:.4f}, R={ov['recall']:.4f}, F1={ov['f1']:.4f} (TP={ov['tp']}, FP={ov['fp']}, FN={ov['fn']})")
    for cname, m in val_eval["per_class"].items():
        print(f"  {cname:12s}: P={m['precision']:.4f}, R={m['recall']:.4f}, F1={m['f1']:.4f} (TP={m['tp']}, FP={m['fp']}, FN={m['fn']})")
    for cam, m in val_eval["per_camera"].items():
        print(f"  {cam:10s}: P={m['precision']:.4f}, R={m['recall']:.4f}, F1={m['f1']:.4f} (TP={m['tp']}, FP={m['fp']}, FN={m['fn']})")
    hn = val_eval["hard_negatives"]
    print(f"Hard Negatives: {hn['false_positives']} FP across {hn['audited_images']} images ({hn['fp_per_image']} FP/img)")
    print("=" * 70)

    # 7. Load baseline, EXP01, and EXP02 validation numbers for comparison
    with open("reports/production_baseline_benchmark_val.json", "r", encoding="utf-8") as f:
        base_val = json.load(f)

    with open("reports/exp01_validation_result.json", "r", encoding="utf-8") as f:
        exp01_val = json.load(f)

    with open("reports/exp02_validation_result.json", "r", encoding="utf-8") as f:
        exp02_val = json.load(f)

    base_ov = base_val["overall"]
    base_pc = base_val["per_class"]
    base_hn = base_val["hard_negatives"]

    exp01_ov = exp01_val["validation_eval"]["overall"]
    exp01_pc = exp01_val["validation_eval"]["per_class"]

    exp02_ov = exp02_val["validation_eval"]["overall"]
    exp02_pc = exp02_val["validation_eval"]["per_class"]

    # 8. Decision logic per section 25
    diff_f1 = ov["f1"] - base_ov["f1"]
    if diff_f1 > 0.0 and val_eval["per_class"]["person"]["f1"] > 0.15:
        decision = "PROMISING"
    elif ov["f1"] > exp02_ov["f1"] and ov["f1"] >= 0.18:
        decision = "IMPROVED BUT NOT PRODUCTION-READY"
    elif ov["f1"] <= 0.15:
        decision = "REJECTED"
    else:
        decision = "REJECTED"

    # 9. Write validation comparison report
    diff_p = ov["precision"] - base_ov["precision"]
    diff_r = ov["recall"] - base_ov["recall"]

    person_diff = val_eval["per_class"]["person"]["f1"] - base_pc["person"]["f1"]
    car_diff = val_eval["per_class"]["car"]["f1"] - base_pc["car"]["f1"]
    moto_diff = val_eval["per_class"]["motorcycle"]["f1"] - base_pc["motorcycle"]["f1"]
    truck_diff = val_eval["per_class"]["truck"]["f1"] - base_pc["truck"]["f1"]

    val_comparison_md = f"""# PRAHARI-AI — Phase A4: Experiment 03 Validation Comparison

**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Candidate**: `{best_pt}` (SHA256: `{best_sha}`)  
**Baseline**: `weights/yolov8n.pt` (Production Frozen Baseline)  
**Configuration**: `lr0=0.001`, `freeze=5` (Backbone layers 0..4 frozen), `batch=16`, `epochs=50`, `seed=42`  
**Evaluation Protocol**: Validation split (169 images), `conf=0.35`, `imgsz=640`, bipartite matching at IoU >= 0.50  
**Status**: **EXP03 = {decision}**  

---

## 1. Metric Comparison Table (Production vs EXP01 vs EXP02 vs EXP03)

| Metric | Production Baseline | Experiment 01 | Experiment 02 | Experiment 03 | Delta vs Production | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Precision** | {base_ov['precision']:.4f} | {exp01_ov['precision']:.4f} | {exp02_ov['precision']:.4f} | {ov['precision']:.4f} | {diff_p:+.4f} | {'Improved' if diff_p > 0 else 'Degraded'} |
| **Recall** | {base_ov['recall']:.4f} | {exp01_ov['recall']:.4f} | {exp02_ov['recall']:.4f} | {ov['recall']:.4f} | {diff_r:+.4f} | {'Improved' if diff_r > 0 else 'Degraded'} |
| **F1-Score** | **{base_ov['f1']:.4f}** | **{exp01_ov['f1']:.4f}** | **{exp02_ov['f1']:.4f}** | **{ov['f1']:.4f}** | **{diff_f1:+.4f}** | **{'Improved' if diff_f1 > 0 else 'Degraded'}** |
| **mAP50** (Ultralytics) | N/A | {exp01_val['ultralytics_metrics']['map50']:.4f} | {exp02_val['ultralytics_metrics']['map50']:.4f} | {ultralytics_map50:.4f} | N/A | Domain Evaluation |
| **mAP50-95** (Ultralytics) | N/A | {exp01_val['ultralytics_metrics']['map50_95']:.4f} | {exp02_val['ultralytics_metrics']['map50_95']:.4f} | {ultralytics_map50_95:.4f} | N/A | Domain Evaluation |
| **Person F1** | {base_pc['person']['f1']:.4f} | {exp01_pc['person']['f1']:.4f} | {exp02_pc['person']['f1']:.4f} | {val_eval['per_class']['person']['f1']:.4f} | {person_diff:+.4f} | {'Improved' if person_diff > 0 else 'Degraded'} |
| **Car F1** | {base_pc['car']['f1']:.4f} | {exp01_pc['car']['f1']:.4f} | {exp02_pc['car']['f1']:.4f} | {val_eval['per_class']['car']['f1']:.4f} | {car_diff:+.4f} | {'Improved' if car_diff > 0 else 'Degraded'} |
| **Motorcycle F1** | {base_pc['motorcycle']['f1']:.4f} | {exp01_pc['motorcycle']['f1']:.4f} | {exp02_pc['motorcycle']['f1']:.4f} | {val_eval['per_class']['motorcycle']['f1']:.4f} | {moto_diff:+.4f} | {'Improved' if moto_diff > 0 else 'Degraded'} |
| **Truck F1** | {base_pc['truck']['f1']:.4f} | {exp01_pc['truck']['f1']:.4f} | {exp02_pc['truck']['f1']:.4f} | {val_eval['per_class']['truck']['f1']:.4f} | {truck_diff:+.4f} | {'Improved' if truck_diff > 0 else 'Degraded'} |
| **Hard-Negative FP/image** | {base_hn['fp_per_image']:.4f} | {exp01_val['validation_eval']['hard_negatives']['fp_per_image']:.4f} | {exp02_val['validation_eval']['hard_negatives']['fp_per_image']:.4f} | {hn['fp_per_image']:.4f} | {hn['fp_per_image'] - base_hn['fp_per_image']:+.4f} | {hn['false_positives']} FP across 28 images |

---

## 2. Counts Summary

- **Production Baseline**: TP={base_ov['tp']}, FP={base_ov['fp']}, FN={base_ov['fn']}
- **Experiment 01**: TP={exp01_ov['tp']}, FP={exp01_ov['fp']}, FN={exp01_ov['fn']}
- **Experiment 02**: TP={exp02_ov['tp']}, FP={exp02_ov['fp']}, FN={exp02_ov['fn']}
- **Experiment 03**: TP={ov['tp']}, FP={ov['fp']}, FN={ov['fn']}

---

## 3. Per-Camera Performance

| Camera | Baseline F1 | EXP01 F1 | EXP02 F1 | EXP03 F1 | Delta vs Production | EXP03 TP | EXP03 FP | EXP03 FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CAM-01** (Gate/Road) | {base_val['per_camera']['CAM-01']['f1']:.4f} | {exp01_val['validation_eval']['per_camera']['CAM-01']['f1']:.4f} | {exp02_val['validation_eval']['per_camera']['CAM-01']['f1']:.4f} | {val_eval['per_camera']['CAM-01']['f1']:.4f} | {val_eval['per_camera']['CAM-01']['f1'] - base_val['per_camera']['CAM-01']['f1']:+.4f} | {val_eval['per_camera']['CAM-01']['tp']} | {val_eval['per_camera']['CAM-01']['fp']} | {val_eval['per_camera']['CAM-01']['fn']} |
| **CAM-02** (Compound) | {base_val['per_camera']['CAM-02']['f1']:.4f} | {exp01_val['validation_eval']['per_camera']['CAM-02']['f1']:.4f} | {exp02_val['validation_eval']['per_camera']['CAM-02']['f1']:.4f} | {val_eval['per_camera']['CAM-02']['f1']:.4f} | {val_eval['per_camera']['CAM-02']['f1'] - base_val['per_camera']['CAM-02']['f1']:+.4f} | {val_eval['per_camera']['CAM-02']['tp']} | {val_eval['per_camera']['CAM-02']['fp']} | {val_eval['per_camera']['CAM-02']['fn']} |
| **CAM-03** (Night IR) | {base_val['per_camera']['CAM-03']['f1']:.4f} | {exp01_val['validation_eval']['per_camera']['CAM-03']['f1']:.4f} | {exp02_val['validation_eval']['per_camera']['CAM-03']['f1']:.4f} | {val_eval['per_camera']['CAM-03']['f1']:.4f} | {val_eval['per_camera']['CAM-03']['f1'] - base_val['per_camera']['CAM-03']['f1']:+.4f} | {val_eval['per_camera']['CAM-03']['tp']} | {val_eval['per_camera']['CAM-03']['fp']} | {val_eval['per_camera']['CAM-03']['fn']} |
| **CAM-04** (Perimeter) | {base_val['per_camera']['CAM-04']['f1']:.4f} | {exp01_val['validation_eval']['per_camera']['CAM-04']['f1']:.4f} | {exp02_val['validation_eval']['per_camera']['CAM-04']['f1']:.4f} | {val_eval['per_camera']['CAM-04']['f1']:.4f} | {val_eval['per_camera']['CAM-04']['f1'] - base_val['per_camera']['CAM-04']['f1']:+.4f} | {val_eval['per_camera']['CAM-04']['tp']} | {val_eval['per_camera']['CAM-04']['fp']} | {val_eval['per_camera']['CAM-04']['fn']} |

---

## 4. Analytical Conclusion & Decision

**Result**: **EXP03 = {decision}**

Experiment 03 tested controlled partial-freeze fine-tuning (`freeze=5`, `lr0=0.001`).
Candidate model weights remain strictly isolated in `{best_pt}`.
Production weights `weights/yolov8n.pt` are completely untouched.
"""

    with open("reports/PHASE_A4_EXP03_VALIDATION.md", "w", encoding="utf-8") as f:
        f.write(val_comparison_md)
    print("[+] Validation comparison written to reports/PHASE_A4_EXP03_VALIDATION.md")

    # 10. Write complete checkpoint
    complete_md = f"""# PRAHARI-AI — Checkpoint: A4_EXP03_COMPLETE

Experiment: A4_EXP03
Status: COMPLETE

Training:
Epochs completed: {epochs_completed}
Best epoch: {best_epoch}
Training duration: {duration}s

Learning rate: lr0=0.001
Freeze configuration: freeze=5 (Backbone layers 0..4 frozen)
Image size: 640
Batch: 16

Validation:

Production Precision: {base_ov['precision']:.4f}
EXP03 Precision: {ov['precision']:.4f}

Production Recall: {base_ov['recall']:.4f}
EXP03 Recall: {ov['recall']:.4f}

Production F1: {base_ov['f1']:.4f}
EXP03 F1: {ov['f1']:.4f}

Person F1: {val_eval['per_class']['person']['f1']:.4f}
Car F1: {val_eval['per_class']['car']['f1']:.4f}
Motorcycle F1: {val_eval['per_class']['motorcycle']['f1']:.4f}
Truck F1: {val_eval['per_class']['truck']['f1']:.4f}

Hard-negative FP: {hn['false_positives']} ({hn['fp_per_image']} FP/image)

CAM-01 F1: {val_eval['per_camera']['CAM-01']['f1']:.4f}
CAM-02 F1: {val_eval['per_camera']['CAM-02']['f1']:.4f}
CAM-03 F1: {val_eval['per_camera']['CAM-03']['f1']:.4f}
CAM-04 F1: {val_eval['per_camera']['CAM-04']['f1']:.4f}

Candidate path: {best_pt}
Candidate SHA256: {best_sha}

Decision: {decision}

Production modified: NO

Next recommended action:
{"Proceed to validation comparison and candidate scorecard analysis." if decision == "PROMISING" else "Evaluate whether small-object resolution (imgsz=800) or architecture capacity (YOLOv8s) is the limiting factor."}
"""
    with open("reports/checkpoints/A4_EXP03_COMPLETE.md", "w", encoding="utf-8") as f:
        f.write(complete_md)
    print("[+] Checkpoint written to reports/checkpoints/A4_EXP03_COMPLETE.md")

    # 11. Save json results
    res_json = {
        "candidate": best_pt,
        "sha256": best_sha,
        "epochs_completed": epochs_completed,
        "best_epoch": best_epoch,
        "duration_sec": duration,
        "hyperparameters": {
            "lr0": 0.001,
            "freeze": 5,
            "batch": 16,
            "epochs": 50,
            "imgsz": 640
        },
        "ultralytics_metrics": {
            "precision": ultralytics_p,
            "recall": ultralytics_r,
            "map50": ultralytics_map50,
            "map50_95": ultralytics_map50_95
        },
        "validation_eval": val_eval,
        "decision": decision
    }
    with open("reports/exp03_validation_result.json", "w", encoding="utf-8") as f:
        json.dump(res_json, f, indent=2)

    print("\n[+] EXPERIMENT 03 PIPELINE COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
