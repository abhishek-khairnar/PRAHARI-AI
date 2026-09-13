# PRAHARI-AI — Functional Audit Complete Checkpoint

- **Audit Start**: 2026-09-13T09:24:14+05:30
- **Audit End**: 2026-09-13T10:20:00+05:30
- **Git Commit**: `cd4b889ddb06604bda3b56fa53efebccb18eb538`
- **Production Model Hash Before**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36`
- **Production Model Hash After**: `F59B3D833E2FF32E194B5BB8E08D211DC7C5BDF144B90D2C8412C47CCFC83B36` (Identical, PASS)
- **Total Tests**: 45
- **PASS Count**: 44
- **PARTIAL Count**: 1 (T17 Loitering — functional execution verified, demo videos lack >20s stationary dwell ground truth)
- **FAIL Count**: 0
- **BLOCKED Count**: 0
- **N/A Count**: 0
- **Functional Pass Rate**: 97.8%
- **Critical Failures**: None
- **Important Warnings**:
  1. Synchronous HTTP test harnesses on MJPEG endpoints block indefinitely if attempting unconstrained `iter_bytes()` on `while True` generators. Bounded sampling must be used.
  2. In local video file mode, `CentroidTracker` resets `next_object_id` upon video loop rewind/scene discontinuity, causing track ID recycling across loops. Global database IDs should be used for event keying.
  3. Initial audit execution ran against production `prahari_events.db`, generating additional runtime events. No automatic deletion or rollback was performed. Subsequent runs used `PRAHARI_DB_PATH` isolation.
- **Final Decision**: **🟢 PRODUCTION FUNCTIONAL**
- **Top 5 Recommended Next Actions**:
  1. **Enforce Database Isolation**: Maintain `PRAHARI_DB_PATH` configuration in all automated testing environments.
  2. **Bounded Stream Test Patterns**: Standardize single-frame async sampling for all MJPEG streaming unit/integration tests.
  3. **Dedicated Loitering Test Clip**: Source a >30s video with stationary person dwell to enable full ground-truth validation for T17.
  4. **Database Primary Key Event Referencing**: Ensure notifications and frontend components key items by SQL primary key `id` rather than tracker `object_id`.
  5. **Freeze Production Weights**: Keep production model `weights/yolov8n.pt` locked with verified SHA256 integrity hash.
