# PRAHARI-AI GitHub Release Audit

**Audit Timestamp**: 2026-09-14 15:02:00 IST  
**Auditor**: Antigravity Autonomous Security Engineer  
**Target Repository**: `https://github.com/abhishek-khairnar/PRAHARI-AI`  
**Target Branch**: `main`  

---

## 1. Repository & Branch Synchronization

- **Remote Origin URL**: `https://github.com/abhishek-khairnar/PRAHARI-AI.git`
- **Initial Remote HEAD**: `cd4b889ddb06604bda3b56fa53efebccb18eb538` (`fix(launcher): resolve CMD parenthesis syntax crash in start_prahari.bat`)
- **Initial Local HEAD**: `7c6676e6883c1119aa7387b6052ca78b8696ca4e` (`feat(admin): complete data-truth, live incident pipeline and camera telemetry hardening`)
- **Lineage Verification**: `git merge-base origin/main HEAD` returned `cd4b889ddb06604bda3b56fa53efebccb18eb538`. Local branch is a direct descendant of remote main with zero divergence.
- **Local Backup Safety Checkpoint**: `backup/pre-github-release-20260914-1445` created at `7c6676e`.
- **Force Push Used**: **NO** (Strictly forbidden).
- **History Rewritten**: **NO** (`git-filter-repo` / rebase / commit deletion strictly avoided).

---

## 2. Included Categories

| Category | Component / Files | Status |
| :--- | :--- | :--- |
| **Backend Core** | `main.py`, `camera_manager.py`, `rtsp_stream.py`, `centroid_tracker.py`, `anpr_engine.py`, `anpr_consensus.py`, `database.py`, `requirements.txt` | Tracked & Synchronized |
| **Admin Subsystem** | `admin/admin_routes.py`, `admin/auth.py`, `admin/__init__.py` | Tracked |
| **Notification Subsystem**| `notifications/notification_models.py`, `notifications/notification_routes.py`, `notifications/notification_service.py`, `notifications/notification_realtime.py` | Tracked |
| **Frontend Source** | `frontend/src/` (App.jsx, Header.jsx, dashboard/, notifications/, admin/, common/, hooks/, services/, styles/) | Tracked |
| **Production AI Models** | `weights/yolov8n.pt` (6.55 MB), `weights/license-plate-finetune-v1n.pt` (5.46 MB), `weights/face_detection_yunet_2023mar.onnx` (0.23 MB) | Tracked (All verified) |
| **Core Demo Videos** | `demo_videos/border_demo.mp4` (10.8 MB), `demo_videos/night_demo.mp4` (1.9 MB), `demo_videos/activity-demo.mp4` (2.45 MB), `demo_videos/cctv_demo.mp4` (3.48 MB) | Tracked (17.78 MB total) |
| **Test Suites** | `tests/test_final_acceptance_suite.py`, `tests/test_p0_regressions.py`, `tests/test_full_suite.py`, `tests/admin/`, `tests/test_notification_*.py`, etc. | Tracked |
| **Configuration** | `.env.example`, `start_prahari.bat`, `start_prahari.ps1`, `package.json`, `vite.config.js` | Tracked |
| **Documentation** | `README.md` (54 sections, 17 Mermaid diagrams), verified audit reports in `reports/` | Tracked |

---

## 3. Excluded Categories (Security & Hygiene Verification)

| Excluded Category | Target Patterns in `.gitignore` | Verification Status |
| :--- | :--- | :--- |
| **Runtime Databases** | `*.db`, `*.db-wal`, `*.db-shm`, `*.db-journal`, `db_backups/` | Confirmed Ignored (`prahari_events.db`, `surveillance.db`) |
| **Runtime Snapshots** | `static/alerts/*`, `static/anpr/*`, `static/anpr_debug/*` | Confirmed Ignored (Preserved `.gitkeep` only) |
| **Secrets & Keys** | `.env`, `.env.*` (except `.env.example`), `*.key`, `*.pem` | Confirmed Clean (No secrets staged) |
| **Frontend Builds & Nodes**| `frontend/dist/`, `node_modules/`, `frontend/node_modules/` | Confirmed Ignored |
| **Python Caches** | `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.pytest_cache/` | Confirmed Ignored |
| **Experimental Models** | `yolo26n.pt`, `weights/candidates/`, `weights/best.pt` | Confirmed Ignored |
| **Training Datasets & Runs**| `dataset/`, `dataset_v2/`, `runs/`, `scratch_archive.zip` | Confirmed Ignored |
| **External Infrastructure** | `mediamtx/`, `ffmpeg/`, `test.mp4` | Confirmed Ignored (Locked per AGENTS.md) |

---

## 4. Model Weight Integrity

| Model Name | Canonical / Before SHA256 | Post-Audit SHA256 | Status |
| :--- | :--- | :--- | :---: |
| `weights/yolov8n.pt` | `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` | `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` | **MATCH (UNCHANGED)** |
| `weights/license-plate-finetune-v1n.pt` | `0AEC75976C56EB6F26DFB274C430620EC65137915FF1AE47C3A48C7AF8AFB7B2` | `0AEC75976C56EB6F26DFB274C430620EC65137915FF1AE47C3A48C7AF8AFB7B2` | **MATCH (UNCHANGED)** |
| `weights/face_detection_yunet_2023mar.onnx` | `8F2383E4DD3CFBB4553EA8718107FC0423210DC964F9F4280604804ED2552FA4` | `8F2383E4DD3CFBB4553EA8718107FC0423210DC964F9F4280604804ED2552FA4` | **MATCH (UNCHANGED)** |

---

## 5. Automated Test & Build Validation

- **Frontend Production Build**: `npm run build` in `frontend/` $\rightarrow$ **SUCCESS** (1627 modules transformed, 0 errors, 1.56s).
- **Backend Import Validation**: All backend modules (`main`, `camera_manager`, `database`, `centroid_tracker`, `anpr_engine`, `anpr_consensus`, `rtsp_stream`, `admin.*`, `notifications.*`) $\rightarrow$ **SUCCESS** (All CUDA FP16 models loaded cleanly).
- **Critical P0 Regression Suite (`tests/test_p0_regressions.py`)**: **13 / 13 PASSED** (100%).
- **Final Acceptance Suite (`tests/test_final_acceptance_suite.py`)**: **72 / 72 PASSED** (100%).
- **Admin & RBAC Suite (`tests/admin/`)**: **48 / 48 PASSED** (100%).
- **Multi-Camera Core Suite (`tests/test_full_suite.py`)**: **9 / 9 PASSED** (100%).
- **ANPR Accuracy & Consensus Suite (`tests/test_anpr_accuracy_fix.py`)**: **44 / 44 PASSED** (100%).
- **Dashboard Telemetry Provenance Suite (`tests/test_dashboard_metric_audit.py`)**: **22 / 22 PASSED** (100%).
- **Combined Simultaneous Core Test Run**: **142 / 142 PASSED** in single session.
- **Total Test Assertions Verified Across Project**: **303 PASSED**.

---

## 6. Documentation Quality & Compliance

- **README Structure**: Complete 54 sections conforming strictly to release guidelines.
- **Mermaid Diagrams**: Exactly 17 valid GitHub-compatible Mermaid diagrams verified (flowcharts, sequence diagrams, state machines, ER diagram) with 100% clean visual rendering on GitHub.
- **ANPR Terminology**: Outdated claim *"VERIFIED = format + confidence"* completely removed. Clearly distinguishes plate detected, OCR read, low confidence, format valid, temporal consensus, and validated ANPR read. Explicitly discloses that authoritative owner verification requires external registry (e.g. VAHAN).
- **Face Privacy**: Explicitly documents detection-only behavior via YuNet ONNX, live counting without identity matching, and absence of biometric database.
- **Notification Architecture**: Documents invariant `DATABASE = SOURCE OF TRUTH`, REST recovery via `since_id` cursor, and real-time WebSocket delivery.
- **Admin Panel & RBAC**: Documents all `/admin/*` routes and permissions for `SUPER_ADMIN`, `ADMIN`, `SUPERVISOR`, and `OFFICER`.
- **Command Center Dashboard**: Reflects true 3+2 layout with CAM-WEBCAM.

---

## 7. Git Safety Verification

- [x] Remote URL confirmed: `https://github.com/abhishek-khairnar/PRAHARI-AI.git`
- [x] Branch confirmed: `main`
- [x] No `git push --force` or `--force-with-lease`
- [x] No `git reset --hard` on remote tracking branches
- [x] No secrets staged
- [x] No production database (`*.db`) staged
- [x] No runtime alert snapshots staged
- [x] No experimental checkpoints or datasets staged
- [x] Production model SHA256 verified identical before and after release
- [x] Clean, intentional staging

---

## 8. Final Release Verdict

**Verdict**: **`READY`**  
The PRAHARI-AI codebase, configuration, models, demo assets, test suites, and documentation are fully verified, robust, and safe for publication on `origin/main`.
