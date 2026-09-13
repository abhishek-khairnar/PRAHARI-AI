import React, { useState, useEffect } from 'react';
import {
  BellRing, Edit2, CheckCircle2, XCircle, AlertCircle, RefreshCw, X
} from 'lucide-react';
import { fetchAdminAlertRules, updateAdminAlertRule } from '../../services/adminApi';

const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'INFO'];

export function AdminAlertRules({ currentUser }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const [editingRule, setEditingRule] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  const loadRules = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminAlertRules();
      setRules(res);
    } catch (err) {
      setError(err.message || 'Failed to load alert rules.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const handleUpdateRule = async (e) => {
    e.preventDefault();
    if (!editingRule) return;
    setModalLoading(true);
    setModalError(null);
    try {
      await updateAdminAlertRule(editingRule.id, {
        severity: editingRule.severity,
        cooldown_seconds: editingRule.cooldown_seconds,
        requires_ack: editingRule.requires_ack,
        is_enabled: editingRule.is_enabled,
        description: editingRule.description
      });
      setEditingRule(null);
      setActionSuccess(`Alert rule '${editingRule.event_type}' updated.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadRules();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const canEdit = ['SUPER_ADMIN', 'ADMIN'].includes(currentUser?.role);

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>Alert Rule Policies</h2>
          <p className="admin-subtitle">Local severity thresholds, alarm cooldown periods, and operator acknowledgement policies</p>
        </div>
        <button className="btn-admin-secondary" onClick={loadRules} title="Refresh Rules">
          <RefreshCw style={{ width: 14, height: 14 }} className={loading ? 'spin-icon' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="admin-alert-success">
          <CheckCircle2 style={{ width: 16, height: 16 }} />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="admin-error-box">
          <AlertCircle style={{ width: 18, height: 18 }} />
          <span>{error}</span>
          <button className="btn-admin-secondary" onClick={loadRules}>Retry</button>
        </div>
      )}

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Event Type</th>
              <th>Severity</th>
              <th>Cooldown</th>
              <th>Requires Ack</th>
              <th>Status</th>
              <th>Description</th>
              {canEdit && <th style={{ textAlign: 'right' }}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {rules.length === 0 ? (
              <tr>
                <td colSpan={7} className="admin-empty-cell">
                  {loading ? 'Loading rules...' : 'No alert rules configured.'}
                </td>
              </tr>
            ) : (
              rules.map((r) => (
                <tr key={r.id}>
                  <td><strong className="mono-cell" style={{ fontSize: '0.85rem' }}>{r.event_type}</strong></td>
                  <td>
                    <span className={`severity-tag sev-${r.severity.toLowerCase()}`}>
                      {r.severity}
                    </span>
                  </td>
                  <td className="mono-cell">{r.cooldown_seconds}s</td>
                  <td>
                    {r.requires_ack ? (
                      <span className="tag-pill tag-teal">Mandatory</span>
                    ) : (
                      <span className="tag-pill tag-muted">Optional</span>
                    )}
                  </td>
                  <td>
                    {r.is_enabled ? (
                      <span className="status-indicator-pill active">Enabled</span>
                    ) : (
                      <span className="status-indicator-pill disabled">Disabled</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>{r.description}</td>
                  {canEdit && (
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn-action-icon"
                        title="Edit Rule"
                        onClick={() => {
                          setModalError(null);
                          setEditingRule({ ...r });
                        }}
                      >
                        <Edit2 style={{ width: 14, height: 14 }} />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Rule Modal */}
      {editingRule && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Edit Rule: {editingRule.event_type}</h3>
              <button className="btn-close-modal" onClick={() => setEditingRule(null)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleUpdateRule} className="admin-modal-form">
              <div className="form-group">
                <label>Severity Level</label>
                <select
                  value={editingRule.severity}
                  onChange={(e) => setEditingRule({ ...editingRule, severity: e.target.value })}
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Alarm Cooldown Period (Seconds)</label>
                <input
                  type="number"
                  min="0"
                  max="300"
                  required
                  value={editingRule.cooldown_seconds}
                  onChange={(e) => setEditingRule({ ...editingRule, cooldown_seconds: parseInt(e.target.value) || 0 })}
                />
              </div>

              <div className="form-group">
                <label>Operator Acknowledgement</label>
                <select
                  value={editingRule.requires_ack}
                  onChange={(e) => setEditingRule({ ...editingRule, requires_ack: parseInt(e.target.value) })}
                >
                  <option value={1}>Mandatory Acknowledgement Required</option>
                  <option value={0}>Auto-Logged / Optional</option>
                </select>
              </div>

              <div className="form-group">
                <label>Rule Status</label>
                <select
                  value={editingRule.is_enabled}
                  onChange={(e) => setEditingRule({ ...editingRule, is_enabled: parseInt(e.target.value) })}
                >
                  <option value={1}>Active & Enforced</option>
                  <option value={0}>Disabled</option>
                </select>
              </div>

              <div className="form-group">
                <label>Description</label>
                <input
                  type="text"
                  value={editingRule.description || ''}
                  onChange={(e) => setEditingRule({ ...editingRule, description: e.target.value })}
                />
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setEditingRule(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Saving...' : 'Save Rule Policy'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
