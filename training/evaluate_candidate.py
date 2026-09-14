"""
PRAHARI-AI — Phase A2 Candidate Evaluation & Comparison Engine
Evaluates candidate models against:
1. Frozen Phase A1 Spatial IoU Benchmark (OBJECT_DETECTION_GT_V2) across CAM-01..CAM-04
2. Held-out Unseen Test Set (dataset/images/test)
3. Resource Profiling on NVIDIA RTX 3050 6GB (Latency, FPS, CUDA VRAM, CPU %)
Produces side-by-side comparison tables between Baseline YOLOv8n and Candidate model.
"""

import os
import sys
sys.path.insert(0, os.path.abspath('.'))

import time
import json
import torch
import psutil
from ultralytics import YOLO

from benchmark.video_analysis import evaluate_object_detection_v2
from benchmark.metrics import match_objects_class_aware
from benchmark.config import YOLO_MODEL_PATH, RESULTS_DIR

def evaluate_on_unseen_test_set(model: YOLO, test_images_dir: str = "dataset/images/test", test_labels_dir: str = "dataset/labels/test", iou_threshold: float = 0.50):
    """
    Evaluates model ONCE on the held-out unseen test set.
    """
    CLASS_MAP_INV = {0: "person", 1: "car", 2: "motorcycle", 3: "truck", 4: "bus"}

    img_files = sorted([f for f in os.listdir(test_images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    
    all_pred_boxes = []
    all_pred_classes = []
    all_pred_confs = []
    all_gt_boxes = []
    all_gt_classes = []

    per_image_results = {}

    for img_name in img_files:
        base_name = os.path.splitext(img_name)[0]
        img_path = os.path.join(test_images_dir, img_name)
        lbl_path = os.path.join(test_labels_dir, f"{base_name}.txt")

        # Load image dimensions
        import cv2
        img = cv2.imread(img_path)
        if img is None:
            continue
        h_img, w_img = img.shape[:2]

        # Read Ground Truth
        gt_boxes = []
        gt_classes = []
        if os.path.exists(lbl_path):
            with open(lbl_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        c_id = int(parts[0])
                        xc, yc, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        # convert normalized yolo to pixel [x1, y1, x2, y2]
                        x1 = (xc - bw / 2.0) * w_img
                        y1 = (yc - bh / 2.0) * h_img
                        x2 = (xc + bw / 2.0) * w_img
                        y2 = (yc + bh / 2.0) * h_img
                        gt_boxes.append([round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)])
                        gt_classes.append(CLASS_MAP_INV.get(c_id, f"unknown_{c_id}"))

        # Run Inference
        results = model(img, conf=0.35, imgsz=640, verbose=False)[0]
        pred_boxes = []
        pred_classes = []
        pred_confs = []

        for b in results.boxes:
            c_idx = int(b.cls[0])
            c_name = model.names[c_idx]
            if c_name in ["person", "car", "motorcycle", "truck", "bus"]:
                xy = b.xyxy[0].cpu().numpy().tolist()
                conf = float(b.conf[0])
                pred_boxes.append([round(x, 1) for x in xy])
                pred_classes.append(c_name)
                pred_confs.append(conf)

        match_res = match_objects_class_aware(
            pred_boxes=pred_boxes,
            pred_classes=pred_classes,
            pred_confs=pred_confs,
            gt_boxes=gt_boxes,
            gt_classes=gt_classes,
            iou_threshold=iou_threshold
        )
        per_image_results[img_name] = match_res

        all_pred_boxes.extend(pred_boxes)
        all_pred_classes.extend(pred_classes)
        all_pred_confs.extend(pred_confs)
        all_gt_boxes.extend(gt_boxes)
        all_gt_classes.extend(gt_classes)

    overall_test = match_objects_class_aware(
        pred_boxes=all_pred_boxes,
        pred_classes=all_pred_classes,
        pred_confs=all_pred_confs,
        gt_boxes=all_gt_boxes,
        gt_classes=all_gt_classes,
        iou_threshold=iou_threshold
    )

    return {
        "overall": overall_test["overall"],
        "per_class": overall_test["per_class"],
        "macro": overall_test["macro"],
        "total_test_images": len(img_files),
        "per_image": per_image_results
    }

def benchmark_resource_performance(model: YOLO, num_warmup: int = 5, num_eval: int = 25):
    """
    Measures inference latency, FPS, CUDA VRAM usage, and CPU % on RTX 3050.
    """
    dummy_frame = torch.zeros((1, 3, 640, 640), dtype=torch.float32)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        dummy_frame = dummy_frame.to(device)

    # Warmup
    for _ in range(num_warmup):
        _ = model(dummy_frame, verbose=False)

    if device == "cuda":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        start_vram = torch.cuda.memory_allocated() / (1024 * 1024)
    else:
        start_vram = 0.0

    latencies = []
    cpu_samples = []

    for _ in range(num_eval):
        t0 = time.perf_counter()
        _ = model(dummy_frame, verbose=False)
        if device == "cuda":
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        cpu_samples.append(psutil.cpu_percent(interval=None))

    if device == "cuda":
        peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)
    else:
        peak_vram = 0.0

    avg_lat = round(sum(latencies) / len(latencies), 2)
    fps = round(1000.0 / avg_lat, 2) if avg_lat > 0 else 0.0
    avg_cpu = round(sum(cpu_samples) / len(cpu_samples), 1)

    return {
        "avg_latency_ms": avg_lat,
        "fps": fps,
        "peak_vram_mb": round(peak_vram, 2),
        "avg_cpu_percent": avg_cpu,
        "device": device
    }

def compare_candidate_with_baseline(candidate_model_path: str):
    """
    Executes apples-to-apples comparison between baseline YOLOv8n and candidate model.
    """
    print("=" * 75)
    print(" PRAHARI-AI PHASE A2 — CANDIDATE VS BASELINE BENCHMARK COMPARISON")
    print("=" * 75)

    print(f"[*] Loading Baseline Model: {YOLO_MODEL_PATH}")
    baseline_model = YOLO(YOLO_MODEL_PATH)

    print(f"[*] Loading Candidate Model: {candidate_model_path}")
    candidate_model = YOLO(candidate_model_path)

    # 1. Phase A1 Benchmark Evaluation (CAM-01..CAM-04)
    print("\n[1/3] Running Phase A1 Benchmark on Baseline (YOLOv8n)...")
    base_bench = evaluate_object_detection_v2(baseline_model)

    print("\n[2/3] Running Phase A1 Benchmark on Candidate...")
    cand_bench = evaluate_object_detection_v2(candidate_model)

    # 2. Held-out Unseen Test Set
    print("\n[3/3] Evaluating on Held-Out Unseen Test Set (dataset/images/test)...")
    base_test = evaluate_on_unseen_test_set(baseline_model)
    cand_test = evaluate_on_unseen_test_set(candidate_model)

    # 3. Resource Profiling
    print("\n[*] Profiling Resource Utilization on RTX 3050 6GB...")
    base_res = benchmark_resource_performance(baseline_model)
    cand_res = benchmark_resource_performance(candidate_model)

    # Prepare comparison data
    comparison = {
        "baseline_model": {
            "name": "yolov8n.pt (Production Frozen)",
            "path": YOLO_MODEL_PATH,
            "benchmark": base_bench,
            "unseen_test": base_test,
            "resources": base_res
        },
        "candidate_model": {
            "name": os.path.basename(candidate_model_path),
            "path": candidate_model_path,
            "benchmark": cand_bench,
            "unseen_test": cand_test,
            "resources": cand_res
        }
    }

    # Print Formatted Comparison Table (Step 13)
    print("\n" + "=" * 85)
    print("                OBJECT DETECTION COMPARISON: BASELINE vs CANDIDATE")
    print("=" * 85)
    print(f"{'Metric':<30} | {'YOLOv8n Baseline':<22} | {'Candidate Model':<22}")
    print("-" * 85)

    classes_to_compare = ["person", "car", "motorcycle", "truck", "bus"]
    
    # Calculate pooled class metrics across cameras
    def get_pooled_class_metrics(bench_dict):
        pooled = {c: {"tp": 0, "fp": 0, "fn": 0} for c in classes_to_compare}
        for cam_data in bench_dict["cameras"].values():
            for c in classes_to_compare:
                if c in cam_data["per_class"]:
                    p = cam_data["per_class"][c]
                    pooled[c]["tp"] += p["tp"]
                    pooled[c]["fp"] += p["fp"]
                    pooled[c]["fn"] += p["fn"]
        metrics = {}
        for c in classes_to_compare:
            tp = pooled[c]["tp"]
            fp = pooled[c]["fp"]
            fn = pooled[c]["fn"]
            prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
            rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
            f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) > 0 else 0.0
            metrics[c] = {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
        return metrics

    base_pooled = get_pooled_class_metrics(base_bench)
    cand_pooled = get_pooled_class_metrics(cand_bench)

    for c in classes_to_compare:
        bp = base_pooled[c]
        cp = cand_pooled[c]
        print(f"{c.capitalize() + ' Precision':<30} | {bp['precision']:<22.2%} | {cp['precision']:<22.2%}")
        print(f"{c.capitalize() + ' Recall':<30} | {bp['recall']:<22.2%} | {cp['recall']:<22.2%}")
        print(f"{c.capitalize() + ' F1':<30} | {bp['f1']:<22.4f} | {cp['f1']:<22.4f}")
        print("-" * 85)

    # Overall metrics
    bo = base_bench["macro_summary"]
    co = cand_bench["macro_summary"]
    print(f"{'Overall Precision (Macro)':<30} | {bo['mean_precision']:<22.2%} | {co['mean_precision']:<22.2%}")
    print(f"{'Overall Recall (Macro)':<30} | {bo['mean_recall']:<22.2%} | {co['mean_recall']:<22.2%}")
    print(f"{'Overall F1 (Macro)':<30} | {bo['mean_f1']:<22.4f} | {co['mean_f1']:<22.4f}")
    print("=" * 85)

    # Per-Camera F1 Comparison
    print("\nPER-CAMERA COMPARISON:")
    for cam in ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]:
        b_cam = base_bench["cameras"][cam]
        c_cam = cand_bench["cameras"][cam]
        print(f"  {cam:<10}: Baseline F1 = {b_cam['overall']['f1']:.4f} ({b_cam['status']})  vs  Candidate F1 = {c_cam['overall']['f1']:.4f} ({c_cam['status']})")
        if "person" in b_cam["per_class"]:
            bp_f1 = b_cam["per_class"]["person"]["f1"]
            cp_f1 = c_cam["per_class"]["person"]["f1"]
            print(f"             Person F1: Baseline = {bp_f1:.4f}  vs  Candidate = {cp_f1:.4f}")

    # Save to JSON
    out_json = os.path.join(RESULTS_DIR, "candidate_model_evaluation.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print(f"\n[+] Saved detailed comparison -> {out_json}")

    return comparison

if __name__ == "__main__":
    cand_path = "weights/candidates/yolov8s.pt"
    if len(sys.argv) > 1:
        cand_path = sys.argv[1]
    compare_candidate_with_baseline(cand_path)
