import os
import hashlib
import json
import time
import numpy as np
import torch
from ultralytics import YOLO

EXPECTED_SHA256 = "F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36".lower()

def test_model():
    model_path = os.path.join(os.path.dirname(__file__), "..", "..", "weights", "yolov8n.pt")
    model_path = os.path.abspath(model_path)
    
    result = {
        "model_path": model_path,
        "exists": False,
        "readable": False,
        "file_size": 0,
        "sha256": None,
        "sha256_match": False,
        "model_load_cuda": False,
        "model_load_cpu": False,
        "cuda_inference": False,
        "cpu_inference": False,
        "inference_time_cuda_ms": None,
        "inference_time_cpu_ms": None,
        "classes_count": 0,
        "classes": {},
        "expected_classes_present": {},
        "class_mapping_correct": False,
        "errors": []
    }

    # 1. Existence and readability
    if not os.path.exists(model_path):
        result["errors"].append(f"Model file not found at {model_path}")
        return save_and_return(result)
    result["exists"] = True
    result["file_size"] = os.path.getsize(model_path)

    try:
        with open(model_path, "rb") as f:
            h = hashlib.sha256()
            while chunk := f.read(8192 * 1024):
                h.update(chunk)
            calc_hash = h.hexdigest().lower()
        result["readable"] = True
        result["sha256"] = calc_hash
        result["sha256_match"] = (calc_hash == EXPECTED_SHA256)
        if not result["sha256_match"]:
            result["errors"].append(f"SHA256 mismatch! Expected {EXPECTED_SHA256}, got {calc_hash}")
            return save_and_return(result)
    except Exception as e:
        result["errors"].append(f"Error reading model file: {e}")
        return save_and_return(result)

    # 2. CUDA loading and inference
    dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
    try:
        model_cuda = YOLO(model_path)
        result["model_load_cuda"] = True
        result["classes_count"] = len(model_cuda.names)
        result["classes"] = model_cuda.names

        # Expected classes check
        expected = ["person", "car", "motorcycle", "truck", "bus"]
        for exp in expected:
            found = False
            for cid, cname in model_cuda.names.items():
                if cname.lower() == exp:
                    found = True
                    result["expected_classes_present"][exp] = {"class_id": cid, "name": cname}
                    break
            if not found:
                result["expected_classes_present"][exp] = None

        result["class_mapping_correct"] = all(result["expected_classes_present"].get(k) is not None for k in expected)

        # Warmup and test CUDA inference
        _ = model_cuda.predict(source=dummy_img, device="cuda:0" if torch.cuda.is_available() else 0, verbose=False)
        t0 = time.perf_counter()
        preds_cuda = model_cuda.predict(source=dummy_img, device="cuda:0" if torch.cuda.is_available() else 0, verbose=False)
        t1 = time.perf_counter()
        result["cuda_inference"] = True
        result["inference_time_cuda_ms"] = round((t1 - t0) * 1000, 2)
    except Exception as e:
        result["errors"].append(f"CUDA loading/inference failed: {e}")

    # 3. CPU loading and inference (fallback behavior)
    try:
        model_cpu = YOLO(model_path)
        result["model_load_cpu"] = True
        t0 = time.perf_counter()
        preds_cpu = model_cpu.predict(source=dummy_img, device="cpu", verbose=False)
        t1 = time.perf_counter()
        result["cpu_inference"] = True
        result["inference_time_cpu_ms"] = round((t1 - t0) * 1000, 2)
    except Exception as e:
        result["errors"].append(f"CPU fallback inference failed: {e}")

    return save_and_return(result)

def save_and_return(result):
    out_path = os.path.join(os.path.dirname(__file__), "model_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Model test result written to {out_path}")
    return result

if __name__ == "__main__":
    test_model()
