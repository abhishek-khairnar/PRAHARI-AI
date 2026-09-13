import React, { useState, useEffect } from 'react';
import {
  FileText, Search, Filter, RefreshCw, AlertCircle, CheckCircle2, XCircle
} from 'lucide-react';
import { fetchAdminAuditLogs } from '../../services/adminApi';

export function AdminAuditLogs({ currentUser }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const loadLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminAuditLogs({
        action: actionFilter || null,
        limit: 150
      });
      setLogs(res);
    } catch (err) {
      setError(err.message || 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [actionFilter]);

  const filtered = logs.filter((l) => {
    const q = searchTerm.toLowerCase();
    return (
      l.actor_username.toLowerCase().includes(q) ||
      l.action.toLowerCase().includes(q) ||
      (l.description && l.description.toLowerCase().includes(q))
    );
  });

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>System Audit & Compliance Logs</h2>
          <p className="admin-subtitle">Immutable chronological trail of administrative mutations, security logins, and access events</p>
        </div>
        <button className="btn-admin-secondary" onClick={loadLogs} title="Refresh Logs">
          <RefreshCw style={{ width: 14, height: 14 }} className={loading ? 'spin-icon' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="admin-error-box">
          <AlertCircle style={{ width: 18, height: 18 }} />
          <span>{error}</span>
          <button className="btn-admin-secondary" onClick={loadLogs}>Retry</button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="admin-filters-bar">
        <div className="search-input-wrapper">
          <Search style={{ width: 15, height: 15, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search by actor, action, or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-select-group">
          <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
            <option value="">All Actions</option>
            <option value="USER">User Actions</option>
            <option value="CAMERA">Camera Actions</option>
            <option value="ZONE">Zone Actions</option>
            <option value="ALERT_RULE">Rule Actions</option>
            <option value="INCIDENT">Incident Actions</option>
            <option value="LOGIN">Authentication Actions</option>
          </select>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Actor</th>
              <th>Role</th>
              <th>Action</th>
              <th>Resource</th>
              <th>Result</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="admin-empty-cell">
                  {loading ? 'Loading audit trail...' : 'No audit records found.'}
                </td>
              </tr>
            ) : (
              filtered.map((log) => (
                <tr key={log.id}>
                  <td className="mono-cell" style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                    {log.timestamp}
                  </td>
                  <td><strong>{log.actor_username}</strong></td>
                  <td>
                    <span className={`role-badge role-${log.role.toLowerCase()}`}>
                      {log.role}
                    </span>
                  </td>
                  <td><span className="action-tag">{log.action}</span></td>
                  <td className="mono-cell" style={{ fontSize: '0.8rem' }}>
                    {log.resource_type} {log.resource_id ? `#${log.resource_id}` : ''}
                  </td>
                  <td>
                    <span className={`result-tag res-${log.result.toLowerCase()}`}>
                      {log.result}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{log.description}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
