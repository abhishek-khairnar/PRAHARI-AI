import os
import json
import cv2
import torch
from ultralytics import YOLO

def test_cameras_and_detection():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    cameras = [
        {"id": "CAM-01", "name": "Border Post Alpha", "rel_path": "demo_videos/border_demo.mp4"},
        {"id": "CAM-02", "name": "Night Surveillance Bravo", "rel_path": "demo_videos/night_demo.mp4"},
        {"id": "CAM-03", "name": "Perimeter Activity Charlie", "rel_path": "demo_videos/activity-demo.mp4"},
        {"id": "CAM-04", "name": "Urban Facility Delta", "rel_path": "demo_videos/cctv_demo.mp4"},
    ]

    camera_results = {}
    
    # 1. Test Camera Inputs
    for cam in cameras:
        cam_id = cam["id"]
        full_path = os.path.join(base_dir, cam["rel_path"])
        res = {
            "id": cam_id,
            "name": cam["name"],
            "path": full_path,
            "exists": os.path.exists(full_path),
            "file_size": os.path.getsize(full_path) if os.path.exists(full_path) else 0,
            "opens": False,
            "fps": None,
            "width": None,
            "height": None,
            "frame_count": None,
            "duration_sec": None,
            "decoded_sample_frames": 0,
            "status": "FAIL",
            "errors": []
        }
        
        if not res["exists"]:
            res["errors"].append("File does not exist")
            camera_results[cam_id] = res
            continue

        cap = cv2.VideoCapture(full_path)
        if not cap.isOpened():
            res["errors"].append("cv2.VideoCapture failed to open")
            camera_results[cam_id] = res
            continue
        
        res["opens"] = True
        res["fps"] = round(cap.get(cv2.CAP_PROP_FPS), 2)
        res["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        res["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        res["frame_count"] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if res["fps"] > 0:
            res["duration_sec"] = round(res["frame_count"] / res["fps"], 2)
            
        # Decode sample frames (first 30 frames)
        decoded = 0
        for _ in range(30):
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            decoded += 1
        cap.release()

        res["decoded_sample_frames"] = decoded
        if decoded >= 30 and res["width"] > 0 and res["height"] > 0:
            res["status"] = "PASS"
        else:
            res["status"] = "PARTIAL" if decoded > 0 else "FAIL"
            res["errors"].append(f"Decoded {decoded}/30 frames")

        camera_results[cam_id] = res

    # Save camera_test.json
    cam_out_path = os.path.join(os.path.dirname(__file__), "camera_test.json")
    with open(cam_out_path, "w", encoding="utf-8") as f:
        json.dump(camera_results, f, indent=2)
    print(f"Camera test result written to {cam_out_path}")

    # 2. Test Object Detection across all 4 cameras
    model_path = os.path.join(base_dir, "weights", "yolov8n.pt")
    model = YOLO(model_path)
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    
    target_classes = {
        "person": {"class_id": 0, "detected_count": 0, "max_conf": 0.0, "sample_bbox": None, "sample_cam": None},
        "car": {"class_id": 2, "detected_count": 0, "max_conf": 0.0, "sample_bbox": None, "sample_cam": None},
        "motorcycle": {"class_id": 3, "detected_count": 0, "max_conf": 0.0, "sample_bbox": None, "sample_cam": None},
        "truck": {"class_id": 7, "detected_count": 0, "max_conf": 0.0, "sample_bbox": None, "sample_cam": None},
        "bus": {"class_id": 5, "detected_count": 0, "max_conf": 0.0, "sample_bbox": None, "sample_cam": None},
    }

    per_camera_detection_summary = {}

    for cam in cameras:
        cam_id = cam["id"]
        full_path = os.path.join(base_dir, cam["rel_path"])
        cap = cv2.VideoCapture(full_path)
        frames_tested = 0
        cam_detections = {cls_name: 0 for cls_name in target_classes}
        
        # Test 100 frames per camera at step of 3 frames to cover time range
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_indices = set(range(0, min(total_f, 300), 3))
        
        frame_idx = 0
        while cap.isOpened() and frames_tested < len(sample_indices):
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx in sample_indices:
                frames_tested += 1
                # Run production-style inference (conf=0.25)
                preds = model.predict(source=frame, conf=0.25, device=device, verbose=False)[0]
                if preds.boxes is not None and len(preds.boxes) > 0:
                    for box in preds.boxes:
                        cid = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        xyxy = [round(float(coord), 1) for coord in box.xyxy[0].tolist()]
                        for cls_name, info in target_classes.items():
                            if cid == info["class_id"]:
                                cam_detections[cls_name] += 1
                                info["detected_count"] += 1
                                if conf > info["max_conf"]:
                                    info["max_conf"] = round(conf, 3)
                                    info["sample_bbox"] = xyxy
                                    info["sample_cam"] = cam_id
            frame_idx += 1
        cap.release()
        per_camera_detection_summary[cam_id] = {
            "frames_tested": frames_tested,
            "detections": cam_detections
        }

    # Evaluate results for each target class
    detection_results = {
        "classes_tested": {},
        "per_camera_summary": per_camera_detection_summary,
        "overall_status": "PASS"
    }

    for cls_name, info in target_classes.items():
        detected = info["detected_count"] > 0
        detection_results["classes_tested"][cls_name] = {
            "class_id": info["class_id"],
            "detected_count": info["detected_count"],
            "max_confidence": info["max_conf"],
            "sample_bbox": info["sample_bbox"],
            "sample_camera": info["sample_cam"],
            "status": "PASS" if detected else "NOT DETECTED IN DEMO VIDEOS"
        }

    det_out_path = os.path.join(os.path.dirname(__file__), "detection_test.json")
    with open(det_out_path, "w", encoding="utf-8") as f:
        json.dump(detection_results, f, indent=2)
    print(f"Detection test result written to {det_out_path}")

if __name__ == "__main__":
    test_cameras_and_detection()
