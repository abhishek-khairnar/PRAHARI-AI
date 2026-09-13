import React, { useState, useEffect } from 'react';
import {
  Video, Edit2, CheckCircle2, XCircle, RefreshCw,
  AlertCircle, AlertTriangle, ShieldCheck, Moon, Car, X
} from 'lucide-react';
import { fetchAdminCameras, updateAdminCamera } from '../../services/adminApi';

export function AdminCameras({ currentUser }) {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const [editingCamera, setEditingCamera] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  const loadCameras = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminCameras();
      setCameras(res);
    } catch (err) {
      setError(err.message || 'Failed to load camera inventory.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCameras();
    const interval = setInterval(loadCameras, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSaveCamera = async (e) => {
    e.preventDefault();
    if (!editingCamera) return;

    try {
      setModalLoading(true);
      setModalError(null);

      await updateAdminCamera(editingCamera.camera_id, {
        name: editingCamera.name,
        location_zone: editingCamera.location_zone,
        ai_enabled: editingCamera.ai_enabled,
        anpr_enabled: editingCamera.anpr_enabled,
        night_detection: editingCamera.night_detection
      });

      setActionSuccess(`Camera ${editingCamera.camera_id} updated successfully.`);
      setTimeout(() => setActionSuccess(null), 3500);
      setEditingCamera(null);
      loadCameras();
    } catch (err) {
      setModalError(err.message || 'Failed to update camera.');
    } finally {
      setModalLoading(false);
    }
  };

  const canEdit = currentUser && ['SUPER_ADMIN', 'ADMIN'].includes(currentUser.role);

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>Surveillance Camera Infrastructure</h2>
          <p className="admin-subtitle">Live stream health, AI pipeline orchestration, and location metadata</p>
        </div>
        <button className="btn-admin-secondary" onClick={loadCameras} title="Refresh Cameras">
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
          <button className="btn-admin-secondary" onClick={loadCameras}>Retry</button>
        </div>
      )}

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Camera ID</th>
              <th>Name</th>
              <th>Location / Zone</th>
              <th>Source Type</th>
              <th>Status</th>
              <th>Telemetry / FPS</th>
              <th>AI Detection</th>
              <th>ANPR</th>
              <th>Night Mode</th>
              {canEdit && <th style={{ textAlign: 'right' }}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {cameras.length === 0 ? (
              <tr>
                <td colSpan={10} className="admin-empty-cell">
                  {loading ? 'Loading camera inventory...' : 'No active cameras found.'}
                </td>
              </tr>
            ) : (
              cameras.map((c) => (
                <tr key={c.camera_id}>
                  <td><span className="cam-badge">{c.camera_id}</span></td>
                  <td><strong>{c.name}</strong></td>
                  <td>{c.location_zone}</td>
                  <td className="mono-cell" style={{ fontSize: '0.75rem' }}>{c.source_type}</td>
                  <td>
                    {c.status === 'ONLINE' ? (
                      <span className="status-indicator-pill active">
                        <CheckCircle2 style={{ width: 12, height: 12 }} /> ONLINE
                      </span>
                    ) : c.status === 'DEGRADED' ? (
                      <span className="status-indicator-pill warning" style={{ background: 'rgba(234, 179, 8, 0.15)', color: '#eab308' }}>
                        <AlertTriangle style={{ width: 12, height: 12 }} /> DEGRADED
                      </span>
                    ) : (
                      <span className="status-indicator-pill disabled">
                        <XCircle style={{ width: 12, height: 12 }} /> OFFLINE
                      </span>
                    )}
                    {c.last_frame_age_seconds !== null && c.last_frame_age_seconds !== undefined && (
                      <div style={{ fontSize: '0.70rem', color: '#94a3b8', marginTop: 2 }}>
                        {c.last_frame_age_seconds < 1.0 ? 'Live (<1s)' : `${c.last_frame_age_seconds}s ago`}
                      </div>
                    )}
                  </td>
                  <td className="mono-cell" style={{ whiteSpace: 'nowrap' }}>
                    <div>
                      <span style={{ color: '#06b6d4', fontWeight: 600 }}>{c.ai_fps !== undefined ? c.ai_fps : c.fps}</span>{' '}
                      <span style={{ fontSize: '0.70rem', color: '#94a3b8' }}>AI FPS</span>
                    </div>
                    {c.capture_fps !== undefined && c.capture_fps > 0 && (
                      <div style={{ fontSize: '0.70rem', color: '#64748b' }}>
                        <span>{c.capture_fps}</span> Cap FPS
                      </div>
                    )}
                  </td>
                  <td>
                    {c.ai_enabled ? (
                      <span className="tag-pill tag-teal"><ShieldCheck style={{ width: 11, height: 11 }} /> Active</span>
                    ) : (
                      <span className="tag-pill tag-muted">Off</span>
                    )}
                  </td>
                  <td>
                    {c.anpr_enabled ? (
                      <span className="tag-pill tag-blue"><Car style={{ width: 11, height: 11 }} /> Enabled</span>
                    ) : (
                      <span className="tag-pill tag-muted">Disabled</span>
                    )}
                  </td>
                  <td>
                    {c.night_detection ? (
                      <span className="tag-pill tag-purple"><Moon style={{ width: 11, height: 11 }} /> Night Mode</span>
                    ) : (
                      <span className="tag-pill tag-muted">Standard</span>
                    )}
                  </td>
                  {canEdit && (
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn-action-icon"
                        title="Configure Camera"
                        onClick={() => {
                          setModalError(null);
                          setEditingCamera({ ...c });
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

      {/* Edit Camera Modal */}
      {editingCamera && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Configure: {editingCamera.camera_id}</h3>
              <button className="btn-close-modal" onClick={() => setEditingCamera(null)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleUpdateCamera} className="admin-modal-form">
              <div className="form-group">
                <label>Camera Friendly Name</label>
                <input
                  type="text"
                  required
                  value={editingCamera.name}
                  onChange={(e) => setEditingCamera({ ...editingCamera, name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Assigned Zone / Sector</label>
                <input
                  type="text"
                  required
                  value={editingCamera.location_zone}
                  onChange={(e) => setEditingCamera({ ...editingCamera, location_zone: e.target.value })}
                />
              </div>

              <div className="form-group-checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={editingCamera.ai_enabled}
                    onChange={(e) => setEditingCamera({ ...editingCamera, ai_enabled: e.target.checked })}
                  />
                  <span>Enable YOLOv8 Detection & Tracking</span>
                </label>
              </div>

              <div className="form-group-checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={editingCamera.anpr_enabled}
                    onChange={(e) => setEditingCamera({ ...editingCamera, anpr_enabled: e.target.checked })}
                  />
                  <span>Enable ANPR License Plate Recognition</span>
                </label>
              </div>

              <div className="form-group-checkbox">
                <label>
                  <input
                    type="checkbox"
                    checked={editingCamera.night_detection}
                    onChange={(e) => setEditingCamera({ ...editingCamera, night_detection: e.target.checked })}
                  />
                  <span>Enable Night Movement & Low-Light Enhancement</span>
                </label>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setEditingCamera(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Saving...' : 'Update Settings'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
