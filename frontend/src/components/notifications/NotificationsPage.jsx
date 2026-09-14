import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ShieldAlert, AlertTriangle, Camera, Clock, Check, ExternalLink,
  RefreshCw, CheckCheck, ChevronLeft, ChevronRight, Search, ArrowLeft, Shield
} from 'lucide-react';
import {
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead
} from '../../services/notificationApi';

const SEVERITY_TABS = ['ALL', 'UNREAD', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export function NotificationsPage({ onNavigateToIncident, onBack }) {
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('tab') || 'ALL';
  });
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      let is_read = null;
      let severity = null;

      if (activeTab === 'UNREAD') {
        is_read = false;
      } else if (activeTab !== 'ALL') {
        severity = activeTab;
      }

      const offset = (page - 1) * pageSize;
      const res = await fetchNotifications({
        is_read,
        severity,
        limit: pageSize,
        offset
      });

      setItems(res.items || []);
      setTotalCount(res.total || 0);
      setUnreadCount(res.unread_count || 0);
      if (typeof res.active_incidents_count === 'number') {
        setActiveIncidentsCount(res.active_incidents_count);
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch notification history');
    } finally {
      setLoading(false);
    }
  }, [activeTab, page]);

  useEffect(() => {
    loadData();
    // Update URL query without reload
    const url = new URL(window.location);
    url.searchParams.set('tab', activeTab);
    window.history.replaceState({}, '', url);

    const handleAuth = () => {
      loadData();
    };
    window.addEventListener('prahari:auth_changed', handleAuth);
    window.addEventListener('prahari:unauthorized', handleAuth);
    return () => {
      window.removeEventListener('prahari:auth_changed', handleAuth);
      window.removeEventListener('prahari:unauthorized', handleAuth);
    };
  }, [loadData, activeTab]);

  const handleTabSelect = (tab) => {
    setActiveTab(tab);
    setPage(1);
  };

  const handleMarkSingleRead = async (id) => {
    try {
      await markNotificationRead(id);
      setItems((prev) =>
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
      setItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Mark all read failed:', err);
    }
  };

  const displayedItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase();
    return items.filter((item) => {
      const title = (item.title || '').toLowerCase();
      const message = (item.message || '').toLowerCase();
      const camera = (item.camera_id || '').toLowerCase();
      const code = (item.incident_code || (item.incident_id ? `inc-${item.incident_id}` : '')).toLowerCase();
      return title.includes(q) || message.includes(q) || camera.includes(q) || code.includes(q);
    });
  }, [items, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <div className="notif-page-container">
      {/* Header & Metrics (Phase 13) */}
      <div className="notif-page-header">
        <div className="notif-page-title-group">
          <div className="brand-logo" style={{ width: 42, height: 42, borderRadius: 8 }}>
            <ShieldAlert style={{ width: 22, height: 22 }} />
          </div>
          <div>
            <h1>Security Notifications</h1>
            <p className="notif-page-subtitle">
              Incident & Alert Center — Monitor security alerts, notification state, and incident response.
            </p>
          </div>
        </div>

        {/* Compact Metric Cards (Phase 13) */}
        <div className="soc-metrics-container">
          <div className="soc-metric-card accent-critical">
            <span className="soc-metric-label">Active Incidents</span>
            <span className="soc-metric-value">{activeIncidentsCount.toLocaleString()}</span>
          </div>
          <div className="soc-metric-card accent-primary">
            <span className="soc-metric-label">Unread Alerts</span>
            <span className="soc-metric-value">{unreadCount.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Notification Toolbar (Phases 14, 15, 18, 19, 20) */}
      <div className="notif-toolbar">
        <div className="notif-toolbar-left">
          <div className="search-input-wrapper" style={{ height: 40, width: '100%', minWidth: 260, maxWidth: 360 }}>
            <Search style={{ width: 14, height: 14, color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search alerts by camera, incident, or message..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search alerts"
            />
          </div>
        </div>

        {/* Filter Chips (Phase 15) */}
        <div className="notif-toolbar-center">
          <div className="filter-chips-group" role="tablist" aria-label="Alert severity filters">
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
                  className={`filter-chip ${activeTab === tab ? 'active' : ''}`}
                  onClick={() => handleTabSelect(tab)}
                  role="tab"
                  aria-selected={activeTab === tab}
                >
                  {labelMap[tab]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Action Controls (Phases 18, 19, 20) */}
        <div className="notif-toolbar-right">
          <button
            className="btn-secondary"
            onClick={handleMarkAllRead}
            disabled={unreadCount === 0}
            title={unreadCount === 0 ? 'No unread alerts' : 'Mark all notifications as read'}
            aria-label="Mark all as read"
          >
            <CheckCheck style={{ width: 14, height: 14 }} />
            <span>Mark all as read</span>
          </button>
          <button
            className="btn-secondary"
            onClick={loadData}
            title="Refresh alert feed"
            aria-label="Refresh alerts"
          >
            <RefreshCw style={{ width: 14, height: 14 }} className={loading ? 'spin-icon' : ''} />
            <span>Refresh</span>
          </button>
          {onBack && (
            <button
              className="btn-secondary"
              onClick={onBack}
              title="Return to Operations Dashboard"
              aria-label="Back to Operations Dashboard"
            >
              <ArrowLeft style={{ width: 14, height: 14 }} />
              <span>Back to Dashboard</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Table / List (Phases 16 & 17) */}
      <div className="notif-table-card">
        {error && (
          <div className="admin-error-box" style={{ margin: '16px' }}>
            <AlertTriangle style={{ width: 18, height: 18 }} />
            <span>{error}</span>
            <button className="btn-secondary" onClick={loadData}>Retry</button>
          </div>
        )}

        {loading ? (
          <div className="soc-empty-state">
            <RefreshCw className="spin-icon" style={{ width: 28, height: 28, color: 'var(--primary)' }} />
            <h3>Loading security alert history...</h3>
            <p>Fetching alerts from event database</p>
          </div>
        ) : displayedItems.length === 0 ? (
          <div className="soc-empty-state">
            <ShieldAlert style={{ width: 40, height: 40, color: 'var(--text-muted)', opacity: 0.35 }} />
            <h3>No notifications found</h3>
            <p>
              There are no notifications matching the current filter ({activeTab})
              {searchQuery ? ` and search "${searchQuery}"` : ''}.
            </p>
            {(activeTab !== 'ALL' || searchQuery) && (
              <button
                className="btn-secondary"
                onClick={() => {
                  setActiveTab('ALL');
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
                  <th style={{ width: '130px', textAlign: 'center' }}>Incident</th>
                  <th style={{ width: '160px', textAlign: 'left' }}>Time</th>
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
                                if (onNavigateToIncident) {
                                  onNavigateToIncident(item.incident_id || incidentCode);
                                }
                              }}
                              title={`Open details for ${incidentCode}`}
                              aria-label={`Open ${incidentCode}`}
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

        {/* Pagination Bar */}
        {totalCount > pageSize && (
          <div className="notif-pagination-bar">
            <span className="pagination-info">
              Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalCount)} of {totalCount} alerts
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
              <span className="page-counter">Page {page} of {totalPages}</span>
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
  );
}
