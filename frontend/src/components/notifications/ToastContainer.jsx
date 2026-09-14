import React from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

/**
 * ToastContainer: Exclusively for non-security SYSTEM_FEEDBACK.
 * SECURITY INCIDENTS ARE STRICTLY FORBIDDEN from rendering here.
 * Real-time security incidents are routed to NotificationBell and NotificationDrawer.
 */
export function ToastContainer({ toasts = [], onDismiss }) {
  // Strict filter: exclude any security incident or legacy notification alert
  const systemFeedbackToasts = (toasts || []).filter((item) => {
    if (!item) return false;
    // Discard any security notifications
    if (item.notification || item.incident_id || item.source_event_id) return false;
    const sev = (item.severity || '').toUpperCase();
    if (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(sev)) return false;
    return true;
  });

  if (systemFeedbackToasts.length === 0) return null;

  const content = (
    <div className="system-feedback-viewport" aria-live="polite" role="status">
      {systemFeedbackToasts.map((toast) => {
        const type = toast.type || 'info';
        let Icon = Info;
        if (type === 'success') Icon = CheckCircle2;
        else if (type === 'error') Icon = AlertCircle;

        return (
          <div
            key={toast.id}
            className={`system-feedback-card type-${type}`}
            role="status"
          >
            <Icon style={{ width: 16, height: 16, flexShrink: 0, color: type === 'success' ? '#10B981' : type === 'error' ? '#DC2626' : '#0284C7' }} />
            <span className="system-feedback-text">
              {toast.title ? <strong>{toast.title}: </strong> : null}
              {toast.message || toast.title}
            </span>
            <button
              className="system-feedback-close"
              onClick={() => onDismiss && onDismiss(toast.id)}
              aria-label="Dismiss feedback"
              title="Dismiss"
            >
              <X style={{ width: 14, height: 14 }} />
            </button>
          </div>
        );
      })}
    </div>
  );

  return typeof document !== 'undefined'
    ? createPortal(content, document.body)
    : content;
}

