import re

def compute_iou(boxA, boxB):
    """
    Computes IoU between boxA (x1, y1, x2, y2) and boxB (x1, y1, x2, y2).
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0, xB - xA)
    inter_h = max(0, yB - yA)
    inter_area = inter_w * inter_h

    areaA = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    areaB = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    union_area = areaA + areaB - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / float(union_area)

def calculate_precision_recall_f1(tp, fp, fn):
    """
    Computes precision, recall, and F1 given true positives, false positives, and false negatives.
    """
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn)
    }

def match_boxes(pred_boxes, gt_boxes, iou_threshold=0.5):
    """
    Greedy bipartite matching between predicted and ground-truth bounding boxes.
    Returns: tp, fp, fn, matched_pairs (list of (pred_idx, gt_idx, iou))
    """
    if not gt_boxes:
        return 0, len(pred_boxes), 0, []
    if not pred_boxes:
        return 0, 0, len(gt_boxes), []

    # Calculate all IoUs
    ious = []
    for p_idx, p_box in enumerate(pred_boxes):
        for g_idx, g_box in enumerate(gt_boxes):
            iou = compute_iou(p_box, g_box)
            if iou >= iou_threshold:
                ious.append((iou, p_idx, g_idx))

    # Sort pairs by descending IoU
    ious.sort(key=lambda x: x[0], reverse=True)

    matched_preds = set()
    matched_gts = set()
    matched_pairs = []

    for iou, p_idx, g_idx in ious:
        if p_idx not in matched_preds and g_idx not in matched_gts:
            matched_preds.add(p_idx)
            matched_gts.add(g_idx)
            matched_pairs.append((p_idx, g_idx, iou))

    tp = len(matched_pairs)
    fp = len(pred_boxes) - tp
    fn = len(gt_boxes) - tp
    return tp, fp, fn, matched_pairs

def compute_count_mae(pred_counts, gt_counts):
    """
    Computes Mean Absolute Error between predicted counts and ground truth counts.
    """
    if not pred_counts or len(pred_counts) != len(gt_counts):
        return 0.0
    total_abs_err = sum(abs(p - g) for p, g in zip(pred_counts, gt_counts))
    return round(total_abs_err / len(pred_counts), 4)

def normalize_plate_string(text):
    """
    Strips non-alphanumeric characters, spaces, and normalizes to uppercase.
    """
    if not text:
        return ""
    clean = re.sub(r'[^A-Za-z0-9]', '', str(text)).upper()
    return clean

def levenshtein_distance(s1, s2):
    """
    Standard Levenshtein edit distance between two strings.
    """
    s1, s2 = str(s1), str(s2)
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[m][n]

def character_accuracy(pred_text, gt_text):
    """
    Computes character-level accuracy normalized by max string length:
    max(0, 1 - (levenshtein / max_len))
    """
    norm_p = normalize_plate_string(pred_text)
    norm_g = normalize_plate_string(gt_text)
    if not norm_g:
        return 1.0 if not norm_p else 0.0
    dist = levenshtein_distance(norm_p, norm_g)
    max_l = max(len(norm_p), len(norm_g))
    if max_l == 0:
        return 1.0
    return round(max(0.0, 1.0 - (dist / float(max_l))), 4)

def exact_match(pred_text, gt_text):
    """
    Boolean exact match on normalized plate strings.
    """
    norm_p = normalize_plate_string(pred_text)
    norm_g = normalize_plate_string(gt_text)
    return bool(norm_p and norm_g and norm_p == norm_g)

def compute_confusion_matrix(classes, y_true, y_pred):
    """
    Computes confusion matrix dictionary for a set of classes.
    """
    matrix = {c_true: {c_pred: 0 for c_pred in classes} for c_true in classes}
    for t, p in zip(y_true, y_pred):
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
    return matrix


# ─────────────────────────────────────────────────────────────────────────────
# Phase A1: Proper Class-Aware 1-to-1 Spatial IoU Matching & Multi-Class Metrics
# ─────────────────────────────────────────────────────────────────────────────

STANDARD_OBJECT_CLASSES = ["person", "car", "motorcycle", "bus", "truck"]


def match_objects_class_aware(
    pred_boxes,
    pred_classes,
    pred_confs=None,
    gt_boxes=None,
    gt_classes=None,
    iou_threshold=0.50,
    target_classes=None
):
    """
    Class-aware greedy 1-to-1 bipartite matching between predicted and ground-truth objects.

    Rules & Invariants:
    1. Class Compatibility: A prediction of class A CANNOT match a ground-truth object of class B.
    2. Spatial Overlap: IoU between prediction and ground-truth must be >= iou_threshold.
    3. One-to-One Matching: Each prediction matches at most one GT; each GT matches at most one prediction.
    4. Deterministic Tie-Breaking: Candidate pairs are sorted primarily by descending confidence,
       then by descending IoU, then by prediction index.
    5. Disjoint Evaluation: Unmatched predictions are False Positives for their predicted class.
       Unmatched ground truths are False Negatives for their ground-truth class.

    Returns: dict with per_class metrics, macro summary, overall summary, matched pairs, unmatched.
    """
    pred_boxes = pred_boxes or []
    pred_classes = [str(c).lower().strip() for c in (pred_classes or [])]
    gt_boxes = gt_boxes or []
    gt_classes = [str(c).lower().strip() for c in (gt_classes or [])]

    if pred_confs is None:
        pred_confs = [1.0] * len(pred_boxes)
    else:
        pred_confs = [float(c) for c in pred_confs]

    if target_classes is None:
        target_classes = sorted(list(set(pred_classes) | set(gt_classes)))
        if not target_classes:
            target_classes = list(STANDARD_OBJECT_CLASSES)
    else:
        target_classes = [str(c).lower().strip() for c in target_classes]

    # Generate valid candidates: class must match AND IoU >= threshold
    candidates = []
    for p_idx, (p_box, p_cls, p_conf) in enumerate(zip(pred_boxes, pred_classes, pred_confs)):
        for g_idx, (g_box, g_cls) in enumerate(zip(gt_boxes, gt_classes)):
            if p_cls == g_cls:
                iou = compute_iou(p_box, g_box)
                if iou >= iou_threshold:
                    # Sort tuple: (p_conf, iou, -p_idx, -g_idx)
                    candidates.append((p_conf, iou, p_idx, g_idx, p_cls))

    # Sort descending by confidence, then IoU, then earlier pred index
    candidates.sort(key=lambda x: (x[0], x[1], -x[2], -x[3]), reverse=True)

    matched_preds = set()
    matched_gts = set()
    matched_pairs = []

    for p_conf, iou, p_idx, g_idx, cls_name in candidates:
        if p_idx not in matched_preds and g_idx not in matched_gts:
            matched_preds.add(p_idx)
            matched_gts.add(g_idx)
            matched_pairs.append({
                "pred_idx": p_idx,
                "gt_idx": g_idx,
                "class": cls_name,
                "iou": round(float(iou), 4),
                "conf": round(float(p_conf), 4),
                "pred_box": pred_boxes[p_idx],
                "gt_box": gt_boxes[g_idx]
            })

    # TPs, FPs, FNs per class
    per_class_tp = {c: 0 for c in target_classes}
    per_class_fp = {c: 0 for c in target_classes}
    per_class_fn = {c: 0 for c in target_classes}
    per_class_gt = {c: 0 for c in target_classes}
    per_class_pred = {c: 0 for c in target_classes}

    # Count GT per class
    for g_idx, g_cls in enumerate(gt_classes):
        if g_cls in per_class_gt:
            per_class_gt[g_cls] += 1

    # Count predictions per class
    for p_idx, p_cls in enumerate(pred_classes):
        if p_cls in per_class_pred:
            per_class_pred[p_cls] += 1

    # TPs from matched pairs
    for m in matched_pairs:
        cls_name = m["class"]
        if cls_name in per_class_tp:
            per_class_tp[cls_name] += 1

    # Unmatched predictions are False Positives
    unmatched_preds = []
    for p_idx, (p_box, p_cls, p_conf) in enumerate(zip(pred_boxes, pred_classes, pred_confs)):
        if p_idx not in matched_preds:
            if p_cls in per_class_fp:
                per_class_fp[p_cls] += 1
            unmatched_preds.append({
                "pred_idx": p_idx,
                "class": p_cls,
                "conf": round(float(p_conf), 4),
                "box": p_box
            })

    # Unmatched ground truth are False Negatives
    unmatched_gts = []
    for g_idx, (g_box, g_cls) in enumerate(zip(gt_boxes, gt_classes)):
        if g_idx not in matched_gts:
            if g_cls in per_class_fn:
                per_class_fn[g_cls] += 1
            unmatched_gts.append({
                "gt_idx": g_idx,
                "class": g_cls,
                "box": g_box
            })

    # Calculate per-class metrics
    per_class_metrics = {}
    for c in target_classes:
        tp = per_class_tp[c]
        fp = per_class_fp[c]
        fn = per_class_fn[c]
        m = calculate_precision_recall_f1(tp, fp, fn)
        m["gt_count"] = per_class_gt[c]
        m["pred_count"] = per_class_pred[c]
        per_class_metrics[c] = m

    # Macro averages across evaluated classes with non-zero support (or all classes)
    classes_with_gt = [c for c in target_classes if per_class_gt[c] > 0]
    eval_classes_for_macro = classes_with_gt if classes_with_gt else target_classes

    if eval_classes_for_macro:
        macro_p = sum(per_class_metrics[c]["precision"] for c in eval_classes_for_macro) / len(eval_classes_for_macro)
        macro_r = sum(per_class_metrics[c]["recall"] for c in eval_classes_for_macro) / len(eval_classes_for_macro)
        macro_f1 = (2 * macro_p * macro_r) / (macro_p + macro_r) if (macro_p + macro_r) > 0 else 0.0
    else:
        macro_p, macro_r, macro_f1 = 0.0, 0.0, 0.0

    # Overall totals
    total_tp = sum(per_class_tp.values())
    total_fp = sum(per_class_fp.values())
    total_fn = sum(per_class_fn.values())
    total_gt = len(gt_boxes)
    total_pred = len(pred_boxes)
    overall_m = calculate_precision_recall_f1(total_tp, total_fp, total_fn)
    overall_m["total_gt"] = total_gt
    overall_m["total_pred"] = total_pred
    overall_m["count_mae"] = abs(total_pred - total_gt)

    return {
        "per_class": per_class_metrics,
        "macro": {
            "precision": round(macro_p, 4),
            "recall": round(macro_r, 4),
            "f1": round(macro_f1, 4),
            "evaluated_classes": eval_classes_for_macro
        },
        "overall": overall_m,
        "matched_pairs": matched_pairs,
        "unmatched_predictions": unmatched_preds,
        "unmatched_ground_truth": unmatched_gts,
        "iou_threshold": iou_threshold
    }


def compute_ap_from_pr(recalls, precisions):
    """
    Computes Average Precision (AP) from arrays/lists of recall and precision points
    using standard 11-point interpolation or all-point trapezoidal area (VOC/COCO standard).
    """
    if not recalls or not precisions:
        return 0.0

    # Append sentinel values
    mrec = [0.0] + list(recalls) + [1.0]
    mpre = [0.0] + list(precisions) + [0.0]

    # Compute maximum precision envelope backwards
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])

    # Integrate area under envelope curve
    ap = 0.0
    for i in range(len(mrec) - 1):
        if mrec[i + 1] != mrec[i]:
            ap += (mrec[i + 1] - mrec[i]) * mpre[i + 1]

    return round(float(ap), 4)

