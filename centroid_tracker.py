import math
from collections import OrderedDict, deque


def compute_iou(boxA: tuple, boxB: tuple) -> float:
    """Calculates Intersection Over Union (IoU) between two bounding boxes (x1, y1, x2, y2)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = max(1, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(1, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou


class CentroidTracker:
    def __init__(self, max_disappeared: int = 25, max_distance: float = 220.0):
        # Stores next available unique object ID
        self.next_object_id = 1
        
        # Metadata dicts keyed by object_id
        self.objects = OrderedDict()          # object_id -> (cx, cy)
        self.prev_objects = OrderedDict()     # object_id -> (cx, cy)
        self.disappeared = OrderedDict()      # object_id -> frame_count
        self.hits = OrderedDict()             # object_id -> consecutive_detection_count
        self.classes = OrderedDict()          # object_id -> class_name
        self.confidences = OrderedDict()      # object_id -> conf
        self.bboxes = OrderedDict()           # object_id -> (x1, y1, x2, y2)
        self.trajectories = OrderedDict()     # object_id -> deque of (cx, cy) maxlen 15
        self.crossed_fence = OrderedDict()    # object_id -> bool
        self.crossing_direction = OrderedDict() # object_id -> "IN" / "OUT" / None
        self.fence_sides = OrderedDict()      # object_id -> -1 (above) / 1 (below)
        
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def reset(self, reset_counter: bool = True):
        """Resets all active tracking state when stream loops or disconnects."""
        self.objects.clear()
        self.prev_objects.clear()
        self.disappeared.clear()
        self.hits.clear()
        self.classes.clear()
        self.confidences.clear()
        self.bboxes.clear()
        self.trajectories.clear()
        self.crossed_fence.clear()
        self.crossing_direction.clear()
        self.fence_sides.clear()
        if reset_counter:
            self.next_object_id = 1

    def register(self, centroid: tuple, bbox: tuple, class_name: str, confidence: float) -> int:
        """Registers a new object with a unique ID."""
        object_id = self.next_object_id
        self.objects[object_id] = centroid
        self.prev_objects[object_id] = centroid
        self.disappeared[object_id] = 0
        self.hits[object_id] = 1
        self.classes[object_id] = class_name
        self.confidences[object_id] = confidence
        self.bboxes[object_id] = bbox
        self.trajectories[object_id] = deque([centroid], maxlen=15)
        self.crossed_fence[object_id] = False
        self.crossing_direction[object_id] = None
        self.fence_sides[object_id] = None
        
        self.next_object_id += 1
        return object_id

    def deregister(self, object_id: int):
        """Deregisters an object that has left the frame or disappeared."""
        for d in (
            self.objects, self.prev_objects, self.disappeared, self.hits,
            self.classes, self.confidences, self.bboxes, self.trajectories,
            self.crossed_fence, self.crossing_direction, self.fence_sides
        ):
            if object_id in d:
                del d[object_id]

    def update(self, rects_and_meta: list) -> dict:
        """
        Updates object positions using input list of tuples:
        [(x1, y1, x2, y2, class_name, confidence), ...]
        Returns active tracked objects dictionary.
        """
        # If no detections in current frame, increment disappeared counter for all active objects
        if len(rects_and_meta) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self._get_active_objects()

        # Compute centroids for input detections
        input_centroids = []
        for (x1, y1, x2, y2, cls_name, conf) in rects_and_meta:
            cx = int((x1 + x2) / 2.0)
            cy = int((y1 + y2) / 2.0)
            input_centroids.append((cx, cy))

        # If currently tracking no objects, register all input centroids
        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                (x1, y1, x2, y2, cls_name, conf) = rects_and_meta[i]
                self.register(input_centroids[i], (x1, y1, x2, y2), cls_name, conf)
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())
            object_bboxes = list(self.bboxes.values())
            object_classes = list(self.classes.values())

            # Compute combined matching cost: IoU Overlap + Centroid Distance + Class Consistency
            match_candidates = []
            for r in range(len(object_centroids)):
                oc = object_centroids[r]
                ob = object_bboxes[r]
                o_cls = object_classes[r]
                ob_w = ob[2] - ob[0]
                ob_h = ob[3] - ob[1]
                dyn_max_dist = max(self.max_distance, max(ob_w, ob_h) * 1.5)

                for c in range(len(input_centroids)):
                    ic = input_centroids[c]
                    ib = rects_and_meta[c][:4]
                    i_cls = rects_and_meta[c][4]

                    # Euclidean centroid distance
                    dist = math.hypot(oc[0] - ic[0], oc[1] - ic[1])
                    
                    # Bounding box IoU
                    iou = compute_iou(ob, ib)
                    
                    # Reject candidate only if distance is excessively large AND no bounding box overlap
                    if dist > dyn_max_dist and iou < 0.05:
                        continue

                    # Combined cost: IoU is given high priority when bounding boxes overlap
                    norm_dist = min(1.0, dist / dyn_max_dist)
                    if iou >= 0.20:
                        cost = (0.25 * norm_dist) + (0.75 * (1.0 - iou))
                    else:
                        cost = (0.60 * norm_dist) + (0.40 * (1.0 - iou))
                    
                    # Class consistency check
                    if o_cls != i_cls:
                        is_veh_o = o_cls in ("Car", "Bus", "Truck", "Motorcycle", "Vehicle")
                        is_veh_i = i_cls in ("Car", "Bus", "Truck", "Motorcycle", "Vehicle")
                        if not (is_veh_o and is_veh_i):
                            cost += 0.35

                    match_candidates.append((cost, dist, r, c))

            # Sort candidate matches by cost ascending
            match_candidates.sort(key=lambda x: x[0])

            used_rows = set()
            used_cols = set()

            for cost, dist, r, c in match_candidates:
                if r in used_rows or c in used_cols:
                    continue

                object_id = object_ids[r]
                # Store previous centroid before updating
                self.prev_objects[object_id] = self.objects[object_id]
                self.objects[object_id] = input_centroids[c]
                
                (x1, y1, x2, y2, cls_name, conf) = rects_and_meta[c]
                self.bboxes[object_id] = (x1, y1, x2, y2)
                self.classes[object_id] = cls_name
                self.confidences[object_id] = conf
                self.disappeared[object_id] = 0
                self.hits[object_id] = self.hits.get(object_id, 0) + 1
                
                if object_id in self.trajectories:
                    self.trajectories[object_id].append(input_centroids[c])
                else:
                    self.trajectories[object_id] = deque([input_centroids[c]], maxlen=15)

                used_rows.add(r)
                used_cols.add(c)

            # Handle unmatched existing objects
            unused_rows = set(range(len(object_centroids))) - used_rows
            for r in unused_rows:
                object_id = object_ids[r]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            # Register new unmatched input centroids
            unused_cols = set(range(len(input_centroids))) - used_cols
            for c in unused_cols:
                (x1, y1, x2, y2, cls_name, conf) = rects_and_meta[c]
                self.register(input_centroids[c], (x1, y1, x2, y2), cls_name, conf)

        return self._get_active_objects()

    def check_intrusion_crossing(self, object_id: int, line_y: int) -> tuple:
        """
        Evaluates genuine centroid crossing of the virtual fence line at line_y.
        Requires hits >= 2 to prevent single-frame spurious detection noise.
        Returns: (is_new_intrusion, direction) where direction is 'IN' (moving down) or 'OUT' (moving up).
        """
        if object_id not in self.objects or object_id not in self.prev_objects:
            return False, None

        (cx, cy) = self.objects[object_id]
        current_side = -1 if cy < line_y else 1
        previous_side = self.fence_sides.get(object_id)

        if previous_side is None:
            self.fence_sides[object_id] = current_side
            return False, None

        if self.hits.get(object_id, 0) < 2:
            return False, None

        (prev_cx, prev_cy) = self.prev_objects[object_id]

        is_new_intrusion = False
        direction = None

        if previous_side != current_side:
            if previous_side == -1 and current_side == 1:
                direction = "IN"   # Moving downwards / crossing into zone
            elif previous_side == 1 and current_side == -1:
                direction = "OUT"  # Moving upwards / crossing out of zone

            self.fence_sides[object_id] = current_side

            # Allow new crossing if direction changed or not yet crossed in this direction
            last_dir = self.crossing_direction.get(object_id)
            if (not self.crossed_fence.get(object_id, False)) or (last_dir != direction):
                self.crossed_fence[object_id] = True
                self.crossing_direction[object_id] = direction
                is_new_intrusion = True

        return is_new_intrusion, (direction or self.crossing_direction.get(object_id, "IN"))

    def _get_active_objects(self) -> dict:
        """Returns dictionary of currently tracked objects."""
        active = {}
        for object_id in self.objects:
            active[object_id] = {
                "centroid": self.objects[object_id],
                "prev_centroid": self.prev_objects[object_id],
                "bbox": self.bboxes[object_id],
                "class": self.classes[object_id],
                "confidence": self.confidences[object_id],
                "disappeared": self.disappeared[object_id],
                "hits": self.hits.get(object_id, 0),
                "direction": self.crossing_direction.get(object_id)
            }
        return active
