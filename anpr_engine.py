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


class ANPREngine:
    def __init__(self):
        import torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.ocr = None
        self.easy_reader = None
        self.engine_type = "None"
        self.plate_detector = None
        self.detector_model_name = "None"

        # 1. Initialize YOLO License Plate Detector Model from Hugging Face
        try:
            from ultralytics import YOLO
            from huggingface_hub import hf_hub_download

            logger.info("Loading fine-tuned YOLO License Plate Detection model from Hugging Face...")
            try:
                # Primary: morsetechlab YOLOv11 license plate nano model
                model_path = hf_hub_download(
                    repo_id="morsetechlab/yolov11-license-plate-detection",
                    filename="license-plate-finetune-v1n.pt"
                )
                self.plate_detector = YOLO(model_path)
                self.detector_model_name = "morsetechlab/yolov11-license-plate-detection (v1n)"
                logger.info(f"YOLO License Plate Detector model successfully loaded: {self.detector_model_name}")
            except Exception as e1:
                logger.warning(f"Could not load morsetechlab model ({e1}). Trying fallback keremberke/yolov5n-license-plate...")
                model_path = hf_hub_download(
                    repo_id="keremberke/yolov5n-license-plate",
                    filename="best.pt"
                )
                self.plate_detector = YOLO(model_path)
                self.detector_model_name = "keremberke/yolov5n-license-plate (best.pt)"
                logger.info(f"Fallback YOLO License Plate Detector loaded: {self.detector_model_name}")
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
                    box_w = px2 - px1
                    box_h = py2 - py1

                    # Outward expansion padding: Expand 12% horizontally and 18% vertically
                    # to prevent edge characters (e.g. 'M', 'H', '4', '6') from being clipped
                    pad_x = max(6, int(box_w * 0.12))
                    pad_y = max(4, int(box_h * 0.18))

                    px1_expanded = max(0, px1 - pad_x)
                    py1_expanded = max(0, py1 - pad_y)
                    px2_expanded = min(crop_w, px2 + pad_x)
                    py2_expanded = min(crop_h, py2 + pad_y)

                    plate_crop = vehicle_crop[py1_expanded:py2_expanded, px1_expanded:px2_expanded]
                    ph, pw = plate_crop.shape[:2]

                    # Validate minimum plate dimensions (reject micro-noise)
                    if ph >= 10 and pw >= 35:
                        # Check sharpness via Laplacian variance (allow moderate sharpness for upscaling)
                        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
                        blur_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                        if blur_var >= 4.0:  # Sufficient sharpness for Lanczos upscale + OCR
                            return plate_crop, True, round(best_conf, 3)
                        else:
                            logger.debug(f"Plate crop rejected due to low sharpness ({blur_var:.1f} < 4.0)")
            except Exception as e:
                logger.error(f"Error during license plate detection inference: {e}")

        # Return full vehicle crop as candidate fallback when no plate detected
        return vehicle_crop, False, round(best_conf, 3)

    def extract_plate_crop(self, frame: np.ndarray, bbox: tuple, conf_threshold: float = 0.15) -> tuple:
        """Runs plate detector on vehicle bounding box."""
        fh, fw = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(fw, x2), min(fh, y2)
        vehicle_crop = frame[y1:y2, x1:x2]
        plate_crop, is_detected, best_conf = self.extract_plate_crop_from_vehicle(vehicle_crop, conf_threshold)
        return plate_crop, None, is_detected, best_conf

    def _preprocess_variants(self, plate_crop: np.ndarray) -> list:
        """
        Prepares high-quality preprocessing variants for OCR:
        1. Aspect-ratio preserving Lanczos upscale + CLAHE
        2. Unsharp mask sharpening
        3. High-contrast grayscale
        """
        ph, pw = plate_crop.shape[:2]
        MIN_HEIGHT = 90
        MIN_WIDTH = 320

        # Compute aspect-ratio preserving scale
        scale_h = MIN_HEIGHT / float(ph) if ph < MIN_HEIGHT else 1.0
        scale_w = MIN_WIDTH / float(pw) if pw < MIN_WIDTH else 1.0
        scale = max(scale_h, scale_w)

        if scale > 1.0:
            target_w = int(pw * scale)
            target_h = int(ph * scale)
            upscaled = cv2.resize(plate_crop, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            upscaled = plate_crop.copy()

        variants = []

        # Variant 1: CLAHE Contrast Normalization on LAB L-channel
        try:
            lab = cv2.cvtColor(upscaled, cv2.COLOR_BGR2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            cl = clahe.apply(l_chan)
            var1 = cv2.cvtColor(cv2.merge((cl, a_chan, b_chan)), cv2.COLOR_LAB2BGR)
            variants.append(var1)
        except Exception:
            variants.append(upscaled)

        # Variant 2: Unsharp Mask Sharpening
        try:
            blurred = cv2.GaussianBlur(upscaled, (0, 0), sigmaX=2.0)
            var2 = cv2.addWeighted(upscaled, 1.6, blurred, -0.6, 0)
            variants.append(var2)
        except Exception:
            pass

        # Variant 3: Contrast Stretched Grayscale
        try:
            gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
            norm_gray = cv2.normalize(gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
            var3 = cv2.cvtColor(norm_gray, cv2.COLOR_GRAY2BGR)
            variants.append(var3)
        except Exception:
            pass

        return variants

    def _execute_ocr(self, img: np.ndarray) -> tuple:
        """Executes fast CUDA EasyOCR (primary) with PaddleOCR (fallback) on an image."""
        text_result = None
        confidence = 0.0

        # 1. Try Fast CUDA-Accelerated EasyOCR first
        if self.easy_reader is not None:
            try:
                results = self.easy_reader.readtext(img)
                for bbox, text, prob in results:
                    score = float(prob)
                    if score > confidence:
                        confidence = score
                        text_result = text
                if text_result and confidence >= 0.40:
                    return text_result, round(confidence, 3)
            except Exception as e:
                logger.debug(f"EasyOCR attempt error: {e}")

        # 2. Try PaddleOCR as secondary fallback
        if (text_result is None or confidence < 0.40) and self.ocr is not None:
            try:
                res = self.ocr.ocr(img)
                if res and len(res) > 0:
                    for item in res:
                        if isinstance(item, list) and len(item) > 0:
                            for line in item:
                                if isinstance(line, (list, tuple)) and len(line) >= 2 and isinstance(line[1], (list, tuple)):
                                    txt = line[1][0]
                                    score = float(line[1][1])
                                    if score > confidence:
                                        confidence = score
                                        text_result = txt
                                elif isinstance(line, str):
                                    txt = line
                                    score = 0.85
                                    if score > confidence:
                                        confidence = score
                                        text_result = txt
                        elif isinstance(item, dict):
                            rec_texts = item.get('rec_texts', item.get('rec_text', []))
                            rec_scores = item.get('rec_scores', item.get('rec_score', []))
                            if isinstance(rec_texts, list) and len(rec_texts) > 0:
                                for idx, txt in enumerate(rec_texts):
                                    score = float(rec_scores[idx]) if isinstance(rec_scores, list) and idx < len(rec_scores) else 0.85
                                    if score > confidence:
                                        confidence = score
                                        text_result = txt
            except Exception as e:
                logger.debug(f"PaddleOCR attempt error: {e}")

        return text_result, round(confidence, 3)

    def validate_and_correct_plate(self, raw_text: str, confidence: float) -> tuple:
        """
        Validates and cleans license plate string against Indian registration standards.
        Applies positional character heuristics (e.g. O->0 in numbers, 0->O in state code).
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
        # ^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{3,4}$
        tier1_match = re.match(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{1,4}$', corrected)
        if tier1_match:
            state_code = corrected[:2]
            if state_code in INDIAN_STATE_CODES:
                return corrected, True, 1
            return corrected, True, 1

        # Tier 2 Validation: Valid general alphanumeric plate (5-10 chars with both letters & numbers)
        has_alpha = bool(re.search(r'[A-Z]', corrected))
        has_digit = bool(re.search(r'[0-9]', corrected))
        if 5 <= len(corrected) <= 10 and has_alpha and has_digit:
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

            # Early exit if valid high-tier Indian plate format is already achieved
            if is_valid and tier == 1 and ocr_conf >= 0.45:
                break

        if best_raw:
            return best_cleaned, best_raw, round(best_conf, 2), best_is_valid, best_tier

        return None, None, 0.0, False, 0
