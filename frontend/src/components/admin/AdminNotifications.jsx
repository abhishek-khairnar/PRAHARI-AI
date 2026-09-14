import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Bell, Volume2, VolumeX, Shield, CheckCircle2, AlertTriangle,
  Save, RefreshCw, Smartphone, Laptop, Search, Filter,
  Check, CheckCheck, ExternalLink, ChevronLeft, ChevronRight,
  ShieldAlert, Camera, Clock
} from 'lucide-react';
import {
  fetchNotifications,
  fetchUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  fetchNotificationPreferences,
  updateNotificationPreferences
} from '../../services/notificationApi';
import {
  isDesktopNotificationSupported,
  getDesktopPermissionState,
  requestDesktopNotificationPermission
} from '../../services/desktopNotification';

const SEVERITY_TABS = ['ALL', 'UNREAD', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export function AdminNotifications({ currentUser, onNavigate }) {
  const [activeViewTab, setActiveViewTab] = useState('center'); // 'center' | 'settings'

  // ─── Notification Center State ───
  const [notifItems, setNotifItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);
  const [centerLoading, setCenterLoading] = useState(true);
  const [centerError, setCenterError] = useState(null);
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // ─── Settings State ───
  const [prefs, setPrefs] = useState({
    critical_enabled: true,
    high_enabled: true,
    medium_enabled: true,
    low_enabled: false,
    sound_enabled: true,
    browser_enabled: false,
    web_push_enabled: false
  });
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [settingsError, setSettingsError] = useState(null);
  const [desktopState, setDesktopState] = useState(getDesktopPermissionState);

  // ─── Load Notification Center Data ───
  const loadNotificationsData = useCallback(async () => {
    try {
      setCenterLoading(true);
      setCenterError(null);

      let is_read = null;
      let severity = null;

      if (severityFilter === 'UNREAD') {
        is_read = false;
      } else if (severityFilter !== 'ALL') {
        severity = severityFilter;
      }

      const offset = (page - 1) * pageSize;
      const res = await fetchNotifications({
        is_read,
        severity,
        limit: pageSize,
        offset
      });

      setNotifItems(res.items || []);
      setTotalCount(res.total || 0);
      setUnreadCount(res.unread_count || 0);
      if (typeof res.active_incidents_count === 'number') {
        setActiveIncidentsCount(res.active_incidents_count);
      }
    } catch (err) {
      setCenterError(err.message || 'Failed to load notifications history');
    } finally {
      setCenterLoading(false);
    }
  }, [severityFilter, page]);

  // ─── Load Preferences Data ───
  const loadPreferences = useCallback(async () => {
    try {
      setSettingsLoading(true);
      setSettingsError(null);
      const data = await fetchNotificationPreferences();
      setPrefs({
        critical_enabled: data.critical_enabled ?? true,
        high_enabled: data.high_enabled ?? true,
        medium_enabled: data.medium_enabled ?? true,
        low_enabled: data.low_enabled ?? false,
        sound_enabled: data.sound_enabled ?? true,
        browser_enabled: data.browser_enabled ?? false,
        web_push_enabled: data.web_push_enabled ?? false
      });
    } catch (err) {
      setSettingsError(err.message || 'Failed to load preferences');
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNotificationsData();
  }, [loadNotificationsData]);

  useEffect(() => {
    if (activeViewTab === 'settings') {
      loadPreferences();
    }
  }, [activeViewTab, loadPreferences]);

  // Client-side search filter over page items
  const displayedItems = useMemo(() => {
    if (!searchQuery.trim()) return notifItems;
    const q = searchQuery.toLowerCase();
    return notifItems.filter((item) => {
      const title = (item.title || '').toLowerCase();
      const message = (item.message || '').toLowerCase();
      const camera = (item.camera_id || '').toLowerCase();
      const code = (item.incident_code || (item.incident_id ? `inc-${item.incident_id}` : '')).toLowerCase();
      return title.includes(q) || message.includes(q) || camera.includes(q) || code.includes(q);
    });
  }, [notifItems, searchQuery]);

  // Center Actions
  const handleMarkSingleRead = async (id) => {
    try {
      await markNotificationRead(id);
      setNotifItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, is_read: true } : item))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error('Mark read failed:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Mark all read failed:', err);
    }
  };

  // Settings Actions
  const handleTogglePref = (key) => {
    setPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
    setSaveSuccess(false);
  };

  const handleSaveSettings = async () => {
    try {
      setSaving(true);
      setSettingsError(null);
      await updateNotificationPreferences(prefs);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSettingsError(err.message || 'Failed to update preferences');
    } finally {
      setSaving(false);
    }
  };

  const handleRequestDesktop = async () => {
    const res = await requestDesktopNotificationPermission();
    setDesktopState(res);
    if (res === 'granted') {
      setPrefs((prev) => ({ ...prev, browser_enabled: true }));
    }
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <div className="notif-center-shell">
      {/* Top Nav Tabs Bar: [ Notification Center ] [ Settings ] */}
      <div className="notif-nav-tabs-bar" role="tablist" aria-label="Notification Views">
        <button
          className={`btn-notif-nav-tab ${activeViewTab === 'center' ? 'active' : ''}`}
          onClick={() => setActiveViewTab('center')}
          role="tab"
          aria-selected={activeViewTab === 'center'}
        >
          <Bell style={{ width: 16, height: 16 }} />
          <span>Notification Center</span>
          {unreadCount > 0 && (
            <span className="notif-unread-badge" style={{ marginLeft: 4 }}>
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>
        <button
          className={`btn-notif-nav-tab ${activeViewTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveViewTab('settings')}
          role="tab"
          aria-selected={activeViewTab === 'settings'}
        >
          <Shield style={{ width: 16, height: 16 }} />
          <span>Alert Settings</span>
        </button>
      </div>

      {/* ─── TAB 1: NOTIFICATION CENTER ─── */}
      {activeViewTab === 'center' && (
        <div className="notif-center-view">
          {/* Controls Bar (Phases 14, 15, 19, 20) */}
          <div className="notif-toolbar" style={{ margin: '0 0 16px 0' }}>
            <div className="notif-toolbar-left">
              <div className="search-input-wrapper" style={{ height: 40, width: '100%', minWidth: 260, maxWidth: 360 }}>
                <Search style={{ width: 14, height: 14, color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search camera, incident ID, or alert..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search notifications"
                />
              </div>
            </div>

            <div className="notif-toolbar-center">
              <div className="filter-chips-group" role="tablist" aria-label="Severity filter">
                {SEVERITY_TABS.map((tab) => {
                  const labelMap = {
                    ALL: 'All',
                    UNREAD: unreadCount > 0 ? `Unread (${unreadCount.toLocaleString()})` : 'Unread',
                    CRITICAL: 'Critical',
                    HIGH: 'High',
                    MEDIUM: 'Medium',
                    LOW: 'Low'
                  };
                  return (
                    <button
                      key={tab}
                      className={`filter-chip ${severityFilter === tab ? 'active' : ''}`}
                      onClick={() => {
                        setSeverityFilter(tab);
                        setPage(1);
                      }}
                      role="tab"
                      aria-selected={severityFilter === tab}
                    >
                      {labelMap[tab]}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="notif-toolbar-right">
              <button
                className="btn-secondary"
                onClick={handleMarkAllRead}
                disabled={unreadCount === 0}
                title={unreadCount === 0 ? 'No unread notifications' : 'Mark all notifications as read'}
                aria-label="Mark all as read"
              >
                <CheckCheck style={{ width: 14, height: 14 }} />
                <span>Mark all as read</span>
              </button>
              <button
                className="btn-secondary"
                onClick={loadNotificationsData}
                title="Refresh notifications list"
                aria-label="Refresh notifications"
              >
                <RefreshCw style={{ width: 14, height: 14 }} className={centerLoading ? 'spin-icon' : ''} />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {centerError && (
            <div className="admin-error-box" style={{ marginBottom: '16px' }}>
              <AlertTriangle style={{ width: 18, height: 18 }} />
              <span>{centerError}</span>
              <button className="btn-secondary" onClick={loadNotificationsData}>Retry</button>
            </div>
          )}

          {/* Main Table Card (Phases 16 & 17) */}
          <div className="notif-table-card">
            {centerLoading ? (
              <div className="soc-empty-state">
                <RefreshCw className="spin-icon" style={{ width: 28, height: 28, color: 'var(--primary)' }} />
                <h3>Loading notification records...</h3>
                <p>Retrieving recent operational alerts</p>
              </div>
            ) : displayedItems.length === 0 ? (
              <div className="soc-empty-state">
                <ShieldAlert style={{ width: 40, height: 40, color: 'var(--text-muted)', opacity: 0.35 }} />
                <h3>No notifications found</h3>
                <p>
                  No security incidents match the filter "{severityFilter}"
                  {searchQuery ? ` and search "${searchQuery}"` : ''}.
                </p>
                {(severityFilter !== 'ALL' || searchQuery) && (
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      setSeverityFilter('ALL');
                      setSearchQuery('');
                      setPage(1);
                    }}
                    style={{ marginTop: 8 }}
                  >
                    Clear Filters
                  </button>
                )}
              </div>
            ) : (
              <div className="notif-table-wrapper">
                <table className="notif-table">
                  <thead>
                    <tr>
                      <th style={{ width: '110px', textAlign: 'center' }}>Severity</th>
                      <th style={{ textAlign: 'left' }}>Alert</th>
                      <th style={{ width: '110px', textAlign: 'center' }}>Camera</th>
                      <th style={{ width: '130px', textAlign: 'center' }}>Incident ID</th>
                      <th style={{ width: '160px', textAlign: 'left' }}>Timestamp</th>
                      <th style={{ width: '90px', textAlign: 'center' }}>Status</th>
                      <th style={{ width: '150px', textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedItems.map((item) => {
                      const sev = (item.severity || 'HIGH').toUpperCase();
                      const isUnread = !item.is_read;
                      const incidentCode =
                        item.incident_code ||
                        (item.incident_id ? `INC-${String(item.incident_id).padStart(4, '0')}` : null);

                      return (
                        <tr key={item.id} className={isUnread ? 'row-unread' : 'row-read'}>
                          <td style={{ textAlign: 'center' }}>
                            <span className={`notif-sev-pill sev-${sev.toLowerCase()}`}>
                              {sev}
                            </span>
                          </td>
                          <td style={{ textAlign: 'left' }}>
                            <div className="notif-cell-text">
                              <span className="notif-title-line">{item.title}</span>
                              <span className="notif-sub-line">{item.message}</span>
                            </div>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span className="cam-badge">
                              {item.camera_id || 'System'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            {incidentCode ? (
                              <span className="incident-code-badge">
                                {incidentCode}
                              </span>
                            ) : (
                              <span style={{ color: 'var(--text-disabled)' }}>—</span>
                            )}
                          </td>
                          <td style={{ textAlign: 'left' }}>
                            <span className="notif-time-text" title={item.created_at}>
                              {item.created_at}
                            </span>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span className={`notif-read-state ${isUnread ? 'state-unread' : 'state-read'}`}>
                              {isUnread ? 'Unread' : 'Read'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div className="notif-action-cell" style={{ justifyContent: 'flex-end' }}>
                              {incidentCode && (
                                <button
                                  className="btn-table-action"
                                  onClick={() => {
                                    if (onNavigate) {
                                      onNavigate('incidents');
                                    } else {
                                      window.location.href = '/admin/incidents';
                                    }
                                  }}
                                  title={`Investigate ${incidentCode} in Admin Incidents`}
                                  aria-label={`Investigate ${incidentCode}`}
                                >
                                  <ExternalLink style={{ width: 13, height: 13 }} />
                                  <span>Incident</span>
                                </button>
                              )}
                              {isUnread && (
                                <button
                                  className="btn-icon btn-mark-read"
                                  onClick={() => handleMarkSingleRead(item.id)}
                                  title="Mark as read"
                                  aria-label="Mark as read"
                                >
                                  <Check style={{ width: 14, height: 14 }} />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {totalCount > pageSize && (
              <div className="notif-pagination-bar">
                <span className="pagination-info">
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalCount)} of {totalCount} notifications
                </span>
                <div className="pagination-buttons">
                  <button
                    className="btn-page"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft style={{ width: 14, height: 14 }} />
                    <span>Prev</span>
                  </button>
                  <span className="page-counter">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    className="btn-page"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    <span>Next</span>
                    <ChevronRight style={{ width: 14, height: 14 }} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── TAB 2: ALERT SETTINGS (WCAG AA High Contrast) ─── */}
      {activeViewTab === 'settings' && (
        <div className="notif-settings-view">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#111827', margin: 0 }}>
                Notification & Alert Preferences
              </h2>
              <p style={{ fontSize: '0.8rem', color: '#475569', margin: '4px 0 0 0' }}>
                Configure severity subscription filters and dispatch delivery channels
              </p>
            </div>
            <button
              className="btn-header btn-primary"
              onClick={handleSaveSettings}
              disabled={saving}
            >
              <Save style={{ width: 15, height: 15 }} />
              <span>{saving ? 'Saving...' : 'Save Preferences'}</span>
            </button>
          </div>

          {saveSuccess && (
            <div className="admin-success-banner">
              <CheckCircle2 style={{ width: 16, height: 16 }} />
              <span>Notification preferences successfully updated!</span>
            </div>
          )}

          {settingsError && (
            <div className="admin-error-banner">
              <AlertTriangle style={{ width: 16, height: 16 }} />
              <span>{settingsError}</span>
            </div>
          )}

          <div className="notif-settings-grid">
            {/* Section 1: Severity Thresholds */}
            <div className="notif-settings-section">
              <h3>
                <Shield style={{ width: 18, height: 18, color: '#0284C7' }} />
                <span>Severity Thresholds</span>
              </h3>
              <p className="section-desc">
                Select which incident severities trigger real-time attention signals and unread count badges for your user session ({currentUser?.role || 'OFFICER'}).
              </p>

              <div className="pref-toggle-list">
                <label className="pref-toggle-item">
                  <div className="pref-info">
                    <span className="pref-title text-critical">Critical Incidents</span>
                    <span className="pref-sub">Perimeter crossings, active virtual-fence boundary intrusions</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.critical_enabled}
                    onChange={() => handleTogglePref('critical_enabled')}
                    aria-label="Toggle Critical incidents"
                  />
                </label>

                <label className="pref-toggle-item">
                  <div className="pref-info">
                    <span className="pref-title text-high">High Severity Alerts</span>
                    <span className="pref-sub">Night movement, suspicious loitering, after-hours presence</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.high_enabled}
                    onChange={() => handleTogglePref('high_enabled')}
                    aria-label="Toggle High severity alerts"
                  />
                </label>

                <label className="pref-toggle-item">
                  <div className="pref-info">
                    <span className="pref-title text-medium">Medium Severity</span>
                    <span className="pref-sub">ANPR license plate recognition events and vehicle tracking</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.medium_enabled}
                    onChange={() => handleTogglePref('medium_enabled')}
                    aria-label="Toggle Medium severity alerts"
                  />
                </label>

                <label className="pref-toggle-item">
                  <div className="pref-info">
                    <span className="pref-title">Low / Informational</span>
                    <span className="pref-sub">System diagnostics, camera reconnects, health heartbeats</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.low_enabled}
                    onChange={() => handleTogglePref('low_enabled')}
                    aria-label="Toggle Low informational alerts"
                  />
                </label>
              </div>
            </div>

            {/* Section 2: Delivery Channels */}
            <div className="notif-settings-section">
              <h3>
                <Bell style={{ width: 18, height: 18, color: '#0284C7' }} />
                <span>Delivery Channels & Attention</span>
              </h3>
              <p className="section-desc">
                Manage audio alert chimes and native OS desktop push notifications.
              </p>

              <div className="pref-toggle-list">
                <label className="pref-toggle-item">
                  <div className="pref-info">
                    <span className="pref-title">Sound Alerts & Chimes</span>
                    <span className="pref-sub">Synthesized audio cues tailored to alert urgency (plays once per newly created notification)</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.sound_enabled}
                    onChange={() => handleTogglePref('sound_enabled')}
                    aria-label="Toggle Sound alerts"
                  />
                </label>

                <div className="pref-toggle-item">
                  <div className="pref-info">
                    <span className="pref-title">Desktop Browser Notifications</span>
                    <span className="pref-sub">
                      OS permission state: <strong>{desktopState.toUpperCase()}</strong>
                    </span>
                  </div>
                  {desktopState !== 'granted' ? (
                    <button
                      type="button"
                      className="btn-header"
                      onClick={handleRequestDesktop}
                      title="Request browser desktop notification permission"
                    >
                      <Laptop style={{ width: 14, height: 14 }} />
                      <span>Request Permission</span>
                    </button>
                  ) : (
                    <span className="desktop-granted-pill">Active</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
