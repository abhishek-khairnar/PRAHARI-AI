import React from 'react';
import { Database, X } from 'lucide-react';

export function AnalyticsDrawer({
  isOpen,
  analyticsData = {},
  onClose
}) {
  if (!isOpen) return null;

  const totalIntrusions = analyticsData.event_breakdown?.intrusion || 0;
  const totalAnpr = analyticsData.event_breakdown?.anpr || 0;
  const totalSuspicious = analyticsData.event_breakdown?.suspicious_activity || 0;
  const totalNight = analyticsData.event_breakdown?.night_movement || 0;
  const totalAll = totalIntrusions + totalAnpr + totalSuspicious + totalNight;
  const verifiedPlates = analyticsData.verified_plates_count || 0;

  const precision = totalAnpr > 0 ? ((verifiedPlates / totalAnpr) * 100).toFixed(1) : "100.0";

  const perCam = analyticsData.events_per_camera || {};
  const sortedCamKeys = Object.keys(perCam).sort();
  const maxCamEvents = Math.max(...Object.values(perCam), 1);

  const incidentTypes = [
    { label: "Intrusions", val: totalIntrusions, color: "#D95757" },
    { label: "ANPR Reads", val: totalAnpr, color: "#16B8C9" },
    { label: "Suspicious", val: totalSuspicious, color: "#E9A23B" },
    { label: "Night Move", val: totalNight, color: "#7C5CFC" }
  ];
  const maxIncidentVal = Math.max(...incidentTypes.map(t => t.val), 1);

  const handleBackdropClick = (e) => {
    if (e.target.className && typeof e.target.className === 'string' && e.target.className.includes('modal-overlay')) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleBackdropClick}>
      <div className="analytics-drawer">
        <div className="focus-modal-header">
          <div className="focus-modal-title">
            <Database style={{ width: 18, height: 18, color: 'var(--accent-teal)' }} />
            <span>SQLite Surveillance Analytics</span>
          </div>
          <button className="btn-close" onClick={onClose}>
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>
        <div className="analytics-drawer-body">
          <div className="analytics-metric-grid">
            <div className="analytics-stat-card">
              <span>Total Security Events</span>
              <strong>{totalAll.toLocaleString()}</strong>
            </div>
            <div className="analytics-stat-card">
              <span>Verified Plates</span>
              <strong>{verifiedPlates.toLocaleString()}</strong>
            </div>
            <div className="analytics-stat-card">
              <span>ANPR Precision</span>
              <strong>{precision}%</strong>
            </div>
          </div>

          <div className="analytics-breakdown-box">
            <h4>Security Events by Camera</h4>
            {sortedCamKeys.length === 0 ? (
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>No historical camera records.</p>
            ) : (
              sortedCamKeys.map(camId => {
                const cnt = perCam[camId];
                const pct = ((cnt / maxCamEvents) * 100).toFixed(0);
                return (
                  <div key={camId} className="progress-bar-row">
                    <span className="progress-label">{camId}</span>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${pct}%` }}></div>
                    </div>
                    <span className="progress-val">{cnt}</span>
                  </div>
                );
              })
            )}
          </div>

          <div className="analytics-breakdown-box">
            <h4>Security Incident Classification</h4>
            {incidentTypes.map(t => {
              const pct = ((t.val / maxIncidentVal) * 100).toFixed(0);
              return (
                <div key={t.label} className="progress-bar-row">
                  <span className="progress-label">{t.label}</span>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${pct}%`, background: t.color }}></div>
                  </div>
                  <span className="progress-val">{t.val}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
