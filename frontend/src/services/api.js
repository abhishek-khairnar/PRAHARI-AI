/**
 * PRAHARI-AI API Service Client
 * Encapsulates FastAPI backend communications cleanly without scattering fetch calls.
 */

export async function fetchDashboardStats() {
  const res = await fetch('/api/dashboard_stats');
  if (!res.ok) throw new Error(`Dashboard stats error: ${res.statusText}`);
  return await res.json();
}

export async function fetchCameras() {
  const res = await fetch('/api/cameras');
  if (!res.ok) throw new Error(`Cameras fetch error: ${res.statusText}`);
  return await res.json();
}

export async function fetchAnalytics() {
  const res = await fetch('/api/analytics');
  if (!res.ok) throw new Error(`Analytics fetch error: ${res.statusText}`);
  return await res.json();
}

export async function fetchAlerts(limit = 25, cameraId = null) {
  let url = `/api/alerts?limit=${limit}`;
  if (cameraId) url += `&camera_id=${encodeURIComponent(cameraId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Alerts fetch error: ${res.statusText}`);
  return await res.json();
}

export async function fetchAnprLog(limit = 25, cameraId = null) {
  let url = `/api/anpr_log?limit=${limit}`;
  if (cameraId) url += `&camera_id=${encodeURIComponent(cameraId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`ANPR fetch error: ${res.statusText}`);
  return await res.json();
}

export async function fetchSecurityEvents(limit = 25, eventType = null, cameraId = null) {
  let url = `/api/security_events?limit=${limit}`;
  if (eventType) url += `&event_type=${encodeURIComponent(eventType)}`;
  if (cameraId) url += `&camera_id=${encodeURIComponent(cameraId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Security events fetch error: ${res.statusText}`);
  return await res.json();
}

export async function startWebcam(deviceIndex = 0) {
  const res = await fetch('/api/webcam/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_index: deviceIndex })
  });
  if (!res.ok) throw new Error(`Start webcam error: ${res.statusText}`);
  return await res.json();
}

export async function stopWebcam() {
  const res = await fetch('/api/webcam/stop', {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Stop webcam error: ${res.statusText}`);
  return await res.json();
}
