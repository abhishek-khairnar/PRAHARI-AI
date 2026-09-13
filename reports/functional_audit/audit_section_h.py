import os
import sys
import json
import cv2
import numpy as np

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, base_dir)

from rtsp_stream import (
    NIGHT_DETECTION_ENABLED,
    NIGHT_ENTER_THRESHOLD,
    NIGHT_EXIT_THRESHOLD,
    NIGHT_CONFIRM_FRAMES
)

def audit_night_mode():
    config = {
        "NIGHT_DETECTION_ENABLED": NIGHT_DETECTION_ENABLED,
        "NIGHT_ENTER_THRESHOLD": NIGHT_ENTER_THRESHOLD,
        "NIGHT_EXIT_THRESHOLD": NIGHT_EXIT_THRESHOLD,
        "NIGHT_CONFIRM_FRAMES": NIGHT_CONFIRM_FRAMES
    }

    # Measure brightness across CAM-01 (Day) and CAM-02 (Night)
    videos = [
        {"id": "CAM-01", "name": "Border Post Alpha (Day)", "path": os.path.join(base_dir, "demo_videos/border_demo.mp4")},
        {"id": "CAM-02", "name": "Night Surveillance Bravo (Night)", "path": os.path.join(base_dir, "demo_videos/night_demo.mp4")},
    ]

    camera_measurements = {}

    for v in videos:
        cid = v["id"]
        cap = cv2.VideoCapture(v["path"])
        brightness_vals = []
        state_history = []
        is_night = False
        
        frames_read = 0
        entered_night_count = 0
        exited_day_count = 0
        night_frames_count = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Compute luminance as in RTSPStreamReader._process_frame_ai:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_thumb = cv2.resize(gray, (64, 36))
            mean_b = float(cv2.mean(gray_thumb)[0])
            med_b = float(np.median(gray_thumb))
            effective_brightness = round(0.5 * mean_b + 0.5 * med_b, 1)
            brightness_vals.append(effective_brightness)

            state_history.append(effective_brightness)
            if len(state_history) > NIGHT_CONFIRM_FRAMES:
                state_history.pop(0)

            if len(state_history) >= 15:
                avg_b = sum(state_history) / len(state_history)
                if not is_night and avg_b <= NIGHT_ENTER_THRESHOLD:
                    is_night = True
                    entered_night_count += 1
                elif is_night and avg_b >= NIGHT_EXIT_THRESHOLD:
                    is_night = False
                    exited_day_count += 1

            if is_night:
                night_frames_count += 1
            frames_read += 1
        cap.release()

        avg_measured = round(sum(brightness_vals) / max(1, len(brightness_vals)), 2)
        min_measured = min(brightness_vals) if brightness_vals else 0
        max_measured = max(brightness_vals) if brightness_vals else 0

        camera_measurements[cid] = {
            "name": v["name"],
            "frames_measured": frames_read,
            "average_brightness": avg_measured,
            "min_brightness": min_measured,
            "max_brightness": max_measured,
            "night_frames_count": night_frames_count,
            "entered_night_transitions": entered_night_count,
            "exited_day_transitions": exited_day_count,
            "final_night_mode": is_night,
            "expected_activation": (cid == "CAM-02"),
            "activated_night_mode": (night_frames_count > 0),
            "state_match": (night_frames_count > 0 if cid == "CAM-02" else night_frames_count == 0)
        }

    # Test Hysteresis transition behavior with synthetic steps
    # Day (120) -> Darkness (60) -> Transition to NIGHT after confirmation -> Twilight (90) -> Stays NIGHT -> Full daylight (110) -> Exits to DAY
    hist = []
    mode = False
    transition_trace = []
    
    # 20 frames of day (120)
    for _ in range(20):
        hist.append(120.0)
        if len(hist) > NIGHT_CONFIRM_FRAMES: hist.pop(0)
        avg_b = sum(hist) / len(hist)
        if not mode and avg_b <= NIGHT_ENTER_THRESHOLD: mode = True
        elif mode and avg_b >= NIGHT_EXIT_THRESHOLD: mode = False
    transition_trace.append(("Initial Day", mode, round(avg_b, 1)))

    # 25 frames of night (40)
    for _ in range(25):
        hist.append(40.0)
        if len(hist) > NIGHT_CONFIRM_FRAMES: hist.pop(0)
        avg_b = sum(hist) / len(hist)
        if not mode and avg_b <= NIGHT_ENTER_THRESHOLD: mode = True
        elif mode and avg_b >= NIGHT_EXIT_THRESHOLD: mode = False
    transition_trace.append(("Darkness Entered", mode, round(avg_b, 1)))

    # 25 frames of twilight (90) - between 85 and 98 -> should STAY Night (hysteresis)
    for _ in range(25):
        hist.append(90.0)
        if len(hist) > NIGHT_CONFIRM_FRAMES: hist.pop(0)
        avg_b = sum(hist) / len(hist)
        if not mode and avg_b <= NIGHT_ENTER_THRESHOLD: mode = True
        elif mode and avg_b >= NIGHT_EXIT_THRESHOLD: mode = False
    transition_trace.append(("Twilight Hysteresis Hold", mode, round(avg_b, 1)))

    # 25 frames of bright day (130) -> should exit to Day
    for _ in range(25):
        hist.append(130.0)
        if len(hist) > NIGHT_CONFIRM_FRAMES: hist.pop(0)
        avg_b = sum(hist) / len(hist)
        if not mode and avg_b <= NIGHT_ENTER_THRESHOLD: mode = True
        elif mode and avg_b >= NIGHT_EXIT_THRESHOLD: mode = False
    transition_trace.append(("Full Day Restored", mode, round(avg_b, 1)))

    hysteresis_verified = (
        transition_trace[0][1] is False and # Initial Day
        transition_trace[1][1] is True and  # Darkness Entered
        transition_trace[2][1] is True and  # Twilight Hold (Hysteresis working)
        transition_trace[3][1] is False     # Day restored
    )

    all_matches = all(m["state_match"] for m in camera_measurements.values())

    result = {
        "configuration": config,
        "camera_measurements": camera_measurements,
        "hysteresis_test": {
            "verified": hysteresis_verified,
            "trace": [
                {"phase": t[0], "night_mode_active": t[1], "effective_avg_luminance": t[2]}
                for t in transition_trace
            ]
        },
        "overall_status": "PASS" if (all_matches and hysteresis_verified) else "FAIL"
    }

    out_path = os.path.join(os.path.dirname(__file__), "night_mode_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Night Mode audit report written to {out_path}")

if __name__ == "__main__":
    audit_night_mode()
