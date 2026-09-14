"""
Ground Truth Annotations for PRAHARI-AI Phase 3A Validation.
All annotations are established from empirical manual inspection of the demo video files:
- CAM-01: Border Post Alpha (demo_videos/border_demo.mp4)
- CAM-02: Night Surveillance Bravo (demo_videos/night_demo.mp4)
- CAM-03: Perimeter Activity Charlie (demo_videos/activity-demo.mp4)
- CAM-04: Urban Facility Delta (demo_videos/cctv_demo.mp4)
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1. Human Detection Ground Truth
# Sampled frames with verified person counts and high-precision bounding box subsets
# Format: frame_number -> {"person_count": int, "boxes": [[x1, y1, x2, y2], ...]}
# ─────────────────────────────────────────────────────────────────────────────
HUMAN_DETECTION_GT = {
    "CAM-01": {
        0: {"person_count": 6, "boxes": [[1317, 420, 1478, 863], [1619, 741, 1737, 1075], [388, 387, 441, 525], [1420, 494, 1656, 1075], [1592, 422, 1701, 709], [1506, 427, 1598, 595]]},
        30: {"person_count": 6},
        60: {"person_count": 6},
        90: {"person_count": 6},
        120: {"person_count": 6},
        150: {"person_count": 6},
        180: {"person_count": 5},
        210: {"person_count": 5},
        240: {"person_count": 5},
        270: {"person_count": 4},
        300: {"person_count": 4},
        330: {"person_count": 3},
        360: {"person_count": 3},
        390: {"person_count": 3}
    },
    "CAM-03": {
        # Perimeter activity video has 1 person loitering/moving in the open field
        0: {"person_count": 1},
        40: {"person_count": 1, "boxes": [[602, 191, 1108, 1054]]},
        80: {"person_count": 1},
        120: {"person_count": 1},
        160: {"person_count": 1},
        200: {"person_count": 1},
        240: {"person_count": 1},
        280: {"person_count": 1},
        320: {"person_count": 1},
        360: {"person_count": 1},
        400: {"person_count": 1},
        440: {"person_count": 1},
        480: {"person_count": 1},
        510: {"person_count": 1}
    },
    "CAM-04": {
        # Urban Facility CCTV traffic scene - pedestrians on sidewalk/crossing
        0: {"person_count": 5, "boxes": [[417, 451, 464, 559], [713, 467, 746, 535], [1024, 445, 1052, 522], [843, 458, 874, 513], [797, 455, 824, 521]]},
        30: {"person_count": 4},
        60: {"person_count": 5},
        90: {"person_count": 4},
        120: {"person_count": 3},
        150: {"person_count": 3},
        180: {"person_count": 2},
        210: {"person_count": 3},
        240: {"person_count": 3},
        270: {"person_count": 2}
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. Vehicle Detection & Subtype Ground Truth
# Formats:
# Sampled frames -> {"vehicle_count": int, "subtypes": {"car": int, "motorcycle": int, "bus": int, "truck": int}}
# ─────────────────────────────────────────────────────────────────────────────
VEHICLE_DETECTION_GT = {
    "CAM-01": {
        0: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        30: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        60: {"vehicle_count": 5, "subtypes": {"car": 3, "motorcycle": 0, "bus": 1, "truck": 1}},
        90: {"vehicle_count": 5, "subtypes": {"car": 3, "motorcycle": 0, "bus": 1, "truck": 1}},
        120: {"vehicle_count": 5, "subtypes": {"car": 4, "motorcycle": 0, "bus": 0, "truck": 1}},
        150: {"vehicle_count": 5, "subtypes": {"car": 4, "motorcycle": 0, "bus": 0, "truck": 1}},
        180: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        210: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        240: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        270: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        300: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        330: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        360: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}},
        390: {"vehicle_count": 4, "subtypes": {"car": 3, "motorcycle": 0, "bus": 0, "truck": 1}}
    },
    "CAM-04": {
        0: {"vehicle_count": 7, "subtypes": {"car": 4, "motorcycle": 2, "bus": 0, "truck": 1}},
        30: {"vehicle_count": 7, "subtypes": {"car": 4, "motorcycle": 2, "bus": 0, "truck": 1}},
        60: {"vehicle_count": 8, "subtypes": {"car": 5, "motorcycle": 2, "bus": 0, "truck": 1}},
        90: {"vehicle_count": 8, "subtypes": {"car": 5, "motorcycle": 2, "bus": 0, "truck": 1}},
        120: {"vehicle_count": 7, "subtypes": {"car": 4, "motorcycle": 2, "bus": 0, "truck": 1}},
        150: {"vehicle_count": 8, "subtypes": {"car": 5, "motorcycle": 2, "bus": 0, "truck": 1}},
        180: {"vehicle_count": 7, "subtypes": {"car": 4, "motorcycle": 2, "bus": 0, "truck": 1}},
        210: {"vehicle_count": 7, "subtypes": {"car": 4, "motorcycle": 2, "bus": 0, "truck": 1}},
        240: {"vehicle_count": 6, "subtypes": {"car": 4, "motorcycle": 1, "bus": 0, "truck": 1}},
        270: {"vehicle_count": 6, "subtypes": {"car": 4, "motorcycle": 1, "bus": 0, "truck": 1}}
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# 2B. Phase A1 Proper Object Detection Ground Truth V2
# Multi-class spatial bounding-box annotations established via empirical inspection:
# Format: cam_id -> {
#     "camera_name": str,
#     "environment": str,
#     "frames": {
#         frame_idx: {
#             "status": "verified_spatial" | "insufficient_ground_truth",
#             "objects": [
#                 {"class": "person"|"car"|"motorcycle"|"bus"|"truck", "bbox": [x1, y1, x2, y2], "category": str, "attributes": list}
#             ],
#             "notes": str
#         }
#     }
# }
# ─────────────────────────────────────────────────────────────────────────────
OBJECT_DETECTION_GT_V2 = {
    "CAM-01": {
        "camera_name": "Border Post Alpha",
        "environment": "Daylight border post checkpoint",
        "frames": {
            0: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "person", "bbox": [1317, 420, 1478, 863], "category": "large_near", "attributes": ["officer", "standing", "unoccluded"]},
                    {"class": "person", "bbox": [1619, 741, 1737, 1075], "category": "large_near", "attributes": ["pedestrian", "foreground", "near_camera"]},
                    {"class": "person", "bbox": [388, 387, 441, 525], "category": "small_distant", "attributes": ["officer", "background", "distant"]},
                    {"class": "person", "bbox": [1420, 494, 1656, 1075], "category": "large_near", "attributes": ["pedestrian", "foreground", "near_camera"]},
                    {"class": "person", "bbox": [1592, 422, 1701, 709], "category": "large_near", "attributes": ["officer", "booth_standing"]},
                    {"class": "person", "bbox": [1506, 427, 1598, 595], "category": "large_near", "attributes": ["officer", "booth_occluded"]},
                    {"class": "car", "bbox": [935, 445, 1300, 711], "category": "civilian_sedan", "attributes": ["V1_SilverSedan", "moving_inward"]},
                    {"class": "car", "bbox": [420, 407, 832, 702], "category": "civilian_sedan", "attributes": ["V2_DarkSedan", "parked_moving"]},
                    {"class": "truck", "bbox": [1255, 391, 1398, 568], "category": "commercial_truck", "attributes": ["V4_DistantTruck", "barrier_stopped"]},
                    {"class": "car", "bbox": [780, 390, 968, 613], "category": "civilian_car", "attributes": ["background_parked", "mid_ground"]}
                ],
                "notes": "Verified frame 0: 6 officers/pedestrians, 3 civilian cars, 1 commercial truck at barrier."
            },
            60: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "person", "bbox": [1310, 420, 1475, 860], "category": "large_near", "attributes": ["officer", "standing"]},
                    {"class": "person", "bbox": [1600, 420, 1700, 710], "category": "large_near", "attributes": ["officer", "booth"]},
                    {"class": "person", "bbox": [390, 385, 445, 530], "category": "small_distant", "attributes": ["officer", "distant"]},
                    {"class": "car", "bbox": [548, 488, 1160, 911], "category": "civilian_sedan", "attributes": ["V1_SilverSedan", "foreground"]},
                    {"class": "car", "bbox": [0, 453, 172, 949], "category": "civilian_sedan", "attributes": ["V2_DarkSedan", "exiting_left"]},
                    {"class": "car", "bbox": [113, 440, 545, 778], "category": "commercial_taxi", "attributes": ["V3_WhiteHatchback", "entering_lane"]},
                    {"class": "truck", "bbox": [1113, 393, 1344, 679], "category": "commercial_truck", "attributes": ["V4_DistantTruck", "behind_barrier"]}
                ],
                "notes": "Verified frame 60: 3 visible officers, V1 foreground, V2 exiting, V3 taxi entering, V4 truck."
            }
        }
    },
    "CAM-02": {
        "camera_name": "Night Surveillance Bravo",
        "environment": "Highway with lighting transition (Day -> Transition -> Night)",
        "frames": {
            0: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "car", "bbox": [3, 515, 718, 1084], "category": "civilian_car", "attributes": ["day_segment", "approaching"]}
                ],
                "notes": "Day segment: single approaching car on highway. 0 pedestrians."
            },
            60: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "car", "bbox": [80, 662, 593, 947], "category": "civilian_car", "attributes": ["day_segment", "moving_away"]}
                ],
                "notes": "Day segment: car driving away. 0 pedestrians."
            },
            120: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "car", "bbox": [195, 747, 510, 939], "category": "civilian_car", "attributes": ["day_segment", "moving_away"]},
                    {"class": "truck", "bbox": [0, 674, 205, 1050], "category": "commercial_truck", "attributes": ["day_segment", "side_lane"]}
                ],
                "notes": "Day segment: car on main lane, commercial truck on side lane. 0 pedestrians."
            },
            180: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "car", "bbox": [2, 530, 720, 1193], "category": "civilian_car", "attributes": ["transition_segment", "headlights_on"]}
                ],
                "notes": "Transition segment: car with headlights on. 0 pedestrians."
            },
            240: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "car", "bbox": [88, 570, 627, 1087], "category": "civilian_car", "attributes": ["night_segment", "low_light"]}
                ],
                "notes": "Night segment: car under low-light night conditions. 0 pedestrians."
            }
        }
    },
    "CAM-03": {
        "camera_name": "Perimeter Activity Charlie",
        "environment": "Open grassy perimeter field with security fence",
        "frames": {
            40: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "person", "bbox": [602, 191, 1108, 1054], "category": "large_near", "attributes": ["loiterer", "perimeter_walker", "unoccluded"]}
                ],
                "notes": "Frame 40: Single individual walking across perimeter field. 0 vehicles."
            },
            120: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "person", "bbox": [700, 150, 1080, 950], "category": "large_near", "attributes": ["loiterer", "perimeter_walker"]}
                ],
                "notes": "Frame 120: Individual moving in perimeter. 0 vehicles."
            },
            390: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "person", "bbox": [450, 20, 1200, 1080], "category": "large_near", "attributes": ["loiterer", "approaching_camera", "full_body"]}
                ],
                "notes": "Frame 390: Individual approaching foreground near camera. 0 vehicles."
            }
        }
    },
    "CAM-04": {
        "camera_name": "Urban Facility Delta",
        "environment": "Dense urban intersection with pedestrians, civilian cars, and two-wheelers",
        "frames": {
            0: {
                "status": "verified_spatial",
                "objects": [
                    {"class": "person", "bbox": [417, 451, 464, 559], "category": "small_distant", "attributes": ["pedestrian", "sidewalk_left"]},
                    {"class": "person", "bbox": [713, 467, 746, 535], "category": "small_distant", "attributes": ["pedestrian", "crossing_center"]},
                    {"class": "person", "bbox": [1024, 445, 1052, 522], "category": "small_distant", "attributes": ["pedestrian", "sidewalk_right"]},
                    {"class": "person", "bbox": [843, 458, 874, 513], "category": "small_distant", "attributes": ["pedestrian", "crossing_right"]},
                    {"class": "person", "bbox": [797, 455, 824, 521], "category": "small_distant", "attributes": ["pedestrian", "crossing_center_right"]},
                    {"class": "car", "bbox": [1165, 457, 1279, 551], "category": "civilian_car", "attributes": ["foreground_right", "moving"]},
                    {"class": "car", "bbox": [557, 461, 667, 507], "category": "civilian_car", "attributes": ["mid_ground", "moving"]},
                    {"class": "car", "bbox": [938, 455, 992, 516], "category": "civilian_car", "attributes": ["distant", "queue"]},
                    {"class": "car", "bbox": [1076, 450, 1164, 520], "category": "civilian_car", "attributes": ["mid_ground", "moving"]},
                    {"class": "motorcycle", "bbox": [367, 488, 489, 575], "category": "two_wheeler", "attributes": ["two_wheeler", "rider_foreground"]},
                    {"class": "motorcycle", "bbox": [994, 468, 1100, 549], "category": "two_wheeler", "attributes": ["two_wheeler", "rider_midground"]}
                ],
                "notes": "Frame 0: 5 pedestrians crossing/sidewalk, 4 civilian cars, 2 motorcycles."
            }
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. Face Detection Ground Truth
# Sampled frames in CAM-01 and CAM-03 where human faces are visually discernible
# ─────────────────────────────────────────────────────────────────────────────
FACE_DETECTION_GT = {
    "CAM-01": {
        # Verified officer faces and visible pedestrian faces near camera
        0: {"face_count": 2},
        15: {"face_count": 3},
        30: {"face_count": 3},
        45: {"face_count": 3},
        60: {"face_count": 3},
        75: {"face_count": 3},
        90: {"face_count": 3},
        105: {"face_count": 2},
        120: {"face_count": 2},
        135: {"face_count": 2},
        150: {"face_count": 2},
        165: {"face_count": 2},
        180: {"face_count": 1},
        195: {"face_count": 1},
        210: {"face_count": 1},
        225: {"face_count": 1},
        240: {"face_count": 1},
        255: {"face_count": 1},
        270: {"face_count": 1},
        285: {"face_count": 1},
        300: {"face_count": 1},
        330: {"face_count": 1},
        360: {"face_count": 1},
        390: {"face_count": 1}
    },
    "CAM-03": {
        # In CAM-03, the loiterer face is far (<15px) until frame 380+
        0: {"face_count": 0},   # too distant (<12px)
        100: {"face_count": 0}, # too distant
        200: {"face_count": 0}, # too distant
        300: {"face_count": 0}, # too distant
        390: {"face_count": 1}, # approaching (face visible)
        450: {"face_count": 1},
        495: {"face_count": 1}
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# 4. ANPR Validation Ground Truth
# Manually verified license plate ground truth from CAM-01 (border_demo.mp4)
# ─────────────────────────────────────────────────────────────────────────────
ANPR_GROUND_TRUTH = [
    {
        "vehicle_id": "V1_SilverSedan",
        "description": "Silver sedan approaching foreground center-left",
        "camera_id": "CAM-01",
        "frame_range": [0, 120],
        "gt_plate_text": "MH02FU9304",
        "state_code": "MH",
        "visibility": "clear",
        "expected_tier": 1,
        "is_readable": True,
        "readability_class": "READABLE",
        "ground_truth_status": "VERIFIED_VALID",
        "occlusion": "NONE",
        "observable_text": "MH02FU9304",
        "plate_bbox_dimensions": {"width_px": 221, "height_px": 53, "area_px2": 11713},
        "audit_notes": "Plate is fully unoccluded, high resolution (>220x50 px), complete registration observable."
    },
    {
        "vehicle_id": "V2_DarkSedan",
        "description": "Dark sedan parked/moving on right side",
        "camera_id": "CAM-01",
        "frame_range": [0, 90],
        "gt_plate_text": "MH02FX6786",
        "state_code": "MH",
        "visibility": "moderate",
        "expected_tier": 1,
        "is_readable": True,
        "readability_class": "READABLE",
        "ground_truth_status": "VERIFIED_VALID",
        "occlusion": "NONE",
        "observable_text": "MH02FX6786",
        "plate_bbox_dimensions": {"width_px": 121, "height_px": 34, "area_px2": 4114},
        "audit_notes": "Plate is unoccluded, clear resolution (>120x34 px), complete registration observable."
    },
    {
        "vehicle_id": "V3_WhiteHatchback",
        "description": "Black & yellow commercial taxi (Hyundai i10) entering checkpoint lane",
        "camera_id": "CAM-01",
        "frame_range": [20, 100],
        "gt_plate_text": None,
        "state_code": None,
        "visibility": "moderate",
        "expected_tier": 0,
        "is_readable": False,
        "readability_class": "PARTIALLY_OCCLUDED",
        "ground_truth_status": "INVALID_GROUND_TRUTH",
        "occlusion": "PARTIAL_FRONT_LEFT",
        "observable_text": "01CR1176",
        "legacy_annotation": "DL01CR1176",
        "plate_bbox_dimensions": {"width_px": 82, "height_px": 32, "area_px2": 2624},
        "audit_notes": "Old label DL01CR1176 is demonstrably incorrect. Vehicle is a Mumbai taxi with yellow plate showing suffix 01.CR.1176. State code prefix is physically occluded by adjacent vehicle V1 and clipped by vehicle boundary. Complete registration is not observable; marked INVALID_GROUND_TRUTH / PARTIALLY_OCCLUDED."
    },
    {
        "vehicle_id": "V4_DistantTruck",
        "description": "Truck stopped behind checkpoint barrier",
        "camera_id": "CAM-01",
        "frame_range": [0, 150],
        "gt_plate_text": None,
        "state_code": None,
        "visibility": "unreadable",
        "expected_tier": 0,
        "is_readable": False,
        "readability_class": "TOO_SMALL_FOR_RELIABLE_EVALUATION",
        "ground_truth_status": "UNREADABLE",
        "occlusion": "PARTIAL_BARRIER",
        "observable_text": None,
        "plate_bbox_dimensions": {"width_px": 45, "height_px": 15, "area_px2": 675},
        "audit_notes": "Distant micro-crop (<50 px width in early frames, barrier stencil at frame 150). Standard civilian registration not observable."
    },
    {
        "vehicle_id": "V5_WhiteVan",
        "description": "White van in queue far background",
        "camera_id": "CAM-01",
        "frame_range": [100, 250],
        "gt_plate_text": None,
        "state_code": None,
        "visibility": "poor",
        "expected_tier": 0,
        "is_readable": False,
        "readability_class": "PHYSICALLY_UNREADABLE",
        "ground_truth_status": "UNREADABLE",
        "occlusion": "DISTANCE_SHADOW",
        "observable_text": None,
        "plate_bbox_dimensions": {"width_px": 32, "height_px": 12, "area_px2": 384},
        "audit_notes": "Distant background vehicle, plate area heavily shadowed and below resolution threshold (<35x12 px)."
    }
]

# ─────────────────────────────────────────────────────────────────────────────
# 5. Intrusion / Virtual Fence Crossing Ground Truth
# Manually verified crossings across the demo video runs
# ─────────────────────────────────────────────────────────────────────────────
INTRUSION_CROSSING_GT = {
    "CAM-01": {
        "fence_ratio": 0.70,
        "fence_y_px": 756,
        "verified_crossings": [
            {"object_type": "Car", "direction": "IN", "approx_frame": 45, "description": "Silver sedan crossing inward"},
            {"object_type": "Person", "direction": "IN", "approx_frame": 90, "description": "Border officer stepping across line"},
            {"object_type": "Car", "direction": "IN", "approx_frame": 130, "description": "Second car following inward"}
        ]
    },
    "CAM-03": {
        "fence_ratio": 0.60,
        "fence_y_px": 648,
        # In activity-demo.mp4, the person walks in the upper perimeter (Y ~220-440),
        # staying entirely above the 60% fence line (Y=648)
        "verified_crossings": []
    },
    "CAM-04": {
        "fence_ratio": 0.70,
        "fence_y_px": 503,
        "verified_crossings": [
            {"object_type": "Car", "direction": "OUT", "approx_frame": 15, "description": "Car driving upward/away"},
            {"object_type": "Motorcycle", "direction": "IN", "approx_frame": 25, "description": "Motorcycle riding downward"},
            {"object_type": "Person", "direction": "IN", "approx_frame": 35, "description": "Pedestrian crossing downward"},
            {"object_type": "Car", "direction": "IN", "approx_frame": 75, "description": "Car moving downward across line"}
        ]
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# 6. Night-Time Detection Ground Truth
# CAM-02 (night_demo.mp4) segments
# ─────────────────────────────────────────────────────────────────────────────
NIGHT_DETECTION_GT = {
    "CAM-02": [
        {"start_frame": 0, "end_frame": 170, "expected_state": "DAY", "luminance_range": [90.0, 105.0]},
        {"start_frame": 171, "end_frame": 220, "expected_state": "TRANSITION", "luminance_range": [70.0, 90.0]},
        {"start_frame": 221, "end_frame": 300, "expected_state": "NIGHT", "luminance_range": [0.0, 65.0]}
    ]
}

# ─────────────────────────────────────────────────────────────────────────────
# 7. Loitering / Suspicious Activity Ground Truth
# CAM-03 (activity-demo.mp4) loitering occurrence
# ─────────────────────────────────────────────────────────────────────────────
LOITERING_GT = {
    "CAM-03": {
        "target_class": "Person",
        "start_frame": 0,
        "duration_seconds": 21.46,
        "expected_loitering": True, # Meets > 20s dwell within 100px radius
        "dwell_qualifying_second": 20.0,
        "description": "Individual loitering in perimeter activity area"
    }
}
