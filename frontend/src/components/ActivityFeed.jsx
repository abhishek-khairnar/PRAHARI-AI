import React from 'react';
import { Shield, ShieldCheck, AlertCircle, CreditCard, Eye, AlertTriangle } from 'lucide-react';

export function ActivityFeed({
  events = [],
  activeTab = 'all',
  onSelectTab,
  onOpenLightbox
}) {
  const safeEvents = Array.isArray(events) ? events : [];

  return (
    <div className="feed-section">
      <div className="feed-header">
        <div className="feed-title">
          <Shield style={{ width: 16, height: 16, color: 'var(--accent-teal)' }} />
          <span>Live Incidents</span>
        </div>
        <span className="feed-badge-count">{safeEvents.length} EVENTS</span>
      </div>

      <div className="feed-tabs">
        <button
          className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => onSelectTab('all')}
        >
          All
        </button>
        <button
          className={`tab-btn ${activeTab === 'intrusions' ? 'active' : ''}`}
          onClick={() => onSelectTab('intrusions')}
        >
          Intrusions
        </button>
        <button
          className={`tab-btn ${activeTab === 'anpr' ? 'active' : ''}`}
          onClick={() => onSelectTab('anpr')}
        >
          ANPR
        </button>
        <button
          className={`tab-btn ${activeTab === 'suspicious' ? 'active' : ''}`}
          onClick={() => onSelectTab('suspicious')}
        >
          Suspicious
        </button>
      </div>

      <div className="feed-list">
        {safeEvents.length === 0 ? (
          <div className="empty-feed-placeholder">
            <ShieldCheck style={{ width: 28, height: 28, color: 'var(--text-subtle)' }} />
            <span>No verified incidents recorded.<br />Surveillance perimeter secure.</span>
          </div>
        ) : (
          safeEvents.slice(0, 30).map((ev, idx) => {
            const camId = ev.camera_id || "CAM-01";
            const ts = (ev.timestamp || "").split(" ")[1] || ev.timestamp || "--:--:--";

            const isAnpr = ev.event_type === "anpr" || (ev.plate_text && ev.plate_text !== "N/A" && ev.plate_text !== "PLATE NOT READ" && ev.plate_text !== "ANALYZING...");
            const isSuspicious = ev.event_type === "suspicious_activity" || ev.event_type === "night_movement";

            let cardClass = "event-card";
            let IconComponent = AlertCircle;
            let desc = "";
            let snapUrl = ev.snapshot_url || (ev.snapshot_filename ? `/alerts/${ev.snapshot_filename}` : "");

            if (isAnpr) {
              cardClass += " event-anpr";
              IconComponent = CreditCard;
              const isVerified = ev.validation_status === "VERIFIED" || ev.is_verified;
              const valBadgeClass = isVerified ? "val-badge val-verified" : "val-badge val-detected";
              const confVal = Number.isFinite(ev.confidence) ? (ev.confidence * 100).toFixed(0) : "0";
              desc = `Plate Read: ${ev.plate_text}`;
              return (
                <div key={ev.id || idx} className={cardClass} onClick={() => onOpenLightbox(snapUrl, desc)}>
                  <div className="event-card-top">
                    <span className="event-cam-tag">{camId}</span>
                    <span className="event-time">{ts}</span>
                  </div>
                  <div className="event-card-body">
                    <div className="event-icon-box">
                      <IconComponent style={{ width: 14, height: 14 }} />
                    </div>
                    <div className="event-details">
                      <div className="event-main-text">{desc}</div>
                      <div className="event-sub-text">
                        <span>{ev.vehicle_type || ev.object_type || 'Vehicle'} • {confVal}% Conf</span>
                        <span className={valBadgeClass}>{ev.validation_status || 'DETECTED'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            } else if (isSuspicious) {
              cardClass += " event-suspicious";
              IconComponent = Eye;
              desc = ev.details || `${ev.object_type || 'Subject'} Suspicious Activity`;
              return (
                <div key={ev.id || idx} className={cardClass} onClick={() => onOpenLightbox(snapUrl, desc)}>
                  <div className="event-card-top">
                    <span className="event-cam-tag">{camId}</span>
                    <span className="event-time">{ts}</span>
                  </div>
                  <div className="event-card-body">
                    <div className="event-icon-box">
                      <IconComponent style={{ width: 14, height: 14 }} />
                    </div>
                    <div className="event-details">
                      <div className="event-main-text">{desc}</div>
                      <div className="event-sub-text">
                        <span>Severity: HIGH</span>
                        <span className="val-badge val-detected">VALIDATED</span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            } else {
              cardClass += " event-intrusion";
              IconComponent = AlertTriangle;
              const dir = ev.direction || "IN";
              const objType = ev.object_type || "Subject";
              desc = `${objType} crossed virtual perimeter`;
              const hasPlate = ev.plate_text && ev.plate_text !== "N/A" && ev.plate_text !== "ANALYZING..." && ev.plate_text !== "PLATE NOT READ";

              return (
                <div key={ev.id || idx} className={cardClass} onClick={() => onOpenLightbox(snapUrl, desc)}>
                  <div className="event-card-top">
                    <span className="event-cam-tag">{camId}</span>
                    <span className="event-time">{ts}</span>
                  </div>
                  <div className="event-card-body">
                    <div className="event-icon-box">
                      <IconComponent style={{ width: 14, height: 14 }} />
                    </div>
                    <div className="event-details">
                      <div className="event-main-text">{desc}</div>
                      <div className="event-sub-text">
                        <span>Direction: [{dir}] • ID #{ev.object_id}</span>
                        {hasPlate && <span className="val-badge val-verified">[Plate: {ev.plate_text}]</span>}
                      </div>
                    </div>
                  </div>
                </div>
              );
            }
          })
        )}
      </div>
    </div>
  );
}
