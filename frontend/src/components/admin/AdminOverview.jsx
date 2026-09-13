import React, { useState, useEffect, useRef } from 'react';
import {
  Users, Video, AlertTriangle, ShieldCheck, Activity,
  Clock, ArrowRight, RefreshCw, AlertCircle, CheckCircle2, Server, Database
} from 'lucide-react';
import { fetchAdminOverview } from '../../services/adminApi';

export function AdminOverview({ onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [secondsAgo, setSecondsAgo] = useState(0);

  const mountedRef = useRef(true);

  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      else setIsRefreshing(true);
      setError(null);
      const res = await fetchAdminOverview();
      if (mountedRef.current) {
        setData(res);
        setLastUpdated(new Date());
        setSecondsAgo(0);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to load admin overview.');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        setIsRefreshing(false);
      }
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    loadData();

    // 4-second live polling interval
    const pollInterval = setInterval(() => {
      loadData(true);
    }, 4000);

    // 1-second elapsed counter for truthful "Updated X seconds ago"
    const timerInterval = setInterval(() => {
      setSecondsAgo(prev => prev + 1);
    }, 1000);

    return () => {
      mountedRef.current = false;
      clearInterval(pollInterval);
      clearInterval(timerInterval);
    };
  }, []);

  if (loading && !data) {
    return (
      <div className="admin-loading-container">
        <RefreshCw className="spin-icon" style={{ width: 24, height: 24, color: 'var(--accent-teal)' }} />
        <span>Loading Admin Telemetry from Backend...</span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="admin-error-box">
        <AlertCircle style={{ width: 20, height: 20 }} />
        <span>{error}</span>
        <button className="btn-admin-secondary" onClick={() => loadData(false)}>Retry</button>
      </div>
    );
  }

  const metrics = data?.metrics || {};
  const incidentsByStatus = data?.incidents_by_status || {};
  const recentIncidents = data?.recent_incidents || [];
  const recentAudits = data?.recent_audits || [];
  const aiPipeline = data?.ai_pipeline || {};
  const systemSummary = data?.system_summary || {};

  // Status mapping for AI Engine
  const aiStatus = aiPipeline.status || 'ONLINE';
  const getAiColor = () => {
    if (aiStatus === 'ONLINE') return 'var(--status-live)';
    if (aiStatus === 'DEGRADED') return 'var(--status-warn)';
    return 'var(--status-danger)';
  };

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>System Administration Overview</h2>
          <p className="admin-subtitle">
            Authoritative database metrics, live runtime telemetry, and incident workflows
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {isRefreshing ? 'Refreshing...' : `Updated ${secondsAgo}s ago`}
          </span>
          <button className="btn-admin-secondary" onClick={() => loadData(false)} title="Refresh Telemetry Now">
            <RefreshCw style={{ width: 14, height: 14 }} className={isRefreshing ? 'spin-icon' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Compact System Health Summary Strip (Authoritative Backend State) */}
      {systemSummary.api && (
        <div className="system-summary-strip">
          <div className="summary-item">
            <Server style={{ width: 14, height: 14, color: 'var(--accent-blue)' }} />
            <span className="summary-label">API Gateway:</span>
            <span className={`summary-badge ${(systemSummary.api || 'healthy').toLowerCase()}`}>
              {systemSummary.api}
            </span>
          </div>

          <div className="summary-item">
            <Database style={{ width: 14, height: 14, color: 'var(--status-live)' }} />
            <span className="summary-label">Database:</span>
            <span className={`summary-badge ${(systemSummary.database || 'healthy').toLowerCase()}`}>
              {systemSummary.database}
            </span>
          </div>

          <div className="summary-item">
            <ShieldCheck style={{ width: 14, height: 14, color: 'var(--accent-teal)' }} />
            <span className="summary-label">AI Engine:</span>
            <span className={`summary-badge ${(systemSummary.ai_engine || 'online').toLowerCase()}`}>
              {systemSummary.ai_engine}
            </span>
          </div>

          <div className="summary-item">
            <Video style={{ width: 14, height: 14, color: 'var(--status-live)' }} />
            <span className="summary-label">Cameras:</span>
            <span className="summary-badge online">
              {systemSummary.cameras || `${metrics.online_cameras || 0}/${metrics.total_cameras || 4} ONLINE`}
            </span>
          </div>
        </div>
      )}

      {/* Authoritative KPI Cards */}
      <div className="admin-kpi-grid">
        <div className="admin-kpi-card">
          <div className="kpi-icon-wrap" style={{ background: 'rgba(37, 99, 235, 0.1)', color: 'var(--accent-blue)' }}>
            <Users style={{ width: 20, height: 20 }} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Active Accounts</span>
            <span className="kpi-value">{metrics.active_users ?? 0} <small>/ {metrics.total_users ?? 0} Registered</small></span>
          </div>
          <button className="kpi-link-btn" onClick={() => onNavigate('users')}>
            Manage <ArrowRight style={{ width: 13, height: 13 }} />
          </button>
        </div>

        <div className="admin-kpi-card">
          <div className="kpi-icon-wrap" style={{ background: 'rgba(47, 174, 123, 0.1)', color: 'var(--status-live)' }}>
            <Video style={{ width: 20, height: 20 }} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Surveillance Cameras</span>
            <span className="kpi-value">
              {metrics.online_cameras ?? 0} <small>/ {metrics.total_cameras ?? 4} Online</small>
            </span>
          </div>
          <button className="kpi-link-btn" onClick={() => onNavigate('cameras')}>
            Configure <ArrowRight style={{ width: 13, height: 13 }} />
          </button>
        </div>

        <div className="admin-kpi-card">
          <div className="kpi-icon-wrap" style={{ background: 'rgba(233, 162, 59, 0.1)', color: 'var(--status-warn)' }}>
            <AlertTriangle style={{ width: 20, height: 20 }} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">Open Incidents</span>
            <span className="kpi-value">{metrics.open_incidents ?? 0} <small>/ {metrics.total_incidents ?? 0} Total</small></span>
          </div>
          <button className="kpi-link-btn" onClick={() => onNavigate('incidents')}>
            Review <ArrowRight style={{ width: 13, height: 13 }} />
          </button>
        </div>

        <div className="admin-kpi-card">
          <div className="kpi-icon-wrap" style={{ background: 'rgba(22, 184, 201, 0.1)', color: 'var(--accent-teal)' }}>
            <ShieldCheck style={{ width: 20, height: 20 }} />
          </div>
          <div className="kpi-info">
            <span className="kpi-label">AI Inference Engine</span>
            <span className="kpi-value" style={{ fontSize: '1.25rem', color: getAiColor() }}>
              {aiStatus}
            </span>
          </div>
          <button className="kpi-link-btn" onClick={() => onNavigate('system')}>
            Health <ArrowRight style={{ width: 13, height: 13 }} />
          </button>
        </div>
      </div>

      {/* Incident Status Breakdown */}
      <div className="admin-card-section" style={{ marginTop: '1rem' }}>
        <h3 className="section-title">Incident Workflow Distribution</h3>
        <div className="admin-incident-distribution">
          <div className="dist-chip status-new">
            <span className="dist-label">NEW</span>
            <span className="dist-count">{incidentsByStatus['NEW'] || 0}</span>
          </div>
          <div className="dist-chip status-ack">
            <span className="dist-label">ACKNOWLEDGED</span>
            <span className="dist-count">{incidentsByStatus['ACKNOWLEDGED'] || 0}</span>
          </div>
          <div className="dist-chip status-inv">
            <span className="dist-label">INVESTIGATING</span>
            <span className="dist-count">{incidentsByStatus['INVESTIGATING'] || 0}</span>
          </div>
          <div className="dist-chip status-res">
            <span className="dist-label">RESOLVED</span>
            <span className="dist-count">{incidentsByStatus['RESOLVED'] || 0}</span>
          </div>
          <div className="dist-chip status-dism">
            <span className="dist-label">DISMISSED</span>
            <span className="dist-count">{incidentsByStatus['DISMISSED'] || 0}</span>
          </div>
        </div>
      </div>

      <div className="admin-two-col-grid" style={{ marginTop: '1rem' }}>
        {/* Recent Incidents */}
        <div className="admin-card-section">
          <div className="section-header-row">
            <h3 className="section-title">Recent Operational Incidents</h3>
            <button className="btn-link-action" onClick={() => onNavigate('incidents')}>View All</button>
          </div>
          {recentIncidents.length === 0 ? (
            <div className="admin-empty-state">No incidents recorded in database.</div>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Camera</th>
                    <th>Event</th>
                    <th>Severity</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentIncidents.map((inc) => (
                    <tr key={inc.id} onClick={() => onNavigate('incidents')} style={{ cursor: 'pointer' }}>
                      <td className="mono-cell">{inc.incident_code}</td>
                      <td><span className="cam-badge">{inc.camera_id}</span></td>
                      <td style={{ textTransform: 'capitalize' }}>{inc.event_type.replace('_', ' ')}</td>
                      <td>
                        <span className={`severity-tag sev-${inc.severity.toLowerCase()}`}>
                          {inc.severity}
                        </span>
                      </td>
                      <td>
                        <span className={`status-pill status-${inc.status.toLowerCase()}`}>
                          {inc.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Recent Security Audits */}
        <div className="admin-card-section">
          <div className="section-header-row">
            <h3 className="section-title">Recent Administrative Audit Logs</h3>
            <button className="btn-link-action" onClick={() => onNavigate('audit')}>View All</button>
          </div>
          {recentAudits.length === 0 ? (
            <div className="admin-empty-state">No audit activity recorded yet.</div>
          ) : (
            <div className="admin-table-wrapper">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {recentAudits.map((a) => (
                    <tr key={a.id}>
                      <td className="mono-cell" style={{ fontSize: '0.75rem' }}>
                        {a.timestamp?.includes(' ') ? a.timestamp.split(' ')[1] : a.timestamp}
                      </td>
                      <td><strong>{a.actor_username}</strong> <small>({a.role})</small></td>
                      <td><span className="action-tag">{a.action}</span></td>
                      <td>
                        <span className={`result-tag res-${a.result.toLowerCase()}`}>
                          {a.result}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
