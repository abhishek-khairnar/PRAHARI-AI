import time
import torch
import cv2
import numpy as np
from ultralytics import YOLO

print("=" * 60)
print("TESTING YOLO NMS & INFERENCE SPEED ON CUDA")
print("=" * 60)

model = YOLO("yolov8n.pt")
model.to("cuda")

# Test 1080p frame
frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

# Warmup
for _ in range(5):
    with torch.inference_mode():
        _ = model.predict(source=frame, imgsz=640, device="cuda", verbose=False)
torch.cuda.synchronize()

print("\nBenchmarking 50 YOLO inferences on CUDA...")
times = []
for i in range(50):
    t0 = time.perf_counter()
    with torch.inference_mode():
        results = model.predict(
            source=frame,
            imgsz=640,
            classes=[0, 1, 2, 3, 5, 7],
            conf=0.35,
            device="cuda",
            verbose=False
        )
    torch.cuda.synchronize()
    t_ms = (time.perf_counter() - t0) * 1000.0
    times.append(t_ms)

print(f"Mean YOLO Inference Time: {np.mean(times):.2f} ms")
print(f"Min YOLO Inference Time:  {np.min(times):.2f} ms")
print(f"Max YOLO Inference Time:  {np.max(times):.2f} ms")
print(f"Throughput:               {1000.0 / np.mean(times):.1f} FPS")
