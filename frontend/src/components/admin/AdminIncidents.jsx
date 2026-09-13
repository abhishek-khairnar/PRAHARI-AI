import React, { useState, useEffect } from 'react';
import {
  AlertTriangle, CheckCircle2, Search, Filter, Eye,
  RefreshCw, Clock, UserCheck, MessageSquare, X, Camera, Shield
} from 'lucide-react';
import { fetchAdminIncidents, updateAdminIncident } from '../../services/adminApi';

const STATUSES = ['NEW', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED', 'DISMISSED'];
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'INFO'];
const CAMERAS = ['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'];

export function AdminIncidents({ currentUser }) {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [cameraFilter, setCameraFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  // Selected Incident for Detail Modal
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Update controls inside modal
  const [noteInput, setNoteInput] = useState('');
  const [assignedOfficerInput, setAssignedOfficerInput] = useState('');

  const loadIncidents = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminIncidents({
        status: statusFilter || null,
        severity: severityFilter || null,
        camera_id: cameraFilter || null,
        limit: 100
      });
      setIncidents(res);
    } catch (err) {
      setError(err.message || 'Failed to load incidents.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, [statusFilter, severityFilter, cameraFilter]);

  const handleOpenDetail = (inc) => {
    setSelectedIncident(inc);
    setNoteInput('');
    setAssignedOfficerInput(inc.assigned_officer_name || '');
    setModalError(null);
  };

  const handleStatusTransition = async (nextStatus) => {
    if (!selectedIncident) return;
    setModalLoading(true);
    setModalError(null);
    try {
      const updated = await updateAdminIncident(selectedIncident.id, {
        status: nextStatus,
        assigned_officer_name: assignedOfficerInput || selectedIncident.assigned_officer_name,
        notes: noteInput.trim() ? noteInput.trim() : `Status changed to ${nextStatus}`
      });
      setSelectedIncident(updated);
      setNoteInput('');
      setActionSuccess(`Incident ${updated.incident_code} transitioned to ${nextStatus}.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadIncidents();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleAddNoteOnly = async (e) => {
    e.preventDefault();
    if (!noteInput.trim() || !selectedIncident) return;
    setModalLoading(true);
    setModalError(null);
    try {
      const updated = await updateAdminIncident(selectedIncident.id, {
        notes: noteInput.trim(),
        assigned_officer_name: assignedOfficerInput
      });
      setSelectedIncident(updated);
      setNoteInput('');
      setActionSuccess('Investigator notes updated.');
      setTimeout(() => setActionSuccess(null), 3000);
      loadIncidents();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const isOfficer = currentUser?.role === 'OFFICER';
  const canResolve = ['SUPER_ADMIN', 'ADMIN', 'SUPERVISOR'].includes(currentUser?.role);

  const filtered = incidents.filter((i) => {
    const q = searchTerm.toLowerCase();
    return (
      i.incident_code.toLowerCase().includes(q) ||
      i.camera_id.toLowerCase().includes(q) ||
      i.event_type.toLowerCase().includes(q) ||
      (i.assigned_officer_name && i.assigned_officer_name.toLowerCase().includes(q))
    );
  });

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>Operational Incident Management</h2>
          <p className="admin-subtitle">Triage, investigation workflows, operator assignments, and evidentiary closure</p>
        </div>
        <button className="btn-admin-secondary" onClick={loadIncidents} title="Refresh Incidents">
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
          <AlertTriangle style={{ width: 18, height: 18 }} />
          <span>{error}</span>
          <button className="btn-admin-secondary" onClick={loadIncidents}>Retry</button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="admin-filters-bar">
        <div className="search-input-wrapper">
          <Search style={{ width: 15, height: 15, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search incident code, camera, or event..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-select-group">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
            <option value="">All Severities</option>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select value={cameraFilter} onChange={(e) => setCameraFilter(e.target.value)}>
            <option value="">All Cameras</option>
            {CAMERAS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Incidents Table */}
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Incident Code</th>
              <th>Camera</th>
              <th>Event Type</th>
              <th>Sector / Zone</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Assigned Officer</th>
              <th>Logged At</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="admin-empty-cell">
                  {loading ? 'Loading incidents...' : 'No matching incidents found.'}
                </td>
              </tr>
            ) : (
              filtered.map((inc) => (
                <tr key={inc.id} onClick={() => handleOpenDetail(inc)} style={{ cursor: 'pointer' }}>
                  <td className="mono-cell"><strong>{inc.incident_code}</strong></td>
                  <td><span className="cam-badge">{inc.camera_id}</span></td>
                  <td style={{ textTransform: 'capitalize' }}>{inc.event_type.replace('_', ' ')}</td>
                  <td>{inc.zone_name || 'General Sector'}</td>
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
                  <td>{inc.assigned_officer_name || <span style={{ color: 'var(--text-subtle)' }}>Unassigned</span>}</td>
                  <td className="mono-cell" style={{ fontSize: '0.8rem' }}>{inc.created_at}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn-action-icon"
                      title="Review Incident"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDetail(inc);
                      }}
                    >
                      <Eye style={{ width: 14, height: 14 }} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ─── INCIDENT DETAIL MODAL ─── */}
      {selectedIncident && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box admin-modal-wide">
            <div className="admin-modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <h3>Incident Details: {selectedIncident.incident_code}</h3>
                <span className={`status-pill status-${selectedIncident.status.toLowerCase()}`}>
                  {selectedIncident.status}
                </span>
                <span className={`severity-tag sev-${selectedIncident.severity.toLowerCase()}`}>
                  {selectedIncident.severity}
                </span>
              </div>
              <button className="btn-close-modal" onClick={() => setSelectedIncident(null)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertTriangle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <div className="incident-modal-body">
              {/* Left Column: Metadata & Evidence */}
              <div className="incident-meta-col">
                <div className="meta-card">
                  <h4>Incident Metadata</h4>
                  <div className="meta-row">
                    <span className="meta-label">Camera Feed:</span>
                    <span className="cam-badge">{selectedIncident.camera_id}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Event Category:</span>
                    <strong style={{ textTransform: 'capitalize' }}>{selectedIncident.event_type.replace('_', ' ')}</strong>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Protected Zone:</span>
                    <span>{selectedIncident.zone_name || 'Restricted Sector'}</span>
                  </div>
                  <div className="meta-row">
                    <span className="meta-label">Detection Timestamp:</span>
                    <span className="mono-cell">{selectedIncident.created_at}</span>
                  </div>
                  {selectedIncident.resolved_by && (
                    <div className="meta-row">
                      <span className="meta-label">Resolved By:</span>
                      <span><strong>{selectedIncident.resolved_by}</strong> at {selectedIncident.resolved_at}</span>
                    </div>
                  )}
                </div>

                {/* Evidence Snapshot */}
                {selectedIncident.evidence_snapshot && (
                  <div className="meta-card">
                    <h4>Evidentiary Capture</h4>
                    <div className="incident-snapshot-wrapper">
                      <img
                        src={`/alerts/${selectedIncident.evidence_snapshot.split(/[\\/]/).pop()}`}
                        alt="Incident Evidence"
                        className="incident-evidence-img"
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                      <div className="snapshot-filename mono-cell">
                        {selectedIncident.evidence_snapshot.split(/[\\/]/).pop()}
                      </div>
                    </div>
                  </div>
                )}

                {/* Officer Assignment */}
                <div className="meta-card">
                  <h4>Field Officer Assignment</h4>
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <input
                      type="text"
                      placeholder="Officer Name / Call-Sign"
                      value={assignedOfficerInput}
                      onChange={(e) => setAssignedOfficerInput(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Right Column: Workflow Controls & Notes */}
              <div className="incident-workflow-col">
                <div className="meta-card">
                  <h4>Workflow Progression</h4>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                    Current State: <strong>{selectedIncident.status}</strong>
                  </p>

                  <div className="incident-workflow-buttons">
                    {selectedIncident.status === 'NEW' && (
                      <button
                        className="btn-status-action btn-ack"
                        onClick={() => handleStatusTransition('ACKNOWLEDGED')}
                        disabled={modalLoading}
                      >
                        [Acknowledge Incident]
                      </button>
                    )}

                    {['NEW', 'ACKNOWLEDGED'].includes(selectedIncident.status) && (
                      <button
                        className="btn-status-action btn-inv"
                        onClick={() => handleStatusTransition('INVESTIGATING')}
                        disabled={modalLoading}
                      >
                        [Dispatch / Investigate]
                      </button>
                    )}

                    {selectedIncident.status === 'INVESTIGATING' && canResolve && (
                      <button
                        className="btn-status-action btn-res"
                        onClick={() => handleStatusTransition('RESOLVED')}
                        disabled={modalLoading}
                      >
                        [Mark as Resolved]
                      </button>
                    )}

                    {canResolve && selectedIncident.status !== 'DISMISSED' && selectedIncident.status !== 'RESOLVED' && (
                      <button
                        className="btn-status-action btn-dism"
                        onClick={() => handleStatusTransition('DISMISSED')}
                        disabled={modalLoading}
                      >
                        [Dismiss as False Alarm]
                      </button>
                    )}

                    {selectedIncident.status === 'RESOLVED' && (
                      <div className="alert-resolved-badge">
                        <CheckCircle2 style={{ width: 16, height: 16 }} />
                        <span>This incident has been formally investigated and closed.</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Notes & Activity History */}
                <div className="meta-card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <h4>Investigator Notes & Audit Log</h4>
                  <div className="incident-notes-history">
                    {selectedIncident.notes ? (
                      <pre className="notes-text-area">{selectedIncident.notes}</pre>
                    ) : (
                      <div className="admin-empty-state" style={{ padding: '1rem' }}>No notes added yet.</div>
                    )}
                  </div>

                  <form onSubmit={handleAddNoteOnly} style={{ marginTop: '0.75rem' }}>
                    <textarea
                      rows={2}
                      placeholder="Add investigation update or dispatcher note..."
                      value={noteInput}
                      onChange={(e) => setNoteInput(e.target.value)}
                    />
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                      <button
                        type="submit"
                        className="btn-admin-primary"
                        disabled={modalLoading || !noteInput.trim()}
                        style={{ height: '32px', fontSize: '0.8rem' }}
                      >
                        Add Note
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>

            <div className="admin-modal-actions">
              <button
                type="button"
                className="btn-admin-secondary"
                onClick={() => setSelectedIncident(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
