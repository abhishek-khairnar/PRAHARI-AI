import time
import math
import numpy as np
from collections import deque
import cv2

print("=" * 60)
print("UNIT TESTS: LOITERING & NIGHT DETECTION LOGIC")
print("=" * 60)

# Test 1: Loitering Logic Verification
print("\n[TEST 1] Loitering / Suspicious Activity Logic:")
LOITERING_TIME_SECONDS = 5.0
LOITERING_RADIUS_PIXELS = 60.0

loitering_state = {}
loiter_alerts = []

# Simulate Person A (Loitering: stays around 200, 200 for 6 seconds)
# Simulate Person B (Walking: moves from 500, 100 to 500, 700)
timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.2, 6.0]

for t in timestamps:
    # Person A
    cx_a = 200 + int(5 * math.sin(t))
    cy_a = 200 + int(5 * math.cos(t))
    
    # Person B
    cx_b = 500
    cy_b = 100 + int(100 * t)
    
    tracked = {
        1: {"class": "Person", "centroid": (cx_a, cy_a)},
        2: {"class": "Person", "centroid": (cx_b, cy_b)}
    }
    
    for oid, obj in tracked.items():
        cx, cy = obj["centroid"]
        if oid not in loitering_state:
            loitering_state[oid] = {"first_seen": t, "anchor": (cx, cy), "alerted": False}
            continue
        
        st = loitering_state[oid]
        ax, ay = st["anchor"]
        disp = math.hypot(cx - ax, cy - ay)
        
        if disp > LOITERING_RADIUS_PIXELS:
            st["anchor"] = (cx, cy)
            st["first_seen"] = t
            st["alerted"] = False
            continue
        
        dwell = t - st["first_seen"]
        if dwell >= LOITERING_TIME_SECONDS and not st["alerted"]:
            st["alerted"] = True
            loiter_alerts.append((oid, t, dwell, disp))

print(f"  Loitering alerts triggered: {len(loiter_alerts)}")
for alert in loiter_alerts:
    print(f"  -> Object ID #{alert[0]} triggered LOITERING at t={alert[1]}s (dwell={alert[2]:.1f}s, displacement={alert[3]:.1f}px)")

assert len(loiter_alerts) == 1, "Expected exactly 1 loitering alert for Person A"
assert loiter_alerts[0][0] == 1, "Expected Person A (ID #1) to trigger loitering"
print("  [PASS] Loitering test passed successfully (Person A detected, walking Person B ignored).")

# Test 2: Night Detection Logic Verification
print("\n[TEST 2] Night Mode & Nocturnal Movement Logic:")
NIGHT_BRIGHTNESS_THRESHOLD = 45.0
NIGHT_MOVEMENT_THRESHOLD_PIXELS = 15.0

# 2a. Bright Day Frame
bright_frame = np.full((100, 100, 3), 140, dtype=np.uint8)
gray_bright = cv2.cvtColor(bright_frame, cv2.COLOR_BGR2GRAY)
day_brightness = float(np.mean(gray_bright))
is_night_day = day_brightness <= NIGHT_BRIGHTNESS_THRESHOLD
print(f"  Day Frame Brightness:   {day_brightness:.1f} (Night Mode Active: {is_night_day})")
assert not is_night_day, "Day frame should NOT trigger night mode"

# 2b. Dark Night Frame
dark_frame = np.full((100, 100, 3), 20, dtype=np.uint8)
gray_dark = cv2.cvtColor(dark_frame, cv2.COLOR_BGR2GRAY)
night_brightness = float(np.mean(gray_dark))
is_night_night = night_brightness <= NIGHT_BRIGHTNESS_THRESHOLD
print(f"  Dark Frame Brightness:  {night_brightness:.1f} (Night Mode Active: {is_night_night})")
assert is_night_night, "Dark frame SHOULD trigger night mode"

# 2c. Nocturnal Movement Trigger
night_alerts = []
# Object moving 25px in night mode
movement_1 = math.hypot(125 - 100, 100 - 100)
if is_night_night and movement_1 >= NIGHT_MOVEMENT_THRESHOLD_PIXELS:
    night_alerts.append(("Object #1", movement_1))

# Static object moving 2px in night mode
movement_2 = math.hypot(102 - 100, 100 - 100)
if is_night_night and movement_2 >= NIGHT_MOVEMENT_THRESHOLD_PIXELS:
    night_alerts.append(("Object #2", movement_2))

print(f"  Night movement alerts:  {len(night_alerts)}")
assert len(night_alerts) == 1, "Expected 1 nocturnal movement alert for moving object"
print("  [PASS] Night mode test passed successfully (Dark frame activated, moving object alerted, static ignored).")
print("\nAll unit tests PASSED!")
