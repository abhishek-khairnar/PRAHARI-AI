import React from 'react';
import { Bell } from 'lucide-react';

export function NotificationBell({
  unreadCount = 0,
  connectionStatus = 'disconnected',
  attentionSeverity = null,
  isOpen = false,
  onToggle
}) {
  let statusTitle = 'Real-time notifications active';
  let statusDotColor = 'var(--status-live, #10b981)';
  if (connectionStatus === 'connected') {
    statusTitle = 'Real-time notifications active';
    statusDotColor = '#10b981';
  } else if (connectionStatus === 'reconnecting') {
    statusTitle = 'Reconnecting live alert stream...';
    statusDotColor = '#f59e0b';
  } else if (connectionStatus === 'connecting') {
    statusTitle = 'Connecting live alert stream...';
    statusDotColor = '#f59e0b';
  } else if (connectionStatus === 'auth_error') {
    statusTitle = 'Session expired — authentication required';
    statusDotColor = '#ef4444';
  } else {
    statusTitle = 'Live alert stream disconnected (persisted history available)';
    statusDotColor = '#94a3b8';
  }

  let attentionClass = '';
  if (attentionSeverity === 'CRITICAL') {
    attentionClass = 'attention-critical';
  } else if (attentionSeverity === 'HIGH') {
    attentionClass = 'attention-high';
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (onToggle) onToggle();
    }
  };

  return (
    <button
      className={`btn-header notification-bell-btn ${isOpen ? 'active' : ''} ${attentionClass}`}
      onClick={onToggle}
      onKeyDown={handleKeyDown}
      title={`Security Notifications (${unreadCount} unread) · ${statusTitle}${attentionSeverity ? ` · [NEW ${attentionSeverity} ALERT]` : ''}`}
      aria-label={`Security Notifications (${unreadCount} unread)${attentionSeverity ? ` - New ${attentionSeverity} incident` : ''}`}
      aria-expanded={isOpen}
      type="button"
    >
      <div className="bell-icon-wrapper">
        <Bell style={{ width: 17, height: 17 }} />
        {/* Connection status micro-dot */}
        <span
          className="notif-connection-dot"
          style={{
            backgroundColor: statusDotColor
          }}
          title={statusTitle}
        />
      </div>

      <span className="notif-label">Alerts</span>

      {unreadCount > 0 && (
        <span className="notif-unread-badge" aria-label={`${unreadCount} unread`}>
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  );
}

