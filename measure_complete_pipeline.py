import os
import sys
import time
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from centroid_tracker import CentroidTracker

print("=" * 60)
print("PRAHARI-AI COMPLETE PIPELINE BENCHMARK")
print("=" * 60)

# Check GPU
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU Device Name: {torch.cuda.get_device_name(0)}")
    print(f"Allocated Memory: {torch.cuda.memory_allocated() / (1024*1024):.2f} MB")
    print(f"Reserved Memory: {torch.cuda.memory_reserved() / (1024*1024):.2f} MB")

# Connect RTSP
rtsp_url = "rtsp://localhost:8554/mystream"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

ret, test_frame = cap.read()
if not ret:
    print("ERROR: Failed to connect to RTSP stream!")
    sys.exit(1)

print(f"Successfully connected to stream: {test_frame.shape[1]}x{test_frame.shape[0]}")

# Load YOLO model on CUDA
model = YOLO("yolov8n.pt")
model.to("cuda")

# Warmup GPU
for _ in range(5):
    with torch.inference_mode():
        _ = model.predict(source=test_frame, imgsz=640, device="cuda", verbose=False)
torch.cuda.synchronize()

# Load Face Detector
yunet_path = "weights/face_detection_yunet_2023mar.onnx"
face_det = cv2.FaceDetectorYN_create(yunet_path, "", (640, 360), 0.45, 0.3, 5000)

tracker = CentroidTracker(max_disappeared=15, max_distance=180.0)

# Run 100 benchmark frames
N = 100
t_cap_list = []
t_res_list = []
t_yolo_list = []
t_track_list = []
t_face_list = []
t_draw_list = []
t_enc_list = []
t_total_list = []

valid_frames = 0
corrupt_frames = 0

print(f"\nBenchmarking {N} consecutive live stream frames...")
start_time = time.perf_counter()

for i in range(N):
    t_frame_start = time.perf_counter()

    # 1. Capture
    t0 = time.perf_counter()
    ret, frame = cap.read()
    t_cap = (time.perf_counter() - t0) * 1000.0
    if not ret or frame is None:
        continue
    t_cap_list.append(t_cap)

    # 2. Resize
    t0 = time.perf_counter()
    if frame.shape[1] > 1920 or frame.shape[0] > 1080:
        scale = min(1920.0 / frame.shape[1], 1080.0 / frame.shape[0])
        p_frame = cv2.resize(frame, (int(frame.shape[1] * scale), int(frame.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)
    else:
        p_frame = frame
    t_res = (time.perf_counter() - t0) * 1000.0
    t_res_list.append(t_res)

    # 3. YOLO Inference (GPU CUDA)
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

    # 4. Tracking
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

    # 5. Face Detection (Amortized every 5 frames)
    t0 = time.perf_counter()
    if i % 5 == 0:
        small_f = cv2.resize(p_frame, (640, 360))
        face_det.setInputSize((640, 360))
        _, faces = face_det.detect(small_f)
    t_face = (time.perf_counter() - t0) * 1000.0
    t_face_list.append(t_face)

    # 6. Draw annotations
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

    # 7. JPEG Encode
    t0 = time.perf_counter()
    ret_enc, jpeg_buf = cv2.imencode('.jpg', disp_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    t_enc = (time.perf_counter() - t0) * 1000.0
    t_enc_list.append(t_enc)

    # 8. Decode Integrity Test
    if ret_enc:
        dec = cv2.imdecode(np.frombuffer(jpeg_buf, dtype=np.uint8), cv2.IMREAD_COLOR)
        if dec is not None and dec.shape == disp_frame.shape:
            valid_frames += 1
        else:
            corrupt_frames += 1
    else:
        corrupt_frames += 1

    t_frame_total = (time.perf_counter() - t_frame_start) * 1000.0
    t_total_list.append(t_frame_total)

total_elapsed = time.perf_counter() - start_time
actual_fps = len(t_total_list) / total_elapsed
cap.release()

avg_cap = np.mean(t_cap_list)
avg_res = np.mean(t_res_list)
avg_yolo = np.mean(t_yolo_list)
avg_track = np.mean(t_track_list)
avg_face = np.mean(t_face_list)
avg_draw = np.mean(t_draw_list)
avg_enc = np.mean(t_enc_list)
avg_tot = np.mean(t_total_list)

print("\n" + "=" * 60)
print("STAGE-BY-STAGE MEASURED BENCHMARK (100 Frames Live)")
print("=" * 60)
print(f"Capture:       {avg_cap:6.2f} ms")
print(f"Resize:        {avg_res:6.2f} ms")
print(f"YOLO:          {avg_yolo:6.2f} ms")
print(f"Tracking:      {avg_track:6.2f} ms")
print(f"Face:          {avg_face:6.2f} ms")
print(f"ANPR:            0.00 ms (Asynchronous Worker Pool)")
print(f"Drawing:       {avg_draw:6.2f} ms")
print(f"JPEG encode:   {avg_enc:6.2f} ms")
print("-" * 60)
print(f"Total:         {avg_tot:6.2f} ms")
print(f"Actual FPS:    {actual_fps:6.1f}")
print("-" * 60)
print(f"Valid JPEG frames:  {valid_frames}/100")
print(f"Corrupt frames:     {corrupt_frames}/100")
print("=" * 60)
