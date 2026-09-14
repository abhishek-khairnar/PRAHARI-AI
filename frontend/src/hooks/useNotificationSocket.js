import { useState, useEffect, useRef, useCallback } from 'react';
import { getAuthToken } from '../services/adminApi';
import {
  fetchNotifications,
  fetchUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  getNotificationWebSocketUrl
} from '../services/notificationApi';
import { playAlertSound, isSoundEnabled, setSoundEnabled } from '../services/soundAlert';
import {
  isDesktopNotificationSupported,
  getDesktopPermissionState,
  requestDesktopNotificationPermission,
  showDesktopNotification
} from '../services/desktopNotification';

export const NOTIFICATION_CLASSIFICATION = {
  SECURITY_INCIDENT: 'SECURITY_INCIDENT',
  SYSTEM_FEEDBACK: 'SYSTEM_FEEDBACK'
};

export function useNotificationSocket({ onOpenIncident } = {}) {
  const [status, setStatus] = useState('idle'); // 'idle' | 'loading' | 'ready' | 'error' | 'unauthenticated'
  const [error, setError] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);
  const [attentionSeverity, setAttentionSeverity] = useState(null); // 'CRITICAL' | 'HIGH' | null
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'auth_error'
  const [toasts, setToasts] = useState([]);
  const [soundActive, setSoundActive] = useState(isSoundEnabled);
  const [desktopPermission, setDesktopPermission] = useState(getDesktopPermissionState);

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const attentionTimerRef = useRef(null);
  const isMountedRef = useRef(true);
  const lastReceivedIdRef = useRef(0);

  // Keep a stable ref to onOpenIncident so changes do not restart WebSocket connection
  const onOpenIncidentRef = useRef(onOpenIncident);
  useEffect(() => {
    onOpenIncidentRef.current = onOpenIncident;
  }, [onOpenIncident]);

  // Sync initial notifications and unread count from database via REST
  const refreshNotifications = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      if (isMountedRef.current) {
        setStatus('unauthenticated');
        setNotifications([]);
        setUnreadCount(0);
        setConnectionStatus('disconnected');
      }
      return;
    }

    try {
      if (isMountedRef.current) {
        setStatus((prev) => (prev === 'ready' ? 'ready' : 'loading'));
        setError(null);
      }
      const [listRes, countRes] = await Promise.all([
        fetchNotifications({ limit: 50 }),
        fetchUnreadCount()
      ]);
      if (isMountedRef.current) {
        const items = listRes.items || [];
        setNotifications(items);
        setUnreadCount(countRes.unread_count || 0);
        if (typeof countRes.active_incidents_count === 'number') {
          setActiveIncidentsCount(countRes.active_incidents_count);
        } else if (typeof listRes.active_incidents_count === 'number') {
          setActiveIncidentsCount(listRes.active_incidents_count);
        }
        if (items.length > 0) {
          const maxId = Math.max(...items.map((i) => i.id || 0));
          lastReceivedIdRef.current = Math.max(lastReceivedIdRef.current, maxId);
        }
        setStatus('ready');
      }
    } catch (err) {
      if (isMountedRef.current) {
        const msg = (err.message || '').toLowerCase();
        if (msg.includes('session expired') || msg.includes('authentication') || msg.includes('401')) {
          setStatus('unauthenticated');
          setConnectionStatus('auth_error');
        } else {
          setStatus('error');
          setError(err.message || 'Failed to load notifications');
        }
      }
      console.debug('[NotifHook] Initial notification load failed:', err.message);
    }
  }, []);

  // Delta recovery cursor: fetches notifications created after lastReceivedIdRef
  const recoverMissedNotifications = useCallback(async () => {
    const token = getAuthToken();
    if (!token) return;
    const sinceId = lastReceivedIdRef.current;
    if (!sinceId) {
      return refreshNotifications();
    }
    try {
      const [deltaRes, countRes] = await Promise.all([
        fetchNotifications({ since_id: sinceId, limit: 100 }),
        fetchUnreadCount()
      ]);
      if (isMountedRef.current) {
        const newItems = deltaRes.items || [];
        if (newItems.length > 0) {
          setNotifications((prev) => {
            const map = new Map();
            for (const item of newItems) map.set(item.id, item);
            for (const item of prev) {
              if (!map.has(item.id)) map.set(item.id, item);
            }
            const combined = Array.from(map.values());
            combined.sort((a, b) => (b.id || 0) - (a.id || 0));
            return combined;
          });
          const maxId = Math.max(...newItems.map((i) => i.id || 0));
          lastReceivedIdRef.current = Math.max(lastReceivedIdRef.current, maxId);
        }
        if (typeof countRes.unread_count === 'number') {
          setUnreadCount(countRes.unread_count);
        }
      }
    } catch (err) {
      console.debug('[NotifHook] Missed notification recovery fallback to full refresh:', err.message);
      refreshNotifications();
    }
  }, [refreshNotifications]);

  // Bell attention animation trigger (CRITICAL / HIGH incident alert)
  const triggerAttention = useCallback((severity) => {
    const sev = (severity || '').toUpperCase();
    if (sev !== 'CRITICAL' && sev !== 'HIGH') return;

    if (attentionTimerRef.current) clearTimeout(attentionTimerRef.current);
    setAttentionSeverity(sev);

    const duration = sev === 'CRITICAL' ? 3800 : 2800;
    attentionTimerRef.current = setTimeout(() => {
      if (isMountedRef.current) {
        setAttentionSeverity(null);
      }
    }, duration);
  }, []);

  const dismissToast = useCallback((toastId) => {
    setToasts((prev) => prev.filter((t) => t.id !== toastId));
  }, []);

  // System Feedback Toasts: STRICTLY reserved for non-security application feedback
  const showSystemFeedback = useCallback(({ title, message, type = 'info' }) => {
    const toastId = `feedback-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    const newFeedback = {
      id: toastId,
      classification: NOTIFICATION_CLASSIFICATION.SYSTEM_FEEDBACK,
      title,
      message,
      type,
      createdAt: Date.now()
    };
    setToasts((prev) => [newFeedback, ...prev].slice(0, 3));
    setTimeout(() => {
      dismissToast(toastId);
    }, 4000);
  }, [dismissToast]);

  const handleMarkRead = useCallback(async (id) => {
    try {
      // Optimistic UI update
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));

      // Server update
      const res = await markNotificationRead(id);
      if (res && typeof res.unread_count === 'number') {
        setUnreadCount(res.unread_count);
      }
    } catch (err) {
      console.error('[NotifHook] Mark read failed:', err);
      refreshNotifications();
    }
  }, [refreshNotifications]);

  const handleMarkAllRead = useCallback(async () => {
    try {
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
      await markAllNotificationsRead();
    } catch (err) {
      console.error('[NotifHook] Mark all read failed:', err);
      refreshNotifications();
    }
  }, [refreshNotifications]);

  const toggleSound = useCallback(() => {
    const next = !soundActive;
    setSoundActive(next);
    setSoundEnabled(next);
  }, [soundActive]);

  const requestDesktopPermission = useCallback(async () => {
    const state = await requestDesktopNotificationPermission();
    setDesktopPermission(state);
    return state;
  }, []);

  // WebSocket lifecycle & reconnection manager
  useEffect(() => {
    isMountedRef.current = true;
    const token = getAuthToken();

    if (!token) {
      setStatus('unauthenticated');
      setConnectionStatus('disconnected');
      return;
    }

    // Initial fetch from DB for authenticated user
    refreshNotifications();

    function connectWs() {
      if (!isMountedRef.current) return;
      const currentToken = getAuthToken();
      if (!currentToken) {
        setStatus('unauthenticated');
        setConnectionStatus('disconnected');
        return;
      }

      // Prevent opening duplicate socket if existing is CONNECTING or OPEN
      if (socketRef.current) {
        if (
          socketRef.current.readyState === WebSocket.OPEN ||
          socketRef.current.readyState === WebSocket.CONNECTING
        ) {
          return;
        }
        try {
          socketRef.current.close();
        } catch {}
      }

      const wsUrl = getNotificationWebSocketUrl(currentToken);
      setConnectionStatus((prev) => (prev === 'connected' ? 'reconnecting' : 'connecting'));

      try {
        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
          if (!isMountedRef.current) return;
          setConnectionStatus('connected');
          reconnectAttemptsRef.current = 0;

          // Ping heartbeat every 20 seconds
          if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping' }));
            }
          }, 20000);

          // Recover missed notification counts / items during disconnect
          recoverMissedNotifications();
        };

        ws.onmessage = (event) => {
          if (!isMountedRef.current) return;
          try {
            const data = JSON.parse(event.data);

            if (data.type === 'connection.ack') {
              if (typeof data.unread_count === 'number') {
                setUnreadCount(data.unread_count);
              }
            } else if (data.type === 'pong') {
              if (typeof data.unread_count === 'number') {
                setUnreadCount(data.unread_count);
              }
            } else if (data.type === 'error' && data.code === 1008) {
              setConnectionStatus('auth_error');
              setStatus('unauthenticated');
            } else if (data.type === 'notification.created') {
              const notif = data.notification;
              if (notif) {
                lastReceivedIdRef.current = Math.max(lastReceivedIdRef.current, notif.id || 0);

                // 1. Update notification list with stable deduplication by ID
                setNotifications((prev) => {
                  const filtered = prev.filter((item) => item.id !== notif.id);
                  return [notif, ...filtered];
                });

                // 2. Increment unread count
                if (typeof data.unread_count === 'number') {
                  setUnreadCount(data.unread_count);
                } else {
                  setUnreadCount((c) => c + 1);
                }

                // 3. Audio cue (respects user preference & autoplay)
                playAlertSound(notif.severity);

                // 4. Trigger subtle Bell Attention Pulse for CRITICAL / HIGH
                triggerAttention(notif.severity);

                // 5. Desktop OS notification (optional / permission-based)
                showDesktopNotification({
                  title: notif.title,
                  message: notif.message,
                  severity: notif.severity,
                  incidentId: notif.incident_id,
                  onClick: () => {
                    if (onOpenIncidentRef.current && notif.incident_id) {
                      onOpenIncidentRef.current(notif.incident_id);
                    }
                  }
                });
              }
            } else if (data.type === 'notification.read') {
              const notifId = data.notification_id;
              setNotifications((prev) =>
                prev.map((n) => (n.id === notifId ? { ...n, is_read: true } : n))
              );
              if (typeof data.unread_count === 'number') {
                setUnreadCount(data.unread_count);
              }
            } else if (data.type === 'notification.count') {
              if (typeof data.unread_count === 'number') {
                setUnreadCount(data.unread_count);
              }
            }
          } catch (jsonErr) {
            console.debug('[NotifHook] Non-critical parse error:', jsonErr);
          }
        };

        ws.onclose = (event) => {
          if (!isMountedRef.current) return;
          if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

          // If closed due to unauthorized code 1008, stop reconnect loop
          if (event.code === 1008) {
            setConnectionStatus('auth_error');
            setStatus('unauthenticated');
            return;
          }

          // If no token exists, do not attempt to reconnect
          if (!getAuthToken()) {
            setConnectionStatus('disconnected');
            setStatus('unauthenticated');
            return;
          }

          setConnectionStatus('reconnecting');

          // Bounded exponential backoff reconnect with jitter: 2s, 3s, up to 15s max
          const attempt = reconnectAttemptsRef.current;
          const baseDelay = Math.min(15000, 2000 * Math.pow(1.5, attempt));
          const jitter = Math.floor(Math.random() * 500);
          const delay = baseDelay + jitter;
          reconnectAttemptsRef.current += 1;

          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current && getAuthToken()) {
              connectWs();
            }
          }, delay);
        };

        ws.onerror = () => {
          try {
            ws.close();
          } catch {}
        };
      } catch (wsErr) {
        console.warn('[NotifHook] WebSocket creation error:', wsErr);
      }
    }

    connectWs();

    // Re-verify on visibility change (recovering from sleep/background tab)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        recoverMissedNotifications();
        if (
          !socketRef.current ||
          (socketRef.current.readyState !== WebSocket.OPEN &&
            socketRef.current.readyState !== WebSocket.CONNECTING)
        ) {
          connectWs();
        }
      }
    };

    // Re-verify on online network event
    const handleOnline = () => {
      setConnectionStatus('reconnecting');
      recoverMissedNotifications();
      connectWs();
    };

    const handleOffline = () => {
      setConnectionStatus('disconnected');
    };

    // Global unauthorized event
    const handleUnauthorizedEvent = () => {
      if (!isMountedRef.current) return;
      setStatus('unauthenticated');
      setConnectionStatus('auth_error');
      setNotifications([]);
      setUnreadCount(0);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) {
        try {
          socketRef.current.close();
        } catch {}
      }
    };

    // User logged in / switch account
    const handleAuthChanged = () => {
      if (!isMountedRef.current) return;
      reconnectAttemptsRef.current = 0;
      lastReceivedIdRef.current = 0;
      refreshNotifications();
      connectWs();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    window.addEventListener('prahari:unauthorized', handleUnauthorizedEvent);
    window.addEventListener('prahari:auth_changed', handleAuthChanged);

    return () => {
      isMountedRef.current = false;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('prahari:unauthorized', handleUnauthorizedEvent);
      window.removeEventListener('prahari:auth_changed', handleAuthChanged);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (attentionTimerRef.current) clearTimeout(attentionTimerRef.current);
      if (socketRef.current) {
        try {
          socketRef.current.close();
        } catch {}
      }
    };
  }, [refreshNotifications, recoverMissedNotifications, triggerAttention]);

  return {
    status,
    error,
    notifications,
    unreadCount,
    activeIncidentsCount,
    attentionSeverity,
    connectionStatus,
    toasts,
    soundActive,
    desktopPermission,
    dismissToast,
    showSystemFeedback,
    handleMarkRead,
    handleMarkAllRead,
    toggleSound,
    requestDesktopPermission,
    refreshNotifications,
    recoverMissedNotifications
  };
}
