/**
 * PRAHARI-AI Notification Subsystem API Client
 * Manages REST requests for alerts, unread counts, read acknowledgments,
 * and user delivery preferences.
 */

import { getAuthToken, clearAuth } from './adminApi';

async function notifFetch(endpoint, options = {}) {
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
    throw new Error('Session expired or authentication required.');
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const errorDetail = (data && data.detail) || response.statusText || 'Notification request failed';
    throw new Error(errorDetail);
  }

  return data;
}

export async function fetchNotifications({ is_read = null, severity = null, limit = 50, offset = 0, since_id = null } = {}) {
  const params = new URLSearchParams();
  if (is_read !== null && is_read !== undefined) params.append('is_read', is_read);
  if (severity) params.append('severity', severity);
  if (limit) params.append('limit', limit);
  if (offset) params.append('offset', offset);
  if (since_id !== null && since_id !== undefined) params.append('since_id', since_id);

  const query = params.toString() ? `?${params.toString()}` : '';
  return await notifFetch(`/api/notifications${query}`);
}

export async function fetchUnreadCount() {
  return await notifFetch('/api/notifications/unread-count');
}

export async function markNotificationRead(notificationId) {
  return await notifFetch(`/api/notifications/${notificationId}/read`, {
    method: 'POST'
  });
}

export async function markAllNotificationsRead() {
  return await notifFetch('/api/notifications/mark-all-read', {
    method: 'POST'
  });
}

export async function fetchNotificationPreferences() {
  return await notifFetch('/api/notifications/preferences');
}

export async function updateNotificationPreferences(preferences) {
  return await notifFetch('/api/notifications/preferences', {
    method: 'PUT',
    body: preferences
  });
}

export function getNotificationWebSocketUrl(token) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${protocol}//${host}/api/notifications/ws${tokenParam}`;
}
