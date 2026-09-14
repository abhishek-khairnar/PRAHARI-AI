# Forensic Report: /admin/incidents Blank Page Defect

**Date:** 2026-09-13  
**Auditor:** PRAHARI-AI Advanced Diagnostic Agent  
**Status:** Completed Forensic Audit (Evidence Recorded)

---

## Executive Summary

Navigating to `/admin/incidents` or reloading the Admin section resulted in a completely blank white page under certain conditions.

The investigation proved that:
- **The backend API (`/api/admin/incidents`) is fully functional:** It returns HTTP 200 with schema `{ items: [...], total: 1368, page: 1, page_size: 15 }` and `X-Total-Count: 1368`.
- **The FastAPI routing is fully functional:** `spa_page_fallback` correctly serves `dist/index.html` on `/admin/incidents`.
- **The Root Cause is a Frontend React Runtime Exception:**
  In `frontend/src/components/admin/AdminLayout.jsx`:
  The sidebar navigation array defines:
  ```javascript
  { id: 'notifications', label: 'Notifications', icon: Bell, visible: true },
  ```
  However, in `AdminLayout.jsx` lines 2–6, `Bell` was **NEVER imported from `lucide-react`**! Only `BellRing` was imported.
  At runtime, evaluating `icon: Bell` produces `undefined` (or a `ReferenceError`). When React attempts to render `<Icon style={{ width: 16, height: 16 }} />`, React throws:
  `Element type is invalid: expected a string or a class/function but got: undefined.`
- **Lack of Error Boundary:** PRAHARI-AI had no application-level or route-level React Error Boundary. When any component in the tree throws during render, React unmounts the entire DOM hierarchy, resulting in an unexplained blank white page.

---

## 1. Forensic Evidence & Code Analysis

### Evidence 1: Missing Import in `AdminLayout.jsx`
Lines 1–7 of `frontend/src/components/admin/AdminLayout.jsx`:
```javascript
import React, { useState } from 'react';
import {
  ShieldAlert, LayoutDashboard, Users, Video, Sliders,
  BellRing, AlertTriangle, Activity, FileText, ArrowLeft,
  LogOut, UserCheck
} from 'lucide-react';
```
Line 34:
```javascript
{ id: 'notifications', label: 'Notifications', icon: Bell, visible: true },
```
Line 80:
```javascript
const Icon = item.icon; // evaluates to undefined when item.id === 'notifications'
...
<Icon style={{ width: 16, height: 16 }} /> // Throws fatal React render exception!
```

### Evidence 2: Backend API Verification
Direct query on `/api/admin/incidents`:
- Returns valid JSON with all fields (`incident_code`, `detected_at`, `camera_id`, `event_type`, `severity`, `status`).
- Response status: HTTP 200 OK.
- Database contains 1,368 valid incidents.

### Evidence 3: Frontend Defensive Gaps in `AdminIncidents.jsx`
- Line 340: `selectedIncident.evidence_snapshot.split(/[\\/]/).pop()` assumes `evidence_snapshot` is always a valid string if truthy.
- Absence of defensive check on null/malformed notes in edge cases.

---

## 2. Root Cause Determination

| Category | Finding | Impact |
|---|---|---|
| **Component Import** | `Bell` identifier referenced in `AdminLayout.jsx:34` without import from `lucide-react` | Fatal React runtime exception |
| **Error Handling** | No React `ErrorBoundary` mounted in `App.jsx` or `AdminLayout.jsx` | Uncaught render error unmounts whole UI to blank white screen |
| **Defensive Rendering** | Minor string-splitting assumptions in incident detail modal | Potential crash if evidence snapshot is non-string |

---

## 3. Required Corrective Action Plan

1. **Fix Import in `AdminLayout.jsx`**: Import `Bell` from `lucide-react` (or use `BellRing`).
2. **Implement React Error Boundary**:
   - Create `frontend/src/components/common/ErrorBoundary.jsx`.
   - Provide a recovery UI:
     - "PRAHARI-AI — Something went wrong loading this page."
     - [Retry] button.
     - [Return to Admin Overview] / [Return to Dashboard] buttons.
     - Diagnostic details in development mode without leaking stack traces in production.
   - Wrap the AdminLayout and root application in the Error Boundary.
3. **Enhance Defensive Rendering in `AdminIncidents.jsx`**:
   - Ensure safe handling of empty datasets, undefined fields, non-string snapshots, and loading/error states.
