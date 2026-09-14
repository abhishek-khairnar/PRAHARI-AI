import os
import re
import logging
import cv2
import numpy as np

# Disable Paddlex remote connectivity check and MKLDNN CPU thread saturation
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["PADDLE_DISABLE_MKLDNN"] = "1"
os.environ["FLAGS_use_mkldnn"] = "0"

logger = logging.getLogger("ANPREngine")

# Known Indian State / Union Territory Codes
INDIAN_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP", "HR",
    "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD",
    "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP", "WB", "AN", "BH"
}


def validate_state_code(state_code: str) -> tuple:
    """
    Validates a 2-letter Indian State/UT code against official standards.
    Returns: (status, resolved_code)
      - ("EXACT", state_code): exactly matches known Indian state/UT code.
      - ("FUZZY", resolved_code): distance 1 to exactly ONE known code.
      - ("INVALID", None): distance 1 to multiple codes (ambiguous) or >1 to all codes.
      - ("MALFORMED", None): code is not 2 uppercase letters.
    """
    if not isinstance(state_code, str) or len(state_code) != 2 or not state_code.isalpha():
        return "MALFORMED", None

    code = state_code.upper()
    if code in INDIAN_STATE_CODES:
        return "EXACT", code

    # Conservative fuzzy recovery: Levenshtein distance 1 only
    # For 2-letter codes, distance 1 means exactly 1 character difference
    candidates = [
        sc for sc in INDIAN_STATE_CODES
        if (sc[0] == code[0]) != (sc[1] == code[1])
    ]
    if len(candidates) == 1:
        return "FUZZY", candidates[0]

    return "INVALID", None


class ANPREngine:
    validate_state_code = staticmethod(validate_state_code)
    def __init__(self, model_path: str = None):
        import torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.ocr = None
        self.easy_reader = None
        self.engine_type = "None"
        self.plate_detector = None
        self.detector_model_name = "None"

        # 1. Initialize YOLO License Plate Detector Model (Local-First Offline Priority)
        try:
            from ultralytics import YOLO

            resolved_path = None
            if model_path and os.path.exists(model_path):
                resolved_path = model_path
            else:
                base_dir = os.path.dirname(__file__)
                candidate_paths = [
                    os.path.join(base_dir, "weights", "license-plate-finetune-v1n.pt"),
                    os.path.join(base_dir, "weights", "license_plate_detector.pt"),
                    os.path.join(base_dir, "weights", "best.pt"),
                    os.path.join(base_dir, "license-plate-finetune-v1n.pt"),
                    os.path.join(base_dir, "license_plate_detector.pt")
                ]
                for cand in candidate_paths:
                    if os.path.exists(cand):
                        resolved_path = cand
                        break

            if resolved_path:
                self.plate_detector = YOLO(resolved_path)
                self.detector_model_name = f"Local ({os.path.basename(resolved_path)})"
                logger.info(f"YOLO License Plate Detector loaded locally from: {resolved_path}")
            else:
                err_msg = (
                    "YOLO License Plate Detector model not found in local weights directory. "
                    "Expected 'weights/license-plate-finetune-v1n.pt' or 'weights/license_plate_detector.pt'. "
                    "Please package the exact model artifact for offline-first operation."
                )
                logger.error(f"[ANPREngine] {err_msg}")
                if os.getenv("ALLOW_REMOTE_MODEL_DOWNLOAD", "0").lower() in ("1", "true"):
                    try:
                        from huggingface_hub import hf_hub_download
                        logger.warning("Attempting remote download fallback as ALLOW_REMOTE_MODEL_DOWNLOAD is enabled...")
                        model_path = hf_hub_download(
                            repo_id="morsetechlab/yolov11-license-plate-detection",
                            filename="license-plate-finetune-v1n.pt"
                        )
                        self.plate_detector = YOLO(model_path)
                        self.detector_model_name = "morsetechlab/yolov11-license-plate-detection (v1n)"
                        logger.info(f"YOLO License Plate Detector loaded via remote download: {self.detector_model_name}")
                    except Exception as re:
                        logger.error(f"Remote fallback download failed: {re}")
        except Exception as e:
            logger.error(f"Failed to initialize YOLO License Plate Detector model: {e}")

        # 2. Try initializing Fast CUDA-Accelerated EasyOCR first
        try:
            import easyocr
            self.easy_reader = easyocr.Reader(['en'], gpu=(self.device == "cuda"))
            self.engine_type = "EasyOCR"
            logger.info(f"EasyOCR Engine successfully loaded on device: {self.device.upper()}!")
        except Exception as e:
            logger.warning(f"EasyOCR not available ({e}). Falling back to PaddleOCR...")
            try:
                from paddleocr import PaddleOCR
                self.ocr = PaddleOCR(lang='en')
                self.engine_type = "PaddleOCR"
                logger.info("PaddleOCR Engine successfully loaded for ANPR fallback!")
            except Exception as ep:
                logger.warning(f"PaddleOCR fallback also failed ({ep}).")

    def extract_plate_crop_from_vehicle(self, vehicle_crop: np.ndarray, conf_threshold: float = 0.15) -> tuple:
        """
        Runs the fine-tuned YOLO license plate detector directly on a cropped vehicle image.
        Expands the detected bounding box outward to prevent cutting characters and validates sharpness/size.
        Returns: (plate_crop_bgr, is_plate_detected, best_conf)
        """
        if vehicle_crop is None or vehicle_crop.size == 0:
            return None, False, 0.0

        vh, vw = vehicle_crop.shape[:2]
        if vw < 40 or vh < 30:
            return None, False, 0.0

        best_conf = 0.0
        if self.plate_detector is not None:
            try:
                # Run lightweight nano plate detector on configured device (CUDA/CPU)
                results = self.plate_detector.predict(
                    source=vehicle_crop,
                    conf=conf_threshold,
                    device=self.device,
                    verbose=False
                )

                best_box = None
                if results and len(results) > 0 and results[0].boxes and len(results[0].boxes) > 0:
                    for box in results[0].boxes:
                        conf = float(box.conf[0].item())
                        if conf > best_conf:
                            best_conf = conf
                            best_box = list(map(int, box.xyxy[0].tolist()))

                if best_box is not None:
                    px1, py1, px2, py2 = best_box
                    crop_h, crop_w = vehicle_crop.shape[:2]
                    box_w = max(1, px2 - px1)
                    box_h = max(1, py2 - py1)

                    # Conservative outward expansion padding:
                    # 6% horizontally and 8% vertically (min 2px) to protect edge characters
                    # while avoiding outer black mounting frames, screws, radiator grills, and bumper trim.
                    pad_x = max(2, int(box_w * 0.06))
                    pad_y = max(2, int(box_h * 0.08))

                    # Safe bounds clamping to vehicle crop boundaries (never negative, never out-of-bounds)
                    px1_expanded = max(0, min(crop_w - 1, px1 - pad_x))
                    py1_expanded = max(0, min(crop_h - 1, py1 - pad_y))
                    px2_expanded = max(px1_expanded + 1, min(crop_w, px2 + pad_x))
                    py2_expanded = max(py1_expanded + 1, min(crop_h, py2 + pad_y))

                    plate_crop = vehicle_crop[py1_expanded:py2_expanded, px1_expanded:px2_expanded]
                    if plate_crop is None or plate_crop.size == 0:
                        return vehicle_crop, False, round(best_conf, 3)

                    ph, pw = plate_crop.shape[:2]

                    # Validate minimum plate dimensions (reject micro-noise)
                    if ph >= 10 and pw >= 35:
                        # Check sharpness via Laplacian variance (allow moderate sharpness for upscaling)
                        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
                        blur_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                        if blur_var >= 4.0:  # Sufficient sharpness for cubic upscale + OCR
                            return plate_crop, True, round(best_conf, 3)
                        else:
                            logger.debug(f"Plate crop rejected due to low sharpness ({blur_var:.1f} < 4.0)")
            except Exception as e:
                logger.error(f"Error during license plate detection inference: {e}")

        # Return full vehicle crop as candidate fallback when no plate detected
        return vehicle_crop, False, round(best_conf, 3)

    def extract_plate_crop(self, frame: np.ndarray, bbox: tuple, conf_threshold: float = 0.15) -> tuple:
        """Runs plate detector on vehicle bounding box."""
        if frame is None or frame.size == 0:
            return None, None, False, 0.0
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, max(x1 + 1, x2)), min(fh, max(y1 + 1, y2))
        vehicle_crop = frame[y1:y2, x1:x2]
        plate_crop, is_detected, best_conf = self.extract_plate_crop_from_vehicle(vehicle_crop, conf_threshold)
        return plate_crop, None, is_detected, best_conf

    def _preprocess_variants(self, plate_crop: np.ndarray) -> list:
        """
        Prepares conservative, high-quality preprocessing variants for OCR:
        1. Aspect-ratio preserving Cubic upscale (original color baseline)
        2. LAB L-channel CLAHE contrast normalization (gentle clipLimit=1.8)
        3. Unsharp mask sharpening (gentle halo-free sigma=1.0)
        4. MinMax contrast-stretched grayscale
        5. Adaptive / Otsu thresholding (contrast-gated, safe fallback on low contrast)
        6. Margin-trimmed variant (shaves outer frame/screw noise on large crops)
        """
        if plate_crop is None or plate_crop.size == 0:
            return []

        ph, pw = plate_crop.shape[:2]
        if ph <= 0 or pw <= 0:
            return []

        MIN_HEIGHT = 90
        MIN_WIDTH = 320

        # Aspect-ratio preserving scale (never distort plate proportions)
        scale_h = MIN_HEIGHT / float(ph) if ph < MIN_HEIGHT else 1.0
        scale_w = MIN_WIDTH / float(pw) if pw < MIN_WIDTH else 1.0
        scale = max(scale_h, scale_w)

        if scale > 1.0:
            target_w = max(MIN_WIDTH, int(pw * scale))
            target_h = max(MIN_HEIGHT, int(ph * scale))
            # Use INTER_CUBIC interpolation to avoid INTER_LANCZOS4 ringing halos
            upscaled = cv2.resize(plate_crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
        else:
            upscaled = plate_crop.copy()

        variants = []

        # Variant 1: Base Upscaled Color (Pure baseline, preserves original character strokes)
        variants.append(upscaled)

        # Variant 2: CLAHE Contrast Normalization on LAB L-channel (Gentle contrast enhancement)
        try:
            lab = cv2.cvtColor(upscaled, cv2.COLOR_BGR2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(6, 6))
            cl = clahe.apply(l_chan)
            var_clahe = cv2.cvtColor(cv2.merge((cl, a_chan, b_chan)), cv2.COLOR_LAB2BGR)
            variants.append(var_clahe)
        except Exception:
            pass

        # Variant 3: Gentle Unsharp Mask Sharpening (Edge enhancement without high-frequency ringing)
        try:
            blurred = cv2.GaussianBlur(upscaled, (0, 0), sigmaX=1.0)
            var_sharp = cv2.addWeighted(upscaled, 1.3, blurred, -0.3, 0)
            variants.append(var_sharp)
        except Exception:
            pass

        # Variant 4: MinMax Contrast Stretched Grayscale
        try:
            gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
            norm_gray = cv2.normalize(gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
            var_gray = cv2.cvtColor(norm_gray, cv2.COLOR_GRAY2BGR)
            variants.append(var_gray)
        except Exception:
            gray = None

        # Variant 5: Adaptive / Otsu Thresholding (Contrast-gated)
        try:
            if gray is None:
                gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
            std_dev = float(np.std(gray))
            dynamic_range = float(np.max(gray)) - float(np.min(gray))
            # Only apply thresholding if image has sufficient contrast (prevents crashing/garbage on uniform input)
            if std_dev >= 12.0 and dynamic_range >= 30.0:
                blur_sub = cv2.GaussianBlur(gray, (3, 3), 0)
                _, thresh = cv2.threshold(blur_sub, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                var_thresh = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                variants.append(var_thresh)
        except Exception:
            pass

        # Variant 6: Margin-Trimmed Crop (Shaves 3% outer border to remove dark screws and frame edges)
        try:
            if pw >= 60 and ph >= 20:
                trim_x = max(1, int(pw * 0.03))
                trim_y = max(1, int(ph * 0.04))
                trimmed_crop = plate_crop[trim_y:ph - trim_y, trim_x:pw - trim_x]
                if trimmed_crop.shape[0] >= 10 and trimmed_crop.shape[1] >= 35:
                    t_scale = max(MIN_HEIGHT / float(trimmed_crop.shape[0]), MIN_WIDTH / float(trimmed_crop.shape[1]))
                    t_up = cv2.resize(trimmed_crop, (int(trimmed_crop.shape[1] * t_scale), int(trimmed_crop.shape[0] * t_scale)), interpolation=cv2.INTER_CUBIC)
                    # Contrast normalization on trimmed crop
                    t_gray = cv2.cvtColor(t_up, cv2.COLOR_BGR2GRAY)
                    t_norm = cv2.normalize(t_gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
                    variants.append(cv2.cvtColor(t_norm, cv2.COLOR_GRAY2BGR))
        except Exception:
            pass

        return variants

    def _assemble_and_select_candidate(self, fragments: list) -> tuple:
        """
        Takes a list of OCR fragment dicts:
            [{'raw_text': str, 'clean_text': str, 'conf': float, 'bbox': [x1, y1, x2, y2], 'w': float, 'h': float, 'cx': float, 'cy': float}]
        1. Keeps the best single-box candidate as a safe fallback.
        2. Spatially clusters and chains fragments on the same horizontal text line.
        3. Evaluates assembled candidate vs single-box candidate through plate validation standards.
        4. Returns: (best_text, best_conf)
        """
        if not fragments:
            return None, 0.0

        # Filter out empty or micro-noise fragments (<0.15 confidence)
        valid_frags = [f for f in fragments if f.get("clean_text") and f.get("conf", 0.0) >= 0.15]
        if not valid_frags:
            best = max(fragments, key=lambda f: f.get("conf", 0.0))
            return best.get("raw_text"), round(float(best.get("conf", 0.0)), 3)

        # Single fragment case: directly return fallback without overhead
        best_single = max(valid_frags, key=lambda f: f["conf"])
        if len(valid_frags) == 1:
            return best_single["raw_text"], round(float(best_single["conf"]), 3)

        # Multi-fragment case: sort horizontally from left to right
        sorted_frags = sorted(valid_frags, key=lambda f: f["bbox"][0])

        # Find compatible horizontal chains
        chains = []
        n = len(sorted_frags)
        for i in range(n):
            chain = [sorted_frags[i]]
            for j in range(i + 1, n):
                prev = chain[-1]
                curr = sorted_frags[j]

                max_h = max(prev["h"], curr["h"])
                min_h = min(prev["h"], curr["h"])

                # 1. Vertical alignment: center Y displacement within 55% of max box height
                is_vertically_aligned = abs(prev["cy"] - curr["cy"]) <= (max_h * 0.55)
                # 2. Height ratio: boxes on same line have similar font height
                is_height_compatible = (min_h / max(max_h, 1.0)) >= 0.45
                # 3. Horizontal relationship: curr must be to the right with reasonable gap
                gap = curr["bbox"][0] - prev["bbox"][2]
                is_gap_compatible = (-0.25 * min(prev["w"], curr["w"])) <= gap <= max(max_h * 2.5, 40.0)

                if is_vertically_aligned and is_height_compatible and is_gap_compatible:
                    chain.append(curr)
                else:
                    break

            if len(chain) > 1 and chain not in chains:
                chains.append(chain)

        # Fallback candidate: best single box
        s_cleaned, s_valid, s_tier = self.validate_and_correct_plate(best_single["raw_text"], best_single["conf"])
        best_candidate_text = best_single["raw_text"]
        best_candidate_conf = float(best_single["conf"])
        best_candidate_valid = s_valid
        best_candidate_tier = s_tier
        best_candidate_len = len(s_cleaned) if s_cleaned else 0

        # If no valid multi-box chains found, return safe single fallback
        if not chains:
            return best_candidate_text, round(best_candidate_conf, 3)

        # Evaluate all assembled chains
        for chain in chains:
            joined_raw = "".join(f["raw_text"].strip() for f in chain)
            total_chars = sum(len(f["clean_text"]) for f in chain)
            if total_chars == 0 or total_chars > 12:
                continue

            # Weighted average confidence by character count (no artificial inflation)
            joined_conf = sum(f["conf"] * len(f["clean_text"]) for f in chain) / float(total_chars)

            a_cleaned, a_valid, a_tier = self.validate_and_correct_plate(joined_raw, joined_conf)
            a_len = len(a_cleaned) if a_cleaned else 0

            # Deterministic candidate selection:
            # - Assembled is valid while single box is NOT valid -> Assembled wins
            # - Assembled has higher validation tier than single -> Assembled wins
            # - Both same valid tier: prefer assembled if it captured more of the plate (longer string)
            #   without severe confidence drop (>0.20 drop)
            should_prefer_assembled = False
            if a_valid and not best_candidate_valid:
                should_prefer_assembled = True
            elif a_valid and best_candidate_valid:
                if a_tier > best_candidate_tier:
                    should_prefer_assembled = True
                elif a_tier == best_candidate_tier:
                    if a_len > best_candidate_len and joined_conf >= (best_candidate_conf - 0.20):
                        should_prefer_assembled = True
                    elif a_len == best_candidate_len and joined_conf > best_candidate_conf:
                        should_prefer_assembled = True

            if should_prefer_assembled:
                best_candidate_text = joined_raw
                best_candidate_conf = joined_conf
                best_candidate_valid = a_valid
                best_candidate_tier = a_tier
                best_candidate_len = a_len

        return best_candidate_text, round(best_candidate_conf, 3)

    def _execute_ocr(self, img: np.ndarray) -> tuple:
        """Executes fast CUDA EasyOCR (primary) with PaddleOCR (fallback) on an image."""
        text_result = None
        confidence = 0.0

        # 1. Try Fast CUDA-Accelerated EasyOCR first
        if self.easy_reader is not None:
            try:
                results = self.easy_reader.readtext(img)
                fragments = []
                if results and len(results) > 0:
                    for item in results:
                        if not item or len(item) < 3:
                            continue
                        bbox, text, prob = item[0], item[1], item[2]
                        if not text or not str(text).strip():
                            continue
                        clean_frag = re.sub(r'[^A-Za-z0-9]', '', str(text)).upper()
                        if not clean_frag:
                            continue
                        try:
                            xs = [float(pt[0]) for pt in bbox]
                            ys = [float(pt[1]) for pt in bbox]
                            x1, x2 = min(xs), max(xs)
                            y1, y2 = min(ys), max(ys)
                        except Exception:
                            continue
                        w = max(1.0, x2 - x1)
                        h = max(1.0, y2 - y1)
                        fragments.append({
                            "raw_text": str(text).strip(),
                            "clean_text": clean_frag,
                            "conf": float(prob),
                            "bbox": [x1, y1, x2, y2],
                            "w": w,
                            "h": h,
                            "cx": (x1 + x2) / 2.0,
                            "cy": (y1 + y2) / 2.0
                        })

                if fragments:
                    text_result, confidence = self._assemble_and_select_candidate(fragments)
                    if text_result and confidence >= 0.40:
                        return text_result, round(confidence, 3)
            except Exception as e:
                logger.debug(f"EasyOCR attempt error: {e}")

        # 2. Try PaddleOCR as secondary fallback
        if (text_result is None or confidence < 0.40) and self.ocr is not None:
            try:
                res = self.ocr.ocr(img)
                fragments = []
                if res and len(res) > 0:
                    for item in res:
                        if isinstance(item, list) and len(item) > 0:
                            for line in item:
                                if isinstance(line, (list, tuple)) and len(line) >= 2:
                                    bbox_poly = line[0]
                                    txt_info = line[1]
                                    if isinstance(txt_info, (list, tuple)) and len(txt_info) >= 2:
                                        txt = str(txt_info[0]).strip()
                                        score = float(txt_info[1])
                                    else:
                                        txt = str(txt_info).strip()
                                        score = 0.85
                                    clean_frag = re.sub(r'[^A-Za-z0-9]', '', txt).upper()
                                    if not clean_frag:
                                        continue
                                    try:
                                        xs = [float(pt[0]) for pt in bbox_poly]
                                        ys = [float(pt[1]) for pt in bbox_poly]
                                        x1, x2 = min(xs), max(xs)
                                        y1, y2 = min(ys), max(ys)
                                    except Exception:
                                        x1, y1, x2, y2 = 0.0, 0.0, 100.0, 30.0
                                    w = max(1.0, x2 - x1)
                                    h = max(1.0, y2 - y1)
                                    fragments.append({
                                        "raw_text": txt,
                                        "clean_text": clean_frag,
                                        "conf": score,
                                        "bbox": [x1, y1, x2, y2],
                                        "w": w,
                                        "h": h,
                                        "cx": (x1 + x2) / 2.0,
                                        "cy": (y1 + y2) / 2.0
                                    })
                                elif isinstance(line, str):
                                    txt = line.strip()
                                    clean_frag = re.sub(r'[^A-Za-z0-9]', '', txt).upper()
                                    if clean_frag:
                                        fragments.append({
                                            "raw_text": txt,
                                            "clean_text": clean_frag,
                                            "conf": 0.85,
                                            "bbox": [0.0, 0.0, 100.0, 30.0],
                                            "w": 100.0,
                                            "h": 30.0,
                                            "cx": 50.0,
                                            "cy": 15.0
                                        })
                        elif isinstance(item, dict):
                            rec_texts = item.get('rec_texts', item.get('rec_text', []))
                            rec_scores = item.get('rec_scores', item.get('rec_score', []))
                            if isinstance(rec_texts, list) and len(rec_texts) > 0:
                                for idx, txt in enumerate(rec_texts):
                                    score = float(rec_scores[idx]) if isinstance(rec_scores, list) and idx < len(rec_scores) else 0.85
                                    txt_s = str(txt).strip()
                                    clean_frag = re.sub(r'[^A-Za-z0-9]', '', txt_s).upper()
                                    if clean_frag:
                                        fragments.append({
                                            "raw_text": txt_s,
                                            "clean_text": clean_frag,
                                            "conf": score,
                                            "bbox": [float(idx * 80), 0.0, float(idx * 80 + 80), 30.0],
                                            "w": 80.0,
                                            "h": 30.0,
                                            "cx": float(idx * 80 + 40),
                                            "cy": 15.0
                                        })

                if fragments:
                    p_text, p_conf = self._assemble_and_select_candidate(fragments)
                    if p_text and p_conf > confidence:
                        text_result = p_text
                        confidence = p_conf
            except Exception as e:
                logger.debug(f"PaddleOCR attempt error: {e}")

        return text_result, round(confidence, 3)

    def validate_and_correct_plate(self, raw_text: str, confidence: float = 0.0) -> tuple:
        """
        Validates and cleans license plate string against Indian registration standards.
        Applies positional character heuristics (e.g. O->0 in numbers, 0->O in state code).
        Enforces strict Indian state-code validation with conservative Levenshtein-1 fuzzy recovery.
        Returns: (cleaned_plate_text, is_valid_format, tier)
        """
        if not raw_text:
            return None, False, 0

        # Remove non-alphanumeric characters and uppercase
        cleaned = re.sub(r'[^A-Z0-9]', '', raw_text.upper())

        # Reject obvious garbage
        if len(cleaned) < 4 or len(cleaned) > 11:
            return cleaned, False, 0
        if cleaned.isdigit() or cleaned.isalpha():
            # Genuine plates have a mix of letters and numbers (State code + numbers)
            return cleaned, False, 0
        if len(set(cleaned)) == 1:
            # Repetitive characters like 'AAAA' or '1111'
            return cleaned, False, 0

        chars = list(cleaned)
        n = len(chars)

        # Positional heuristics:
        # First 2 characters must be State Code letters
        # Fix common digit-to-letter OCR errors in state code
        num_to_alpha = {'0': 'O', '1': 'I', '8': 'B', '5': 'S', '2': 'Z'}
        alpha_to_num = {'O': '0', 'I': '1', 'B': '8', 'S': '5', 'Z': '2', 'D': '0', 'G': '6'}

        if n >= 6:
            # If char 0 or 1 is a digit, try correcting to letter
            if chars[0].isdigit() and chars[0] in num_to_alpha:
                chars[0] = num_to_alpha[chars[0]]
            if chars[1].isdigit() and chars[1] in num_to_alpha:
                chars[1] = num_to_alpha[chars[1]]

            # Chars 2-3 are typically District Code digits
            if n >= 4:
                if chars[2].isalpha() and chars[2] in alpha_to_num:
                    chars[2] = alpha_to_num[chars[2]]
                if chars[3].isalpha() and chars[3] in alpha_to_num:
                    chars[3] = alpha_to_num[chars[3]]

            # Last 3-4 characters are typically registration numbers
            for i in range(max(4, n - 4), n):
                if chars[i].isalpha() and chars[i] in alpha_to_num:
                    chars[i] = alpha_to_num[chars[i]]

        corrected = "".join(chars)

        # Tier 1 Validation: Strict Indian registration pattern
        # e.g. MH02FU9302, DL01AB1234, KA05M9999
        # ^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$
        tier1_match = re.match(r'^([A-Z]{2})([0-9]{1,2}[A-Z]{0,3}[0-9]{1,4})$', corrected)
        if tier1_match:
            raw_state = tier1_match.group(1)
            suffix = tier1_match.group(2)
            state_status, resolved_state = self.validate_state_code(raw_state)

            if state_status == "EXACT":
                return corrected, True, 1
            elif state_status == "FUZZY" and resolved_state is not None:
                # Conservative fuzzy recovery: derived candidate with unique valid state code
                derived_plate = resolved_state + suffix
                return derived_plate, True, 1
            else:
                # Invalid or ambiguous state code: MUST NOT trigger Tier 1 success
                return corrected, False, 0

        # Tier 2 Validation: Valid general alphanumeric plate (5-10 chars with both letters & numbers)
        has_alpha = bool(re.search(r'[A-Z]', corrected))
        has_digit = bool(re.search(r'[0-9]', corrected))
        if 5 <= len(corrected) <= 10 and has_alpha and has_digit:
            # If the plate starts with 2 letters followed by digits (looks like Indian registration),
            # but failed state validation above, do not classify as valid Tier 2 plate.
            if re.match(r'^[A-Z]{2}[0-9]', corrected):
                return corrected, False, 0
            return corrected, True, 2

        return corrected, False, 0

    def read_plate(self, plate_crop: np.ndarray) -> tuple:
        """
        Runs OCR over preprocessing variants, validates against format standards,
        and returns: (cleaned_plate_text, raw_text, genuine_confidence, is_valid_format, tier)
        """
        if plate_crop is None or plate_crop.size == 0:
            return None, None, 0.0, False, 0

        variants = self._preprocess_variants(plate_crop)
        best_cleaned = None
        best_raw = None
        best_conf = 0.0
        best_is_valid = False
        best_tier = 0

        for var_img in variants:
            raw_text, ocr_conf = self._execute_ocr(var_img)
            if not raw_text:
                continue

            cleaned, is_valid, tier = self.validate_and_correct_plate(raw_text, ocr_conf)

            # Scoring: format tier priority + genuine OCR confidence
            score = (tier * 1.0) + ocr_conf
            best_score = (best_tier * 1.0) + best_conf

            if score > best_score:
                best_cleaned = cleaned
                best_raw = raw_text
                best_conf = ocr_conf
                best_is_valid = is_valid
                best_tier = tier

            # Early exit ONLY if valid high-tier Indian plate format with EXACT state code is achieved.
            # Invalid or fuzzy-recovered state codes must NOT trigger early exit.
            is_exact_state = False
            if is_valid and tier == 1 and cleaned and len(cleaned) >= 2:
                st_stat, _ = self.validate_state_code(cleaned[:2])
                is_exact_state = (st_stat == "EXACT")

            if is_valid and tier == 1 and is_exact_state and ocr_conf >= 0.45:
                break

        if best_raw:
            return best_cleaned, best_raw, round(best_conf, 2), best_is_valid, best_tier

        return None, None, 0.0, False, 0
