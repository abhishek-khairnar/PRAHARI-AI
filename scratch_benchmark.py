import os
import sys
import time
import math
import cv2
import numpy as np
import torch

# Limit threads
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
torch.set_num_threads(2)
cv2.setNumThreads(2)

print("=" * 60)
print("PRAHARI-AI DEEP PIPELINE BENCHMARK & DIAGNOSTIC")
print("=" * 60)

# 1. GPU Verification
cuda_avail = torch.cuda.is_available()
print(f"CUDA Available: {cuda_avail}")
if cuda_avail:
    device_name = torch.cuda.get_device_name(0)
    print(f"Device Name: {device_name}")
    print(f"Device Count: {torch.cuda.device_count()}")
    print(f"Allocated Memory: {torch.cuda.memory_allocated() / (1024*1024):.2f} MB")
    print(f"Reserved Memory: {torch.cuda.memory_reserved() / (1024*1024):.2f} MB")
else:
    print("WARNING: CUDA is NOT available! Running on CPU.")

# 2. RTSP Connection & Frame Capture Test
rtsp_url = "rtsp://localhost:8554/mystream"
print(f"\nConnecting to RTSP Stream: {rtsp_url}...")
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    print(f"ERROR: Could not open RTSP stream at {rtsp_url}")
    sys.exit(1)

ret, test_frame = cap.read()
if not ret or test_frame is None:
    print("ERROR: Failed to read first frame from RTSP stream")
    sys.exit(1)

h, w, c = test_frame.shape
print(f"Successfully captured frame: {w}x{h}, dtype={test_frame.dtype}, channels={c}")

# 3. Benchmark Individual Stages
from ultralytics import YOLO
from centroid_tracker import CentroidTracker
from anpr_engine import ANPREngine

print("\nLoading Models...")
yolo_model = YOLO("yolov8n.pt")
device = "cuda" if cuda_avail else "cpu"
yolo_model.to(device)
if device == "cuda":
    try:
        yolo_model.model.half()
        print("YOLO FP16 Half precision mode: ENABLED")
    except Exception as e:
        print(f"YOLO FP16 Half precision failed: {e}")

tracker = CentroidTracker(max_disappeared=15, max_distance=180.0)
anpr = ANPREngine()

# Warmup YOLO
dummy = np.zeros((640, 640, 3), dtype=np.uint8)
_ = yolo_model.predict(source=dummy, imgsz=640, device=device, verbose=False, half=(device=="cuda"))

print("\n--- BENCHMARKING 100 FRAMES ---")
capture_times = []
resize_times = []
yolo_times = []
track_times = []
face_times = []
anpr_det_times = []
ocr_times = []
draw_times = []
encode_times = []
decode_corrupt_count = 0
valid_frames_count = 0

for i in range(100):
    # Capture
    t0 = time.perf_counter()
    ret, frame = cap.read()
    t_cap = (time.perf_counter() - t0) * 1000.0
    if not ret or frame is None:
        continue
    capture_times.append(t_cap)

    # Resize
    t0 = time.perf_counter()
    if frame.shape[1] > 1920 or frame.shape[0] > 1080:
        scale = min(1920.0 / frame.shape[1], 1080.0 / frame.shape[0])
        proc_frame = cv2.resize(frame, (int(frame.shape[1] * scale), int(frame.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)
    else:
        proc_frame = frame
    t_resize = (time.perf_counter() - t0) * 1000.0
    resize_times.append(t_resize)

    # YOLO
    t0 = time.perf_counter()
    with torch.inference_mode():
        results = yolo_model.predict(
            source=proc_frame,
            imgsz=640,
            classes=[0, 1, 2, 3, 5, 7],
            conf=0.35,
            device=device,
            verbose=False,
            half=(device=="cuda")
        )
    t_yolo = (time.perf_counter() - t0) * 1000.0
    yolo_times.append(t_yolo)

    # Extract detections
    detections = []
    if results and len(results) > 0:
        boxes = results[0].boxes
        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cls_name = "Person" if cls_id == 0 else "Vehicle"
            detections.append((x1, y1, x2, y2, cls_name, conf))

    # Tracking
    t0 = time.perf_counter()
    tracked = tracker.update(detections)
    t_track = (time.perf_counter() - t0) * 1000.0
    track_times.append(t_track)

    # Draw
    t0 = time.perf_counter()
    display_frame = proc_frame.copy()
    for oid, obj in tracked.items():
        (x1, y1, x2, y2) = obj["bbox"]
        (cx, cy) = obj["centroid"]
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(display_frame, (cx, cy), 4, (0, 0, 255), -1)
    cv2.line(display_frame, (0, 756), (display_frame.shape[1], 756), (0, 0, 255), 2)
    t_draw = (time.perf_counter() - t0) * 1000.0
    draw_times.append(t_draw)

    # Encode JPEG
    t0 = time.perf_counter()
    ret_enc, jpeg_buf = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    t_enc = (time.perf_counter() - t0) * 1000.0
    encode_times.append(t_enc)

    # Test Decode Integrity
    if ret_enc:
        dec_frame = cv2.imdecode(np.frombuffer(jpeg_buf, dtype=np.uint8), cv2.IMREAD_COLOR)
        if dec_frame is not None and dec_frame.shape == display_frame.shape:
            valid_frames_count += 1
        else:
            decode_corrupt_count += 1
    else:
        decode_corrupt_count += 1

cap.release()

# 4. Measure isolated ANPR Plate Detection & OCR latency
print("\n--- BENCHMARKING ISOLATED ANPR & OCR LATENCY ---")
test_vehicle_crop = np.zeros((300, 400, 3), dtype=np.uint8)
cv2.rectangle(test_vehicle_crop, (100, 180), (300, 240), (255, 255, 255), -1)
cv2.putText(test_vehicle_crop, "MH 02 FU 9304", (110, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

for _ in range(5):
    t0 = time.perf_counter()
    p_crop, is_det, p_conf = anpr.extract_plate_crop_from_vehicle(test_vehicle_crop, conf_threshold=0.15)
    t_anpr_det = (time.perf_counter() - t0) * 1000.0
    anpr_det_times.append(t_anpr_det)

    t0 = time.perf_counter()
    if p_crop is not None:
        clean_txt, raw_txt, o_conf, val, tier = anpr.read_plate(p_crop)
    else:
        clean_txt, raw_txt, o_conf, val, tier = anpr.read_plate(test_vehicle_crop[180:240, 100:300])
    t_ocr = (time.perf_counter() - t0) * 1000.0
    ocr_times.append(t_ocr)

# 5. Print Detailed Diagnostic Report
print("\n" + "=" * 60)
print("BENCHMARK RESULTS (Averages over 100 frames)")
print("=" * 60)
avg_cap = np.mean(capture_times)
avg_res = np.mean(resize_times)
avg_yolo = np.mean(yolo_times)
avg_track = np.mean(track_times)
avg_draw = np.mean(draw_times)
avg_enc = np.mean(encode_times)
avg_anpr_det = np.mean(anpr_det_times)
avg_ocr = np.mean(ocr_times)
pipeline_total = avg_cap + avg_res + avg_yolo + avg_track + avg_draw + avg_enc

print(f"Capture:            {avg_cap:6.2f} ms")
print(f"Resize:             {avg_res:6.2f} ms")
print(f"YOLO (GPU FP16):    {avg_yolo:6.2f} ms")
print(f"Tracking:           {avg_track:6.2f} ms")
print(f"Drawing:            {avg_draw:6.2f} ms")
print(f"JPEG encode:        {avg_enc:6.2f} ms")
print("-" * 60)
print(f"Total AI Frame:     {pipeline_total:6.2f} ms")
print(f"Theoretical Max FPS:{1000.0 / pipeline_total:6.1f} FPS")
print(f"Isolated ANPR Det:  {avg_anpr_det:6.2f} ms")
print(f"Isolated PaddleOCR: {avg_ocr:6.2f} ms (NOTE: CPU Heavy!)")
print("-" * 60)
print(f"Valid JPEG frames:  {valid_frames_count}/100")
print(f"Corrupt frames:     {decode_corrupt_count}/100")
print("=" * 60)
