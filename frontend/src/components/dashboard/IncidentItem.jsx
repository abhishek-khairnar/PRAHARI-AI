import React, { useState } from 'react';
import { AlertTriangle, CreditCard, Eye, ShieldAlert } from 'lucide-react';

export function IncidentItem({
  event,
  onOpenLightbox,
  onOpenIncident
}) {
  const [imgError, setImgError] = useState(false);
  const camId = event.camera_id || "CAM-01";
  const rawTs = event.timestamp || "";
  const timeStr = rawTs.includes(" ") ? rawTs.split(" ")[1] : (rawTs || "--:--:--");

  const isAnpr = event.event_type === "anpr" || (event.plate_text && event.plate_text !== "N/A" && event.plate_text !== "PLATE NOT READ" && event.plate_text !== "ANALYZING...");
  const isSuspicious = event.event_type === "suspicious_activity" || event.event_type === "night_movement";

  let severity = "critical";
  let severityLabel = "CRITICAL";
  let Icon = AlertTriangle;
  let title = `${event.object_type || 'Subject'} perimeter breach`;
  let meta = `Direction: [${event.direction || 'IN'}] | ID #${event.object_id || '0'}`;

  // Snapshot URL resolution
  let snapUrl = event.snapshot_url || "";
  if (!snapUrl && event.snapshot_filename) {
    if (isAnpr) {
      snapUrl = `/anpr/${event.snapshot_filename}`;
    } else {
      snapUrl = `/alerts/${event.snapshot_filename}`;
    }
  }

  if (isAnpr) {
    severity = "anpr";
    severityLabel = "ANPR";
    Icon = CreditCard;
    const isVerified = event.validation_status === "VERIFIED" || event.is_verified;
    const confVal = Number.isFinite(event.confidence) ? (event.confidence * 100).toFixed(0) : "0";
    title = `Plate: ${event.plate_text || 'UNKNOWN'}`;
    meta = `${event.vehicle_type || 'Vehicle'} | ${confVal}% Conf | ${isVerified ? 'VERIFIED' : 'DETECTED'}`;
  } else if (isSuspicious) {
    severity = "high";
    severityLabel = "HIGH";
    Icon = Eye;
    title = event.details || `${event.object_type || 'Subject'} Suspicious Activity`;
    meta = `Near restricted area | ID #${event.object_id || '0'}`;
  } else {
    // Standard intrusion
    severity = (event.severity || "CRITICAL").toLowerCase();
    severityLabel = (event.severity || "CRITICAL").toUpperCase();
    Icon = ShieldAlert;
    if (event.plate_text && event.plate_text !== "N/A") {
      meta += ` | Plate: ${event.plate_text}`;
    }
  }

  const handleClick = () => {
    if (snapUrl && !imgError && onOpenLightbox) {
      onOpenLightbox(snapUrl, title);
    } else if (onOpenIncident) {
      onOpenIncident(event.incident_id || event.id);
    }
  };

  return (
    <article
      className="cc-incident-card"
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
      aria-label={`${severityLabel} incident on ${camId}: ${title}`}
    >
      <div className="cc-incident-top">
        <div className="cc-incident-top-left">
          <span className="cc-incident-cam-tag">{camId}</span>
          <span className="cc-incident-time">{timeStr}</span>
        </div>
        <span className={`cc-incident-severity-badge ${severity}`}>
          {severityLabel}
        </span>
      </div>

      <div className="cc-incident-body">
        {snapUrl && !imgError ? (
          <img
            src={snapUrl}
            alt={title}
            className="cc-incident-thumb"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="cc-incident-icon-placeholder">
            <Icon style={{ width: 18, height: 18 }} />
          </div>
        )}

        <div className="cc-incident-details">
          <div className="cc-incident-title" title={title}>
            {title}
          </div>
          <div className="cc-incident-meta" title={meta}>
            {meta}
          </div>
        </div>
      </div>
    </article>
  );
}
