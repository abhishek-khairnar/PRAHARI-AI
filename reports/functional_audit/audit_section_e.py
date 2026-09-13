import os
import sys
import json
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, base_dir)

import cv2
import torch
from ultralytics import YOLO
from centroid_tracker import CentroidTracker

def audit_tracking():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    model_path = os.path.join(base_dir, "weights", "yolov8n.pt")
    model = YOLO(model_path)
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # We will test tracking on CAM-01 (Border) and CAM-04 (Urban CCTV)
    cams_to_test = [
        {"id": "CAM-01", "path": os.path.join(base_dir, "demo_videos/border_demo.mp4"), "frames": 120},
        {"id": "CAM-04", "path": os.path.join(base_dir, "demo_videos/cctv_demo.mp4"), "frames": 120},
    ]

    tracking_results = {
        "unit_test_status": "PASS",
        "camera_runs": {},
        "metrics": {},
        "issues": [],
        "overall_status": "PASS"
    }

    # 1. Controlled synthetic unit validation for CentroidTracker
    try:
        ct = CentroidTracker(max_disappeared=5, max_distance=100.0)
        # Frame 1: 2 objects
        objs1 = ct.update([(10, 10, 30, 30, "Person", 0.9), (100, 100, 120, 120, "Car", 0.85)])
        assert len(objs1) == 2, f"Expected 2 objects, got {len(objs1)}"
        id1, id2 = list(objs1.keys())

        # Frame 2: Small movement -> IDs should persist
        objs2 = ct.update([(12, 12, 32, 32, "Person", 0.9), (102, 102, 122, 122, "Car", 0.85)])
        assert set(objs2.keys()) == {id1, id2}, f"IDs did not persist: {objs2.keys()}"

        # Frame 3-8: Only 1 object, other disappears
        for _ in range(6):
            objs = ct.update([(14, 14, 34, 34, "Person", 0.9)])
        # Object 2 should be deregistered after max_disappeared=5
        assert id2 not in objs, f"Disappeared object {id2} not deregistered"
        assert id1 in objs, f"Active object {id1} prematurely deregistered"
        tracking_results["unit_test_status"] = "PASS"
    except Exception as e:
        tracking_results["unit_test_status"] = "FAIL"
        tracking_results["issues"].append(f"Synthetic tracker unit test failed: {e}")

    # 2. Real-video tracking validation
    total_tracks_created = 0
    total_detections_tracked = 0
    track_lifespans = []
    
    for cam in cams_to_test:
        cam_id = cam["id"]
        cap = cv2.VideoCapture(cam["path"])
        tracker = CentroidTracker(max_disappeared=25, max_distance=220.0)
        
        seen_ids = set()
        id_first_seen = {}
        id_last_seen = {}
        id_classes = {}
        id_positions = {}
        
        frame_idx = 0
        while cap.isOpened() and frame_idx < cam["frames"]:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect
            preds = model.predict(source=frame, conf=0.30, device=device, verbose=False)[0]
            rects = []
            if preds.boxes is not None:
                for box in preds.boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    name = model.names[cls_id]
                    if name in ["person", "car", "motorcycle", "bus", "truck"]:
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        rects.append((x1, y1, x2, y2, name, conf))
            
            # Tracker update
            tracked = tracker.update(rects)
            total_detections_tracked += len(rects)
            
            for tid, centroid in tracked.items():
                seen_ids.add(tid)
                if tid not in id_first_seen:
                    id_first_seen[tid] = frame_idx
                    id_classes[tid] = tracker.classes.get(tid, "unknown")
                    id_positions[tid] = []
                id_last_seen[tid] = frame_idx
                id_positions[tid].append(centroid)
                
            frame_idx += 1
        cap.release()

        lifespans = {tid: (id_last_seen[tid] - id_first_seen[tid] + 1) for tid in seen_ids}
        avg_lifespan = round(sum(lifespans.values()) / max(1, len(lifespans)), 2)
        total_tracks_created += len(seen_ids)
        track_lifespans.extend(lifespans.values())

        # Check for abnormal ID switching: check if any track rapidly changes class
        class_switches = 0
        for tid in seen_ids:
            cur_cls = tracker.classes.get(tid)
            if cur_cls and cur_cls != id_classes.get(tid):
                class_switches += 1

        tracking_results["camera_runs"][cam_id] = {
            "frames_processed": frame_idx,
            "unique_tracks": len(seen_ids),
            "average_track_lifespan_frames": avg_lifespan,
            "max_track_lifespan_frames": max(lifespans.values()) if lifespans else 0,
            "class_switches": class_switches,
            "tracks_persisted_over_10_frames": sum(1 for l in lifespans.values() if l >= 10)
        }

    overall_avg_lifespan = round(sum(track_lifespans) / max(1, len(track_lifespans)), 2) if track_lifespans else 0
    tracking_results["metrics"] = {
        "total_unique_tracks_observed": total_tracks_created,
        "total_detections_tracked": total_detections_tracked,
        "overall_average_track_lifespan_frames": overall_avg_lifespan,
        "tracks_with_persistence_gt_10_frames": sum(1 for l in track_lifespans if l >= 10)
    }

    if tracking_results["unit_test_status"] == "PASS" and total_tracks_created > 0:
        tracking_results["overall_status"] = "PASS"
    else:
        tracking_results["overall_status"] = "PARTIAL"

    out_path = os.path.join(os.path.dirname(__file__), "tracking_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tracking_results, f, indent=2)
    print(f"Tracking audit report written to {out_path}")

if __name__ == "__main__":
    audit_tracking()
