import React from 'react';
import { Monitor, Users, CreditCard, AlertTriangle } from 'lucide-react';

export function SystemStatus({
  activeFeeds = 4,
  totalFeeds = 4,
  captureFps = 0.0,
  totalLiveFaces = 0,
  verifiedAnprCount = 0,
  totalSessionAlerts = 0,
  totalSessionSuspicious = 0
}) {
  const safeLiveFaces = Number.isFinite(totalLiveFaces) ? totalLiveFaces : 0;
  const safeVerifiedAnpr = Number.isFinite(verifiedAnprCount) ? verifiedAnprCount : 0;
  const activeIncidents = (Number.isFinite(totalSessionAlerts) ? totalSessionAlerts : 0) + 
                          (Number.isFinite(totalSessionSuspicious) ? totalSessionSuspicious : 0);

  return (
    <div className="kpi-row">
      <div className="kpi-card">
        <div className="kpi-info">
          <h4>Active Surveillance Feeds</h4>
          <div className="kpi-value">{activeFeeds} / {totalFeeds}</div>
          <div className="kpi-sub">Capture: {(captureFps || 0).toFixed(1)} FPS</div>
        </div>
        <div className="kpi-icon-wrap">
          <Monitor style={{ width: 18, height: 18 }} />
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-info">
          <h4>Total Live Faces</h4>
          <div className="kpi-value">{safeLiveFaces}</div>
          <div className="kpi-sub">YuNet ONNX Engine</div>
        </div>
        <div className="kpi-icon-wrap">
          <Users style={{ width: 18, height: 18 }} />
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-info">
          <h4>Verified ANPR Reads</h4>
          <div className="kpi-value">{safeVerifiedAnpr.toLocaleString()}</div>
          <div className="kpi-sub">YOLOv11 + EasyOCR</div>
        </div>
        <div className="kpi-icon-wrap">
          <CreditCard style={{ width: 18, height: 18 }} />
        </div>
      </div>

      <div className="kpi-card">
        <div className="kpi-info">
          <h4>Active Security Incidents</h4>
          <div className="kpi-value">{activeIncidents}</div>
          <div className="kpi-sub">Session Intrusions: {totalSessionAlerts}</div>
        </div>
        <div className="kpi-icon-wrap">
          <AlertTriangle style={{ width: 18, height: 18 }} />
        </div>
      </div>
    </div>
  );
}
