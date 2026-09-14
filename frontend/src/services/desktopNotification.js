/**
 * PRAHARI-AI Desktop OS Notification Service
 * Integrates native HTML5 Notification API with user opt-in guard.
 */

export function isDesktopNotificationSupported() {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function getDesktopPermissionState() {
  if (!isDesktopNotificationSupported()) return 'unsupported';
  return Notification.permission; // 'default' | 'granted' | 'denied'
}

/**
 * Request notification permission strictly upon explicit user interaction.
 */
export async function requestDesktopNotificationPermission() {
  if (!isDesktopNotificationSupported()) return 'unsupported';

  try {
    const permission = await Notification.requestPermission();
    return permission;
  } catch (err) {
    console.warn('[DesktopNotification] Permission request failed:', err);
    return Notification.permission || 'denied';
  }
}

/**
 * Display a desktop notification for CRITICAL or HIGH operational alerts.
 */
export function showDesktopNotification({ title, message, severity, incidentId, onClick }) {
  if (!isDesktopNotificationSupported() || Notification.permission !== 'granted') {
    return null;
  }

  try {
    const icon = severity === 'CRITICAL' ? '🚨' : '⚠️';
    const notif = new Notification(`${icon} [${severity}] ${title}`, {
      body: message,
      tag: incidentId ? `prahari-inc-${incidentId}` : undefined,
      requireInteraction: severity === 'CRITICAL',
      silent: true // Tone handled by Web Audio API to prevent duplicate sound
    });

    notif.onclick = () => {
      window.focus();
      if (onClick) onClick();
      notif.close();
    };

    return notif;
  } catch (err) {
    console.debug('[DesktopNotification] Native notification suppressed:', err);
    return null;
  }
}
