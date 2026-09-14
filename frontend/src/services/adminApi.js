/**
 * PRAHARI-AI Admin Panel API Client
 * Manages JWT authentication, session persistence, role validation,
 * and administrative REST requests.
 */

const TOKEN_KEY = 'prahari_admin_token';
const USER_KEY = 'prahari_admin_user';

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getStoredUser() {
  const data = localStorage.getItem(USER_KEY);
  if (!data) return null;
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Internal authenticated fetch wrapper with automatic JWT Bearer injection
 * and 401 unauthorized handling.
 */
async function adminFetch(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Accept': 'application/json',
    ...(options.headers || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  const response = await fetch(endpoint, { ...options, headers });

  if (response.status === 401) {
    clearAuth();
    window.dispatchEvent(new CustomEvent('prahari:unauthorized'));
    throw new Error('Session expired or authentication required. Please log in.');
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorDetail = (data && data.detail) || response.statusText || 'Admin request failed';
    throw new Error(errorDetail);
  }

  return data;
}

// ─── Authentication APIs ───

export async function fetchAuthContext() {
  try {
    const res = await fetch('/api/auth/context');
    if (!res.ok) return { is_development: false, allow_demo_credentials: false };
    return await res.json();
  } catch {
    return { is_development: false, allow_demo_credentials: false };
  }
}

export async function login(username, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || 'Login failed.');
  }

  setAuthToken(data.access_token);
  setStoredUser(data.user);
  window.dispatchEvent(new CustomEvent('prahari:auth_changed', { detail: data.user }));
  return data;
}

export async function changePassword(oldPassword, newPassword) {
  const result = await adminFetch('/api/auth/change-password', {
    method: 'POST',
    body: { old_password: oldPassword, new_password: newPassword }
  });
  // Update stored user to clear must_change_password flag
  const currentUser = getStoredUser();
  if (currentUser) {
    currentUser.must_change_password = 0;
    setStoredUser(currentUser);
  }
  return result;
}

export async function logout() {
  try {
    await adminFetch('/api/auth/logout', { method: 'POST' });
  } catch (err) {
    console.warn('Logout warning:', err);
  } finally {
    clearAuth();
    window.dispatchEvent(new CustomEvent('prahari:unauthorized'));
  }
}

export async function fetchCurrentUser() {
  return await adminFetch('/api/auth/me');
}

// ─── Admin Management APIs ───

export async function fetchAdminOverview() {
  return await adminFetch('/api/admin/overview');
}

export async function fetchAdminUsers(role = null, isActive = null) {
  let url = '/api/admin/users?';
  if (role) url += `role=${encodeURIComponent(role)}&`;
  if (isActive !== null) url += `is_active=${encodeURIComponent(isActive)}&`;
  return await adminFetch(url);
}

export async function createAdminUser(userData) {
  return await adminFetch('/api/admin/users', {
    method: 'POST',
    body: userData
  });
}

export async function updateAdminUser(userId, userData) {
  return await adminFetch(`/api/admin/users/${userId}`, {
    method: 'PATCH',
    body: userData
  });
}

export async function resetUserPassword(userId, newPassword) {
  return await adminFetch(`/api/admin/users/${userId}/reset-password`, {
    method: 'POST',
    body: { new_password: newPassword }
  });
}

export async function fetchAdminCameras() {
  return await adminFetch('/api/admin/cameras');
}

export async function updateAdminCamera(cameraId, cameraData) {
  return await adminFetch(`/api/admin/cameras/${cameraId}`, {
    method: 'PATCH',
    body: cameraData
  });
}

export async function fetchAdminZones(cameraId = null, isEnabled = null) {
  let url = '/api/admin/zones?';
  if (cameraId) url += `camera_id=${encodeURIComponent(cameraId)}&`;
  if (isEnabled !== null) url += `is_enabled=${encodeURIComponent(isEnabled)}&`;
  return await adminFetch(url);
}

export async function createAdminZone(zoneData) {
  return await adminFetch('/api/admin/zones', {
    method: 'POST',
    body: zoneData
  });
}

export async function updateAdminZone(zoneId, zoneData) {
  return await adminFetch(`/api/admin/zones/${zoneId}`, {
    method: 'PATCH',
    body: zoneData
  });
}

export async function deleteAdminZone(zoneId) {
  return await adminFetch(`/api/admin/zones/${zoneId}`, {
    method: 'DELETE'
  });
}

export async function fetchAdminAlertRules() {
  return await adminFetch('/api/admin/alert-rules');
}

export async function updateAdminAlertRule(ruleId, ruleData) {
  return await adminFetch(`/api/admin/alert-rules/${ruleId}`, {
    method: 'PATCH',
    body: ruleData
  });
}

export async function fetchAdminIncidents({ status = null, severity = null, camera_id = null, limit = 50, offset = 0, page = null, page_size = null } = {}) {
  let url = `/api/admin/incidents?`;
  if (page !== null) url += `page=${encodeURIComponent(page)}&`;
  if (page_size !== null) url += `page_size=${encodeURIComponent(page_size)}&`;
  url += `limit=${limit}&offset=${offset}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (severity) url += `&severity=${encodeURIComponent(severity)}`;
  if (camera_id) url += `&camera_id=${encodeURIComponent(camera_id)}`;
  return await adminFetch(url);
}

export async function fetchAdminIncident(incidentId) {
  return await adminFetch(`/api/admin/incidents/${incidentId}`);
}

export async function createAdminIncident(incidentData) {
  return await adminFetch('/api/admin/incidents', {
    method: 'POST',
    body: incidentData
  });
}

export async function updateAdminIncident(incidentId, incidentData) {
  return await adminFetch(`/api/admin/incidents/${incidentId}`, {
    method: 'PATCH',
    body: incidentData
  });
}

export async function fetchAdminSystemHealth() {
  return await adminFetch('/api/admin/system-health');
}

export async function fetchAdminAuditLogs({ limit = 100, offset = 0, page = null, page_size = null, action = null, actor = null } = {}) {
  let url = `/api/admin/audit-logs?`;
  if (page !== null) url += `page=${encodeURIComponent(page)}&`;
  if (page_size !== null) url += `page_size=${encodeURIComponent(page_size)}&`;
  url += `limit=${limit}&offset=${offset}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  if (actor) url += `&actor=${encodeURIComponent(actor)}`;
  return await adminFetch(url);
}
