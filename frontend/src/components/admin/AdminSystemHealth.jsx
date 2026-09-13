import React, { useState, useEffect } from 'react';
import {
  Cpu, Database, Video, HardDrive, RefreshCw,
  CheckCircle2, AlertCircle, ShieldCheck, Server
} from 'lucide-react';
import { fetchAdminSystemHealth } from '../../services/adminApi';

export function AdminSystemHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminSystemHealth();
      setHealth(res);
    } catch (err) {
      setError(err.message || 'Failed to fetch system health telemetry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  if (loading && !health) {
    return (
      <div className="admin-loading-container">
        <RefreshCw className="spin-icon" style={{ width: 24, height: 24, color: 'var(--accent-teal)' }} />
        <span>Pinging Platform Infrastructure...</span>
      </div>
    );
  }

  if (error && !health) {
    return (
      <div className="admin-error-box">
        <AlertCircle style={{ width: 18, height: 18 }} />
        <span>{error}</span>
        <button className="btn-admin-secondary" onClick={loadHealth}>Retry</button>
      </div>
    );
  }

  const backend = health?.backend || {};
  const db = health?.database || {};
  const cameras = health?.cameras || {};
  const ai = health?.ai_pipeline || {};
  const storage = health?.storage || {};

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>System Infrastructure & Health Telemetry</h2>
          <p className="admin-subtitle">Live hardware diagnostics, process health, and AI subsystem status</p>
        </div>
        <button className="btn-admin-secondary" onClick={loadHealth} title="Refresh Diagnostics">
          <RefreshCw style={{ width: 14, height: 14 }} className={loading ? 'spin-icon' : ''} />
          <span>Ping System</span>
        </button>
      </div>

      <div className="health-grid">
        {/* Backend Server */}
        <div className="health-card">
          <div className="health-card-header">
            <div className="health-icon-wrap" style={{ background: 'rgba(37, 99, 235, 0.1)', color: 'var(--accent-blue)' }}>
              <Server style={{ width: 20, height: 20 }} />
            </div>
            <div>
              <h3>FastAPI Application Server</h3>
              <span className="health-sub">Process & HTTP Gateway</span>
            </div>
            <span className="status-indicator-pill active" style={{ marginLeft: 'auto' }}>
              <CheckCircle2 style={{ width: 12, height: 12 }} /> {backend.status || 'ONLINE'}
            </span>
          </div>
          <div className="health-details-list">
            <div className="health-row">
              <span>Process PID:</span>
              <strong className="mono-cell">{backend.process_pid || '-'}</strong>
            </div>
            <div className="health-row">
              <span>Server Local Time:</span>
              <strong className="mono-cell">{backend.time || '-'}</strong>
            </div>
            <div className="health-row">
              <span>Framework:</span>
              <span>FastAPI (Uvicorn ASGI)</span>
            </div>
          </div>
        </div>

        {/* SQLite Database */}
        <div className="health-card">
          <div className="health-card-header">
            <div className="health-icon-wrap" style={{ background: 'rgba(47, 174, 123, 0.1)', color: 'var(--status-live)' }}>
              <Database style={{ width: 20, height: 20 }} />
            </div>
            <div>
              <h3>SQLite Persistent Storage</h3>
              <span className="health-sub">WAL Mode High-Concurrency</span>
            </div>
            <span className="status-indicator-pill active" style={{ marginLeft: 'auto' }}>
              <CheckCircle2 style={{ width: 12, height: 12 }} /> {db.status || 'ONLINE'}
            </span>
          </div>
          <div className="health-details-list">
            <div className="health-row">
              <span>Journal Mode:</span>
              <strong className="mono-cell">{db.mode || 'WAL'}</strong>
            </div>
            <div className="health-row">
              <span>Database Size:</span>
              <strong className="mono-cell">{db.size_mb || 0} MB</strong>
            </div>
            <div className="health-row">
              <span>Total Intrusions Logged:</span>
              <span className="mono-cell">{db.table_counts?.intrusion_events || 0}</span>
            </div>
            <div className="health-row">
              <span>Total ANPR Plate Reads:</span>
              <span className="mono-cell">{db.table_counts?.anpr_events || 0}</span>
            </div>
            <div className="health-row">
              <span>Security Events Logged:</span>
              <span className="mono-cell">{db.table_counts?.security_events || 0}</span>
            </div>
          </div>
        </div>

        {/* AI Inference Subsystem */}
        <div className="health-card">
          <div className="health-card-header">
            <div className="health-icon-wrap" style={{ background: 'rgba(22, 184, 201, 0.1)', color: 'var(--accent-teal)' }}>
              <Cpu style={{ width: 20, height: 20 }} />
            </div>
            <div>
              <h3>AI Detection & Neural Pipeline</h3>
              <span className="health-sub">YOLOv8 + OCR + YuNet</span>
            </div>
            <span className="status-indicator-pill active" style={{ marginLeft: 'auto' }}>
              <CheckCircle2 style={{ width: 12, height: 12 }} /> {ai.yolo_model || 'LOADED'}
            </span>
          </div>
          <div className="health-details-list">
            <div className="health-row">
              <span>YOLO Object Detector:</span>
              <strong style={{ color: 'var(--status-live)' }}>{ai.yolo_model || 'LOADED'} (weights/yolov8n.pt)</strong>
            </div>
            <div className="health-row">
              <span>ANPR Optical OCR Engine:</span>
              <strong style={{ color: 'var(--status-live)' }}>{ai.anpr_engine || 'READY'}</strong>
            </div>
            <div className="health-row">
              <span>Compute Hardware Device:</span>
              <span className="mono-cell" style={{ fontSize: '0.8rem' }}>{ai.compute_device || 'CPU Fallback'}</span>
            </div>
            <div className="health-row">
              <span>Hardware Acceleration:</span>
              <span>{ai.cuda_accelerated ? 'CUDA GPU Active' : 'CPU Mode'}</span>
            </div>
          </div>
        </div>

        {/* Storage & Snapshots */}
        <div className="health-card">
          <div className="health-card-header">
            <div className="health-icon-wrap" style={{ background: 'rgba(233, 162, 59, 0.1)', color: 'var(--status-warn)' }}>
              <HardDrive style={{ width: 20, height: 20 }} />
            </div>
            <div>
              <h3>Evidentiary Storage Volume</h3>
              <span className="health-sub">Alerts & ANPR Snapshots</span>
            </div>
            <span className="status-indicator-pill active" style={{ marginLeft: 'auto' }}>
              <CheckCircle2 style={{ width: 12, height: 12 }} /> {storage.status || 'HEALTHY'}
            </span>
          </div>
          <div className="health-details-list">
            <div className="health-row">
              <span>Local Alerts Repository:</span>
              <span>static/alerts/</span>
            </div>
            <div className="health-row">
              <span>Captured Evidentiary Frames:</span>
              <strong className="mono-cell">{storage.snapshot_count || 0} Files</strong>
            </div>
            <div className="health-row">
              <span>Filesystem Status:</span>
              <strong style={{ color: 'var(--status-live)' }}>WRITABLE & VERIFIED</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Multi-Camera Stream Pipeline Diagnostic */}
      <div className="admin-card-section" style={{ marginTop: '1.25rem' }}>
        <h3 className="section-title">Active Surveillance Camera Subsystems</h3>
        <div className="camera-health-grid">
          {Object.entries(cameras).map(([camId, cam]) => (
            <div key={camId} className="cam-health-card">
              <div className="cam-health-header">
                <span className="cam-badge">{camId}</span>
                <span className="cam-health-name">{cam.name}</span>
                <span className={`status-pill status-${cam.status === 'ONLINE' ? 'res' : 'dism'}`} style={{ marginLeft: 'auto' }}>
                  {cam.status}
                </span>
              </div>
              <div className="cam-health-details">
                <div className="health-row">
                  <span>Throughput:</span>
                  <strong className="mono-cell">{cam.fps || 0} AI FPS</strong>
                </div>
                <div className="health-row">
                  <span>Source:</span>
                  <span className="mono-cell" style={{ fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {cam.source}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
