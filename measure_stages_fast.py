import os
import sys
import time
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from centroid_tracker import CentroidTracker

print("=" * 60)
print("FAST STAGE-BY-STAGE LATENCY PROFILER")
print("=" * 60)

# Check GPU
print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"GPU Device Name: {torch.cuda.get_device_name(0)}")

# Load a sample frame from RTSP or file
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
cap = cv2.VideoCapture("rtsp://localhost:8554/mystream", cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

ret, sample_frame = cap.read()
cap.release()

if not ret or sample_frame is None:
    print("Capturing fallback frame from test file or dummy...")
    sample_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

print(f"Sample frame loaded: {sample_frame.shape}")

# Load YOLO model
model = YOLO("yolov8n.pt")
model.to("cuda")

# Warmup GPU
for _ in range(5):
    _ = model.predict(source=sample_frame, imgsz=640, device="cuda", verbose=False)
torch.cuda.synchronize()

# Load Face Detector
yunet_path = "weights/face_detection_yunet_2023mar.onnx"
face_det = cv2.FaceDetectorYN_create(yunet_path, "", (640, 360), 0.45, 0.3, 5000)

tracker = CentroidTracker(max_disappeared=15, max_distance=180.0)

# Measure 50 iterations with loaded frame in memory
N = 50
t_res_list, t_yolo_list, t_track_list, t_face_list, t_draw_list, t_enc_list = [], [], [], [], [], []
valid_frames, corrupt_frames = 0, 0

print(f"\nBenchmarking {N} frames in memory...")
for i in range(N):
    # 1. Resize (if needed)
    t0 = time.perf_counter()
    p_frame = cv2.resize(sample_frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
    t_res = (time.perf_counter() - t0) * 1000.0
    t_res_list.append(t_res)

    # 2. YOLO Inference (GPU on RTX 3050)
    t0 = time.perf_counter()
    with torch.inference_mode():
        results = model.predict(
            source=p_frame,
            imgsz=640,
            classes=[0, 1, 2, 3, 5, 7],
            conf=0.35,
            device="cuda",
            verbose=False
        )
    torch.cuda.synchronize()
    t_yolo = (time.perf_counter() - t0) * 1000.0
    t_yolo_list.append(t_yolo)

    # 3. Tracking
    t0 = time.perf_counter()
    detections = []
    if results and len(results) > 0:
        boxes = results[0].boxes
        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cls_name = "Person" if cls_id == 0 else "Vehicle"
            detections.append((x1, y1, x2, y2, cls_name, conf))
    tracked = tracker.update(detections)
    t_track = (time.perf_counter() - t0) * 1000.0
    t_track_list.append(t_track)

    # 4. Face Detection (Global 640x360 amortized every 5 frames)
    t0 = time.perf_counter()
    if i % 5 == 0:
        small_f = cv2.resize(p_frame, (640, 360))
        face_det.setInputSize((640, 360))
        _, faces = face_det.detect(small_f)
    t_face = (time.perf_counter() - t0) * 1000.0
    t_face_list.append(t_face)

    # 5. Draw annotations
    t0 = time.perf_counter()
    disp_frame = p_frame.copy()
    for oid, obj in tracked.items():
        (x1, y1, x2, y2) = obj["bbox"]
        (cx, cy) = obj["centroid"]
        cv2.rectangle(disp_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(disp_frame, (cx, cy), 4, (0, 0, 255), -1)
        label = f"ID #{oid} {obj['class']}"
        cv2.putText(disp_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.line(disp_frame, (0, 756), (disp_frame.shape[1], 756), (0, 0, 255), 2)
    t_draw = (time.perf_counter() - t0) * 1000.0
    t_draw_list.append(t_draw)

    # 6. JPEG Encode
    t0 = time.perf_counter()
    ret_enc, jpeg_buf = cv2.imencode('.jpg', disp_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    t_enc = (time.perf_counter() - t0) * 1000.0
    t_enc_list.append(t_enc)

    # 7. Decode Integrity Test
    if ret_enc:
        dec = cv2.imdecode(np.frombuffer(jpeg_buf, dtype=np.uint8), cv2.IMREAD_COLOR)
        if dec is not None and dec.shape == disp_frame.shape:
            valid_frames += 1
        else:
            corrupt_frames += 1
    else:
        corrupt_frames += 1

avg_res = np.mean(t_res_list)
avg_yolo = np.mean(t_yolo_list)
avg_track = np.mean(t_track_list)
avg_face = np.mean(t_face_list)
avg_draw = np.mean(t_draw_list)
avg_enc = np.mean(t_enc_list)
tot_ai = avg_res + avg_yolo + avg_track + avg_face + avg_draw + avg_enc

print("\n" + "=" * 60)
print("STAGE TIMING BENCHMARK (Averages across 50 frames)")
print("=" * 60)
print(f"Frame Resize:       {avg_res:6.2f} ms")
print(f"YOLO Inference:     {avg_yolo:6.2f} ms (GPU on RTX 3050)")
print(f"Tracking Update:    {avg_track:6.2f} ms")
print(f"Face Detection:     {avg_face:6.2f} ms (Amortized every 5 frames)")
print(f"Drawing Overlays:   {avg_draw:6.2f} ms")
print(f"JPEG Encoding:      {avg_enc:6.2f} ms")
print("-" * 60)
print(f"Total AI Frame Time:{tot_ai:6.2f} ms")
print(f"Max AI Throughput:  {1000.0 / tot_ai:6.1f} FPS")
print(f"Valid JPEG frames:  {valid_frames}/50")
print(f"Corrupt frames:     {corrupt_frames}/50")
print("=" * 60)
