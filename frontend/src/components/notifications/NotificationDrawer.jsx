import React, { useState, useMemo, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  X, CheckCheck, Volume2, VolumeX, Bell, AlertTriangle,
  ShieldAlert, ExternalLink, Check, Clock, Camera
} from 'lucide-react';

export function NotificationDrawer({
  isOpen = false,
  onClose,
  status = 'ready', // 'idle' | 'loading' | 'ready' | 'error' | 'unauthenticated'
  error = null,
  onRetry,
  onNavigateToLogin,
  notifications = [],
  unreadCount = 0,
  activeIncidentsCount = 0,
  connectionStatus = 'disconnected', // 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'auth_error'
  soundActive = true,
  onToggleSound,
  desktopPermission = 'default',
  onRequestDesktopPermission,
  onMarkRead,
  onMarkAllRead,
  onOpenIncident,
  onViewAll
}) {
  const [filter, setFilter] = useState('all'); // 'all' | 'unread' | 'critical' | 'high' | 'medium'

  // Keyboard accessibility: Escape key closes drawer
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (onClose) onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const filteredNotifications = useMemo(() => {
    return notifications.filter((item) => {
      if (filter === 'unread') return !item.is_read;
      if (filter === 'critical') return item.severity === 'CRITICAL';
      if (filter === 'high') return item.severity === 'HIGH';
      if (filter === 'medium') return item.severity === 'MEDIUM';
      return true;
    });
  }, [notifications, filter]);

  if (!isOpen) return null;

  // Determine connection status indicator & label
  let statusText = 'Live alerts connected';
  let statusClass = 'status-online';
  if (connectionStatus === 'reconnecting') {
    statusText = 'Reconnecting live alerts…';
    statusClass = 'status-reconnecting';
  } else if (connectionStatus === 'connecting') {
    statusText = 'Connecting live alerts…';
    statusClass = 'status-reconnecting';
  } else if (connectionStatus === 'auth_error') {
    statusText = 'Session expired — sign in again';
    statusClass = 'status-auth-error';
  } else if (connectionStatus === 'disconnected') {
    if (status === 'unauthenticated') {
      statusText = 'Sign in required to view alerts';
      statusClass = 'status-offline';
    } else {
      statusText = 'Live alerts unavailable — history still available';
      statusClass = 'status-offline';
    }
  }

  // Non-modal right-side command panel (NO pointer-blocking backdrop overlay)
  const drawerContent = (
    <aside
      className="notif-drawer-panel"
      role="region"
      aria-label="Security Notifications Center"
    >
      {/* Drawer Header */}
      <div className="notif-drawer-header">
        <div className="notif-drawer-title-group">
          <div className="notif-title-row">
            <ShieldAlert style={{ width: 18, height: 18, color: '#0284C7' }} />
            <h2>Security Notifications</h2>
          </div>
          <div className="notif-counters-group">
            {activeIncidentsCount > 0 && (
              <span className="active-incidents-badge" title="Active unresolved incidents">
                {activeIncidentsCount} Active Incidents
              </span>
            )}
            <span className="unread-notifs-badge" title="Unread notifications">
              {unreadCount} Unread
            </span>
          </div>
          <div className="notif-status-line">
            <span className={`notif-status-dot ${statusClass}`} />
            <span>{statusText}</span>
          </div>
        </div>

        <div className="notif-drawer-header-actions">
          {unreadCount > 0 && status !== 'unauthenticated' && (
            <button
              className="btn-notif-action"
              onClick={onMarkAllRead}
              title="Mark all notifications as read"
              aria-label="Mark all notifications as read"
            >
              <CheckCheck style={{ width: 14, height: 14 }} />
              <span>Mark All Read</span>
            </button>
          )}
          <button
            className="btn-notif-close"
            onClick={onClose}
            title="Close notification panel (Esc)"
            aria-label="Close notification panel"
          >
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>
      </div>

      {/* Quick Preferences Bar */}
      <div className="notif-quick-bar">
        <button
          className={`btn-quick-pref ${soundActive ? 'active' : ''}`}
          onClick={onToggleSound}
          title={soundActive ? 'Audio alerts enabled · Click to mute' : 'Audio alerts muted · Click to unmute'}
          aria-label={soundActive ? 'Mute alert audio' : 'Unmute alert audio'}
        >
          {soundActive ? <Volume2 style={{ width: 14, height: 14 }} /> : <VolumeX style={{ width: 14, height: 14 }} />}
          <span>{soundActive ? 'Sound On' : 'Muted'}</span>
        </button>

        {desktopPermission !== 'granted' && (
          <button
            className="btn-quick-pref btn-quick-desktop"
            onClick={onRequestDesktopPermission}
            title="Enable native desktop alerts"
            aria-label="Enable native desktop alerts"
          >
            <Bell style={{ width: 14, height: 14 }} />
            <span>Enable Desktop Alerts</span>
          </button>
        )}

        {desktopPermission === 'granted' && (
          <div className="notif-desktop-granted" title="Desktop notifications enabled">
            <Check style={{ width: 13, height: 13 }} />
            <span>Desktop Active</span>
          </div>
        )}
      </div>

      {/* Filter Tabs */}
      <div className="notif-filter-tabs" role="tablist" aria-label="Filter notifications by severity">
        <button
          className={`notif-tab ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
          role="tab"
          aria-selected={filter === 'all'}
        >
          All ({notifications.length})
        </button>
        <button
          className={`notif-tab ${filter === 'unread' ? 'active' : ''}`}
          onClick={() => setFilter('unread')}
          role="tab"
          aria-selected={filter === 'unread'}
        >
          Unread ({unreadCount})
        </button>
        <button
          className={`notif-tab ${filter === 'critical' ? 'active' : ''}`}
          onClick={() => setFilter('critical')}
          role="tab"
          aria-selected={filter === 'critical'}
        >
          Critical
        </button>
        <button
          className={`notif-tab ${filter === 'high' ? 'active' : ''}`}
          onClick={() => setFilter('high')}
          role="tab"
          aria-selected={filter === 'high'}
        >
          High
        </button>
        <button
          className={`notif-tab ${filter === 'medium' ? 'active' : ''}`}
          onClick={() => setFilter('medium')}
          role="tab"
          aria-selected={filter === 'medium'}
        >
          Medium
        </button>
      </div>

      {/* Persistent notifications warning if refresh failed but cache exists */}
      {status === 'error' && notifications.length > 0 && (
        <div style={{
          background: '#FEF2F2',
          borderBottom: '1px solid #FECACA',
          color: '#B91C1C',
          padding: '0.45rem 1.25rem',
          fontSize: '0.74rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0
        }}>
          <span>Unable to refresh live alerts. Displaying cached history.</span>
          {onRetry && (
            <button
              onClick={onRetry}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#B91C1C',
                fontWeight: 700,
                cursor: 'pointer',
                textDecoration: 'underline',
                fontSize: '0.74rem'
              }}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* Notifications List or Dedicated State Panels */}
      <div className="notif-list-container">
        {status === 'unauthenticated' ? (
          <div className="notif-auth-required-box">
            <ShieldAlert style={{ width: 40, height: 40, color: '#F59E0B' }} />
            <h3>Authentication Required</h3>
            <p>Security incident notifications are restricted to authorized personnel. Please sign in to view and acknowledge perimeter alerts.</p>
            {onNavigateToLogin && (
              <button
                className="btn-header btn-primary"
                onClick={() => {
                  if (onClose) onClose();
                  onNavigateToLogin();
                }}
                style={{ marginTop: '14px', padding: '0.5rem 1.25rem', fontWeight: 600 }}
              >
                Sign In to View Alerts
              </button>
            )}
          </div>
        ) : status === 'loading' && notifications.length === 0 ? (
          <div className="notif-loading-state">
            <Clock className="spin-icon" style={{ width: 34, height: 34, color: '#0284C7' }} />
            <p>Loading security notification history...</p>
            <span>Fetching alerts from event database</span>
          </div>
        ) : status === 'error' && notifications.length === 0 ? (
          <div className="notif-error-state">
            <AlertTriangle style={{ width: 34, height: 34, color: '#EF4444' }} />
            <p>Unable to load notification history</p>
            <span>{error || 'Database or network communication error'}</span>
            {onRetry && (
              <button
                className="btn-notif-action"
                onClick={onRetry}
                style={{ marginTop: '14px', padding: '0.45rem 1.1rem' }}
              >
                Retry Request
              </button>
            )}
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="notif-empty-state">
            <AlertTriangle style={{ width: 32, height: 32, opacity: 0.4 }} />
            <p>No {filter !== 'all' ? filter : ''} notifications</p>
            <span>Surveillance perimeter operations normal</span>
          </div>
        ) : (
          filteredNotifications.map((item) => {
            const sev = (item.severity || 'HIGH').toUpperCase();
            const isUnread = !item.is_read;
            const incidentCode = item.incident_code || (item.incident_id ? `INC-${String(item.incident_id).padStart(4, '0')}` : null);

            return (
              <div
                key={item.id}
                className={`notif-card sev-${sev.toLowerCase()} ${isUnread ? 'is-unread' : 'is-read'}`}
              >
                <div className="notif-card-header">
                  <div className="notif-sev-pill">
                    <span className="sev-text">{sev}</span>
                  </div>

                  <div className="notif-meta-tags">
                    {item.camera_id && (
                      <span className="notif-tag camera-tag">
                        <Camera style={{ width: 11, height: 11 }} />
                        {item.camera_id}
                      </span>
                    )}
                    {incidentCode && (
                      <span className="notif-tag incident-tag">
                        {incidentCode}
                      </span>
                    )}
                  </div>

                  <div className="notif-time" title={item.created_at}>
                    <Clock style={{ width: 11, height: 11 }} />
                    <span>{formatTimeAgo(item.created_at)}</span>
                  </div>
                </div>

                <div className="notif-card-body">
                  <h4 className="notif-card-title">{item.title}</h4>
                  <p className="notif-card-message">{item.message}</p>
                </div>

                <div className="notif-card-footer">
                  {incidentCode && (
                    <button
                      className="btn-notif-open"
                      onClick={() => {
                        if (onOpenIncident) onOpenIncident(item.incident_id || incidentCode);
                        if (onClose) onClose();
                      }}
                      title="Navigate to incident investigation view"
                    >
                      <ExternalLink style={{ width: 12, height: 12 }} />
                      <span>Open Incident</span>
                    </button>
                  )}

                  {isUnread && (
                    <button
                      className="btn-notif-mark"
                      onClick={() => onMarkRead(item.id)}
                      title="Mark as read"
                      aria-label="Mark notification as read"
                    >
                      <Check style={{ width: 12, height: 12 }} />
                      <span>Mark Read</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Drawer Footer */}
      {onViewAll && (
        <div className="notif-drawer-footer">
          <button
            className="btn-notif-view-all"
            onClick={() => {
              if (onClose) onClose();
              onViewAll();
            }}
          >
            <span>View Full Notification History</span>
            <ExternalLink style={{ width: 14, height: 14 }} />
          </button>
        </div>
      )}
    </aside>
  );

  return typeof document !== 'undefined'
    ? createPortal(drawerContent, document.body)
    : drawerContent;
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return '';
  try {
    const date = new Date(dateStr.replace(' ', 'T'));
    if (isNaN(date.getTime())) return dateStr.split(' ')[1] || dateStr;
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 10) return 'Just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}
