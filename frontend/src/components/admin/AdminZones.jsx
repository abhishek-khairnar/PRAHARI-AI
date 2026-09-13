import React, { useState, useEffect } from 'react';
import {
  Sliders, Plus, Edit2, Trash2, CheckCircle2,
  XCircle, AlertCircle, RefreshCw, X
} from 'lucide-react';
import {
  fetchAdminZones, createAdminZone, updateAdminZone, deleteAdminZone
} from '../../services/adminApi';

const ZONE_TYPES = ['RESTRICTED', 'CHECKPOINT', 'PATROL', 'OBSERVATION'];
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'INFO'];
const DIRECTIONS = ['BOTH', 'IN', 'OUT'];
const CAMERAS = ['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'];

export function AdminZones({ currentUser }) {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingZone, setEditingZone] = useState(null);
  const [formData, setFormData] = useState({
    zone_name: '', camera_id: 'CAM-01', zone_type: 'RESTRICTED',
    severity: 'CRITICAL', is_enabled: 1, fence_direction: 'BOTH', fence_ratio: 0.70
  });

  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  const loadZones = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminZones();
      setZones(res);
    } catch (err) {
      setError(err.message || 'Failed to load zones.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadZones();
  }, []);

  const handleCreateZone = async (e) => {
    e.preventDefault();
    setModalLoading(true);
    setModalError(null);
    try {
      await createAdminZone(formData);
      setIsAddModalOpen(false);
      setFormData({
        zone_name: '', camera_id: 'CAM-01', zone_type: 'RESTRICTED',
        severity: 'CRITICAL', is_enabled: 1, fence_direction: 'BOTH', fence_ratio: 0.70
      });
      setActionSuccess(`Zone '${formData.zone_name}' created.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadZones();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleUpdateZone = async (e) => {
    e.preventDefault();
    if (!editingZone) return;
    setModalLoading(true);
    setModalError(null);
    try {
      await updateAdminZone(editingZone.id, {
        zone_name: editingZone.zone_name,
        zone_type: editingZone.zone_type,
        severity: editingZone.severity,
        is_enabled: editingZone.is_enabled,
        fence_direction: editingZone.fence_direction,
        fence_ratio: editingZone.fence_ratio
      });
      setEditingZone(null);
      setActionSuccess(`Zone '${editingZone.zone_name}' updated.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadZones();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleDeleteZone = async (zone) => {
    if (!window.confirm(`Are you sure you want to delete zone '${zone.zone_name}'?`)) return;
    try {
      await deleteAdminZone(zone.id);
      setActionSuccess(`Zone '${zone.zone_name}' deleted.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadZones();
    } catch (err) {
      setError(err.message);
    }
  };

  const isSuperAdmin = currentUser?.role === 'SUPER_ADMIN';
  const canEdit = ['SUPER_ADMIN', 'ADMIN'].includes(currentUser?.role);

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>Security Zones & Virtual Fence Configuration</h2>
          <p className="admin-subtitle">Configure boundary tripwires, patrol perimeters, and intrusion thresholds</p>
        </div>
        {canEdit && (
          <button
            className="btn-admin-primary"
            onClick={() => {
              setModalError(null);
              setIsAddModalOpen(true);
            }}
          >
            <Plus style={{ width: 15, height: 15 }} />
            <span>+ Define New Zone</span>
          </button>
        )}
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
          <button className="btn-admin-secondary" onClick={loadZones}>Retry</button>
        </div>
      )}

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Zone Name</th>
              <th>Camera</th>
              <th>Zone Type</th>
              <th>Severity</th>
              <th>Fence Position</th>
              <th>Direction</th>
              <th>Status</th>
              {canEdit && <th style={{ textAlign: 'right' }}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {zones.length === 0 ? (
              <tr>
                <td colSpan={8} className="admin-empty-cell">
                  {loading ? 'Loading zones...' : 'No security zones defined.'}
                </td>
              </tr>
            ) : (
              zones.map((z) => (
                <tr key={z.id}>
                  <td><strong>{z.zone_name}</strong></td>
                  <td><span className="cam-badge">{z.camera_id}</span></td>
                  <td><span className="type-pill">{z.zone_type}</span></td>
                  <td>
                    <span className={`severity-tag sev-${z.severity.toLowerCase()}`}>
                      {z.severity}
                    </span>
                  </td>
                  <td className="mono-cell">{Math.round((z.fence_ratio || 0.5) * 100)}% H</td>
                  <td className="mono-cell">{z.fence_direction}</td>
                  <td>
                    {z.is_enabled ? (
                      <span className="status-indicator-pill active">Active</span>
                    ) : (
                      <span className="status-indicator-pill disabled">Disabled</span>
                    )}
                  </td>
                  {canEdit && (
                    <td style={{ textAlign: 'right' }}>
                      <div className="table-actions-group">
                        <button
                          className="btn-action-icon"
                          title="Edit Zone"
                          onClick={() => {
                            setModalError(null);
                            setEditingZone({ ...z });
                          }}
                        >
                          <Edit2 style={{ width: 14, height: 14 }} />
                        </button>
                        {isSuperAdmin && (
                          <button
                            className="btn-action-icon btn-danger-icon"
                            title="Delete Zone"
                            onClick={() => handleDeleteZone(z)}
                          >
                            <Trash2 style={{ width: 14, height: 14 }} />
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ─── ADD ZONE MODAL ─── */}
      {isAddModalOpen && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Define Security Zone / Fence</h3>
              <button className="btn-close-modal" onClick={() => setIsAddModalOpen(false)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateZone} className="admin-modal-form">
              <div className="form-group">
                <label>Zone Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. East Perimeter Restricted Zone"
                  value={formData.zone_name}
                  onChange={(e) => setFormData({ ...formData, zone_name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Assigned Camera</label>
                <select
                  value={formData.camera_id}
                  onChange={(e) => setFormData({ ...formData, camera_id: e.target.value })}
                >
                  {CAMERAS.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Zone Type</label>
                <select
                  value={formData.zone_type}
                  onChange={(e) => setFormData({ ...formData, zone_type: e.target.value })}
                >
                  {ZONE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Alert Severity</label>
                <select
                  value={formData.severity}
                  onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Virtual Fence Ratio (Height %: {Math.round(formData.fence_ratio * 100)}%)</label>
                <input
                  type="range"
                  min="0.10"
                  max="0.90"
                  step="0.05"
                  value={formData.fence_ratio}
                  onChange={(e) => setFormData({ ...formData, fence_ratio: parseFloat(e.target.value) })}
                />
              </div>

              <div className="form-group">
                <label>Tripwire Crossing Direction</label>
                <select
                  value={formData.fence_direction}
                  onChange={(e) => setFormData({ ...formData, fence_direction: e.target.value })}
                >
                  {DIRECTIONS.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setIsAddModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Creating...' : 'Save Zone'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── EDIT ZONE MODAL ─── */}
      {editingZone && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Edit Zone: {editingZone.zone_name}</h3>
              <button className="btn-close-modal" onClick={() => setEditingZone(null)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleUpdateZone} className="admin-modal-form">
              <div className="form-group">
                <label>Zone Name</label>
                <input
                  type="text"
                  required
                  value={editingZone.zone_name}
                  onChange={(e) => setEditingZone({ ...editingZone, zone_name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Zone Type</label>
                <select
                  value={editingZone.zone_type}
                  onChange={(e) => setEditingZone({ ...editingZone, zone_type: e.target.value })}
                >
                  {ZONE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Alert Severity</label>
                <select
                  value={editingZone.severity}
                  onChange={(e) => setEditingZone({ ...editingZone, severity: e.target.value })}
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Virtual Fence Ratio: {Math.round((editingZone.fence_ratio || 0.5) * 100)}%</label>
                <input
                  type="range"
                  min="0.10"
                  max="0.90"
                  step="0.05"
                  value={editingZone.fence_ratio}
                  onChange={(e) => setEditingZone({ ...editingZone, fence_ratio: parseFloat(e.target.value) })}
                />
              </div>

              <div className="form-group">
                <label>Direction</label>
                <select
                  value={editingZone.fence_direction}
                  onChange={(e) => setEditingZone({ ...editingZone, fence_direction: e.target.value })}
                >
                  {DIRECTIONS.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Status</label>
                <select
                  value={editingZone.is_enabled}
                  onChange={(e) => setEditingZone({ ...editingZone, is_enabled: parseInt(e.target.value) })}
                >
                  <option value={1}>Active</option>
                  <option value={0}>Disabled</option>
                </select>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setEditingZone(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
