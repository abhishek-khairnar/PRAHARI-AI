import React, { useState, useEffect } from 'react';
import {
  FileText, Search, Filter, RefreshCw, AlertCircle, CheckCircle2, XCircle
} from 'lucide-react';
import { fetchAdminAuditLogs } from '../../services/adminApi';

export function AdminAuditLogs({ currentUser }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  const [searchTerm, setSearchTerm] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const loadLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminAuditLogs({
        action: actionFilter || null,
        page: page,
        page_size: pageSize
      });

      if (res && res.items) {
        setLogs(res.items);
        setTotalCount(res.total ?? res.items.length);
      } else if (Array.isArray(res)) {
        setLogs(res);
        setTotalCount(res.length);
      } else {
        setLogs([]);
        setTotalCount(0);
      }
    } catch (err) {
      setError(err.message || 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [actionFilter, page]);

  const filtered = logs.filter((l) => {
    const q = searchTerm.toLowerCase();
    return (
      (l.actor_username || '').toLowerCase().includes(q) ||
      (l.action || '').toLowerCase().includes(q) ||
      (l.description && l.description.toLowerCase().includes(q))
    );
  });

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const startItem = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, totalCount);

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
          <select value={actionFilter} onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}>
            <option value="">All Actions</option>
            <option value="USER">User Management Actions</option>
            <option value="CAMERA">Camera Actions</option>
            <option value="ZONE">Zone / Fence Actions</option>
            <option value="ALERT_RULE">Rule Actions</option>
            <option value="INCIDENT">Incident Actions</option>
            <option value="LOGIN">Authentication Events</option>
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
                  {loading ? 'Loading audit trail from database...' : 'No audit activity recorded yet.'}
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
                    <span className={`role-badge role-${(log.role || 'officer').toLowerCase()}`}>
                      {log.role}
                    </span>
                  </td>
                  <td><span className="action-tag">{log.action}</span></td>
                  <td className="mono-cell" style={{ fontSize: '0.8rem' }}>
                    {log.resource_type} {log.resource_id ? `#${log.resource_id}` : ''}
                  </td>
                  <td>
                    <span className={`result-tag res-${(log.result || 'success').toLowerCase()}`}>
                      {log.result}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{log.description}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Backend Pagination Footer */}
        <div className="admin-pagination">
          <div>
            Showing <strong>{startItem}</strong> to <strong>{endItem}</strong> of <strong>{totalCount}</strong> audit records
          </div>
          <div className="admin-pagination-actions">
            <button
              className="btn-page"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span>Page {page} of {totalPages}</span>
            <button
              className="btn-page"
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
