"""
PRAHARI-AI Temporal ANPR Consensus Module
Validation-Aware & Positional Character-Wise Temporal Plate Consensus Engine.

Shared by:
- rtsp_stream.py (Production unified stream reader)
- benchmark/video_analysis.py (Scientifically valid ANPR evaluation)
"""

import re
from collections import defaultdict, Counter
from anpr_engine import validate_state_code, INDIAN_STATE_CODES


def validate_plate_string(text: str) -> tuple:
    """
    Validates a plate string using the exact Fix #1 standards:
    - Strict state-code lookup in official INDIAN_STATE_CODES
    - Conservative Levenshtein-1 fuzzy state recovery for unique unambiguous matches
    - Strict alphanumeric formatting and length bounds
    Returns: (cleaned_or_derived_text, is_valid, tier)
    """
    if not text:
        return "", False, 0
    cleaned = re.sub(r'[^A-Z0-9]', '', str(text).upper())
    if len(cleaned) < 4 or len(cleaned) > 11 or cleaned.isdigit() or cleaned.isalpha() or len(set(cleaned)) == 1:
        return cleaned, False, 0

    chars = list(cleaned)
    n = len(chars)
    num_to_alpha = {'0': 'O', '1': 'I', '8': 'B', '5': 'S', '2': 'Z'}
    alpha_to_num = {'O': '0', 'I': '1', 'B': '8', 'S': '5', 'Z': '2', 'D': '0', 'G': '6'}
    if n >= 6:
        if chars[0].isdigit() and chars[0] in num_to_alpha:
            chars[0] = num_to_alpha[chars[0]]
        if chars[1].isdigit() and chars[1] in num_to_alpha:
            chars[1] = num_to_alpha[chars[1]]
        if n >= 4:
            if chars[2].isalpha() and chars[2] in alpha_to_num:
                chars[2] = alpha_to_num[chars[2]]
            if chars[3].isalpha() and chars[3] in alpha_to_num:
                chars[3] = alpha_to_num[chars[3]]
        for i in range(max(4, n - 4), n):
            if chars[i].isalpha() and chars[i] in alpha_to_num:
                chars[i] = alpha_to_num[chars[i]]
    corrected = "".join(chars)

    # Tier 1 Validation: Strict Indian registration pattern
    tier1_match = re.match(r'^([A-Z]{2})([0-9]{1,2}[A-Z]{0,3}[0-9]{1,4})$', corrected)
    if tier1_match:
        raw_state = tier1_match.group(1)
        suffix = tier1_match.group(2)
        state_status, resolved_state = validate_state_code(raw_state)
        if state_status == "EXACT":
            return corrected, True, 1
        elif state_status == "FUZZY" and resolved_state is not None:
            derived_plate = resolved_state + suffix
            return derived_plate, True, 1
        else:
            return corrected, False, 0

    # Tier 2 Validation: General alphanumeric plate
    has_alpha = bool(re.search(r'[A-Z]', corrected))
    has_digit = bool(re.search(r'[0-9]', corrected))
    if 5 <= len(corrected) <= 10 and has_alpha and has_digit:
        if re.match(r'^[A-Z]{2}[0-9]', corrected):
            return corrected, False, 0
        return corrected, True, 2

    return corrected, False, 0


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes standard Levenshtein edit distance between two strings."""
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


def are_strings_groupable(s1: str, s2: str) -> bool:
    """
    Conservative grouping check between two normalized candidate strings.
    Allows exact matches, single-character substitutions, or length difference of 1
    with edit distance <= 1 on long plates. Unrelated strings remain in separate clusters.
    """
    if s1 == s2:
        return True
    l1, l2 = len(s1), len(s2)
    len_diff = abs(l1 - l2)
    if len_diff > 2:
        return False

    if l1 == l2:
        # Equal length: allow Hamming distance <= 2 for long plates (>=8), else <= 1
        diff_count = sum(1 for a, b in zip(s1, s2) if a != b)
        if diff_count <= 1:
            return True
        if diff_count <= 2 and l1 >= 8:
            # Must share prefix or suffix
            if s1[:3] == s2[:3] or s1[-4:] == s2[-4:]:
                return True
        return False

    # Differ by 1 character in length
    if len_diff == 1 and min(l1, l2) >= 7:
        d = levenshtein_distance(s1, s2)
        if d <= 1:
            return True
        if d <= 2 and min(l1, l2) >= 9:
            if s1[:3] == s2[:3] or s1[-3:] == s2[-3:]:
                return True

    return False


def resolve_temporal_consensus(
    observations: list,
    window_seconds: float = 25.0,
    current_ts: float = None,
    min_confidence: float = 0.20
) -> dict:
    """
    Resolves temporal consensus across a sequence of license plate OCR observations.

    Consensus Pipeline:
    1. Normalization & Filtering:
       - Cleans text to uppercase alphanumeric.
       - Validates format and state code via Fix #1 validator.
       - Discards observations outside the temporal window (if current_ts provided).
    2. Deterministic Candidate Grouping:
       - Clusters candidates by edit distance and alignment rules.
       - Cluster seeds are anchored deterministically by observation frequency and confidence.
    3. Validation-Aware Cluster Scoring:
       - Computes weighted score: sum(conf * (1.6 if valid else 0.8)) * repetition_bonus.
       - Repeated observations outrank isolated high-confidence outliers.
       - Low-confidence noise is bounded and cannot overpower solid candidates.
    4. Positional Character-Wise Voting:
       - Activated when cluster has >= 3 observations with consistent length (>=60%) and mean conf >= 0.25.
       - Votes per position weighted by observation confidence and validation bonus.
       - Selects winning character per position and validates the composite string.
       - Fallback to best valid candidate if voted string fails validation.
    5. Publication Tier Assignment:
       - VERIFIED: Valid Tier-1 format, confidence >= 0.45, and confirmed by >= 2 agreeing reads (or high single conf >= 0.70).
       - DETECTED: Valid format with conf >= 0.30, or valid Tier-2 format.
       - LOW_CONFIDENCE: Conf >= min_confidence but unvalidated.
       - NOT_READ: Conf < min_confidence or empty history.

    Args:
        observations: List of observation tuples or dicts.
        window_seconds: Max age of observations in seconds (default: 25.0).
        current_ts: Optional current timestamp to filter recent observations.
        min_confidence: Minimum confidence threshold for LOW_CONFIDENCE publication (default: 0.20).

    Returns:
        dict with:
            "published_plate": str or None,
            "published_conf": float,
            "published_tier": "VERIFIED" | "DETECTED" | "LOW_CONFIDENCE" | "NOT_READ",
            "is_valid": bool,
            "tier_num": int,
            "best_crop": np.ndarray or None,
            "consensus_method": str,
            "observation_count": int,
            "cluster_count": int,
            "agreeing_count": int
    """
    empty_result = {
        "published_plate": None,
        "published_conf": 0.0,
        "published_tier": "NOT_READ",
        "is_valid": False,
        "tier_num": 0,
        "best_crop": None,
        "consensus_method": "none",
        "observation_count": 0,
        "cluster_count": 0,
        "agreeing_count": 0
    }

    if not observations:
        return empty_result

    # Standardize observations
    norm_obs = []
    for obs in observations:
        if isinstance(obs, (list, tuple)):
            c_text = str(obs[0]) if len(obs) > 0 and obs[0] is not None else ""
            r_text = str(obs[1]) if len(obs) > 1 and obs[1] is not None else c_text
            conf = float(obs[2]) if len(obs) > 2 and obs[2] is not None else 0.0
            is_val = bool(obs[3]) if len(obs) > 3 else False
            tier_val = int(obs[4]) if len(obs) > 4 and obs[4] is not None else 0
            ts = float(obs[5]) if len(obs) > 5 and obs[5] is not None else None
            p_crop = obs[6] if len(obs) > 6 else None
        elif isinstance(obs, dict):
            c_text = str(obs.get("text", ""))
            r_text = str(obs.get("raw", c_text))
            conf = float(obs.get("conf", 0.0))
            is_val = bool(obs.get("is_valid", False))
            tier_val = int(obs.get("tier", 0))
            ts = float(obs["ts"]) if "ts" in obs and obs["ts"] is not None else None
            p_crop = obs.get("crop", None)
        else:
            continue

        clean = re.sub(r'[^A-Z0-9]', '', c_text.upper())
        if len(clean) < 3:
            continue

        # Re-validate format if not previously validated or to recover fuzzy state
        val_text, val_valid, val_tier = validate_plate_string(clean)
        if val_valid and val_tier == 1:
            clean = val_text
            is_val = True
            tier_val = 1
        else:
            is_val = val_valid
            tier_val = val_tier

        # Filter by window if timestamp and current_ts are provided
        if current_ts is not None and ts is not None:
            if (current_ts - ts) > window_seconds:
                continue

        norm_obs.append({
            "text": clean,
            "raw": r_text,
            "conf": max(0.0, min(1.0, conf)),
            "is_valid": is_val,
            "tier": tier_val,
            "ts": ts,
            "crop": p_crop
        })

    if not norm_obs:
        return empty_result

    # Group into candidate clusters
    # Sort unique candidates deterministically: (frequency desc, conf_sum desc, text asc)
    freq_map = Counter(o["text"] for o in norm_obs)
    conf_sum_map = defaultdict(float)
    for o in norm_obs:
        conf_sum_map[o["text"]] += o["conf"]

    unique_candidates = sorted(
        freq_map.keys(),
        key=lambda t: (freq_map[t], conf_sum_map[t], -len(t), t),
        reverse=True
    )

    clusters = []  # List of dicts: {"seed": str, "observations": list}
    for cand in unique_candidates:
        cand_obs = [o for o in norm_obs if o["text"] == cand]
        assigned = False
        for cl in clusters:
            if are_strings_groupable(cl["seed"], cand):
                cl["observations"].extend(cand_obs)
                assigned = True
                break
        if not assigned:
            clusters.append({
                "seed": cand,
                "observations": cand_obs
            })

    # Score each cluster deterministically
    best_cluster = None
    best_cluster_score = -1.0

    for cl in clusters:
        c_obs = cl["observations"]
        total_obs = len(c_obs)
        valid_obs = sum(1 for o in c_obs if o["is_valid"])

        # Base weighted confidence sum
        raw_weighted_sum = sum(o["conf"] * (1.6 if o["is_valid"] else 0.8) for o in c_obs)
        # Bounded repetition multiplier: 1.0 (1 read) up to 1.8 (5+ reads)
        rep_multiplier = 1.0 + 0.20 * min(total_obs - 1, 4)

        cluster_score = raw_weighted_sum * rep_multiplier
        cl["score"] = cluster_score
        cl["valid_count"] = valid_obs

        if cluster_score > best_cluster_score:
            best_cluster_score = cluster_score
            best_cluster = cl

    if not best_cluster or not best_cluster["observations"]:
        return empty_result

    win_obs = best_cluster["observations"]
    total_win = len(win_obs)

    # Determine candidate text: Character-Wise Positional Consensus vs Direct Selection
    length_counts = Counter(len(o["text"]) for o in win_obs)
    predom_len, predom_len_count = length_counts.most_common(1)[0]
    can_character_vote = (
        total_win >= 3 and
        (predom_len_count / total_win) >= 0.60 and
        (sum(o["conf"] for o in win_obs) / total_win) >= 0.25
    )

    final_text = None
    final_conf = 0.0
    final_valid = False
    final_tier = 0
    final_crop = None
    consensus_method = "single_candidate"

    if can_character_vote:
        aligned_obs = [o for o in win_obs if len(o["text"]) == predom_len]
        voted_chars = []

        for pos in range(predom_len):
            char_votes = defaultdict(float)
            char_counts = Counter()
            for o in aligned_obs:
                ch = o["text"][pos]
                w = o["conf"] * (1.5 if o["is_valid"] else 1.0)
                char_votes[ch] += w
                char_counts[ch] += 1

            # Deterministic character selection
            best_ch = max(sorted(char_votes.keys()), key=lambda c: (char_votes[c], char_counts[c]))
            voted_chars.append(best_ch)

        voted_string = "".join(voted_chars)
        c_clean, c_val, c_tier = validate_plate_string(voted_string)

        if c_val and c_tier in (1, 2):
            final_text = c_clean
            final_valid = c_val
            final_tier = c_tier
            consensus_method = "character_wise_voted"
        else:
            # If voted string failed validation, fallback to best valid observation in cluster
            valid_candidates = [o for o in aligned_obs if o["is_valid"]]
            if valid_candidates:
                best_v = max(valid_candidates, key=lambda o: (freq_map[o["text"]], o["conf"]))
                final_text = best_v["text"]
                final_valid = True
                final_tier = best_v["tier"]
                consensus_method = "cluster_valid_fallback"
            else:
                final_text = voted_string
                final_valid = False
                final_tier = 0
                consensus_method = "character_wise_unvalidated"

    if not final_text:
        # Direct selection: prioritize valid candidates with high repetition and confidence
        valid_obs_list = [o for o in win_obs if o["is_valid"]]
        if valid_obs_list:
            best_v = max(valid_obs_list, key=lambda o: (freq_map[o["text"]], o["conf"]))
            final_text = best_v["text"]
            final_valid = True
            final_tier = best_v["tier"]
            consensus_method = "direct_valid_best"
        else:
            best_raw = max(win_obs, key=lambda o: (freq_map[o["text"]], o["conf"]))
            final_text = best_raw["text"]
            final_valid = False
            final_tier = 0
            consensus_method = "direct_unvalidated_best"

    # Best crop associated with the final chosen text (or highest confidence crop in cluster)
    matching_crops = [o["crop"] for o in win_obs if o["text"] == final_text and o["crop"] is not None]
    if matching_crops:
        final_crop = matching_crops[0]
    else:
        crops_available = [o["crop"] for o in win_obs if o["crop"] is not None]
        final_crop = crops_available[0] if crops_available else None

    # Calculate final bounded confidence
    matching_obs = [o for o in win_obs if o["text"] == final_text]
    if matching_obs:
        base_c = sum(o["conf"] for o in matching_obs) / len(matching_obs)
        m_count = len(matching_obs)
    else:
        base_c = sum(o["conf"] for o in win_obs) / len(win_obs)
        m_count = len(win_obs)

    # Repetition bonus: bounded up to +0.12 for multiple agreeing reads
    rep_bonus = min(0.12, 0.04 * (m_count - 1)) if m_count > 1 else 0.0
    final_conf = min(0.99, round(base_c + rep_bonus, 2))

    # Publication Tier Assignment
    # Authoritative vehicle verification requires an external official vehicle registry (VAHAN/RTO).
    # In camera surveillance without external registry, format-compliant consensus reads are FORMAT_VALID.
    if final_valid and final_tier == 1 and final_conf >= 0.45 and (m_count >= 2 or final_conf >= 0.70):
        published_tier = "FORMAT_VALID"
    elif final_valid and final_conf >= 0.30:
        published_tier = "DETECTED"
    elif final_conf >= min_confidence:
        published_tier = "LOW_CONFIDENCE"
    else:
        published_tier = "NOT_READ"

    return {
        "published_plate": final_text,
        "published_conf": final_conf,
        "published_tier": published_tier,
        "is_valid": final_valid,
        "tier_num": final_tier,
        "best_crop": final_crop,
        "consensus_method": consensus_method,
        "observation_count": len(norm_obs),
        "cluster_count": len(clusters),
        "agreeing_count": m_count
    }
