import React from 'react';
import { Cpu, Activity, Video, Shield } from 'lucide-react';

export function SystemTelemetry({
  gpuInfo = {},
  aggregateAiFps = 0.0,
  activeCameras = 4,
  totalCameras = 4,
  threatScore = 0,
  threatLevel: propThreatLevel
}) {
  const gpuAvailable = Boolean(gpuInfo.available);
  const rawName = gpuInfo.device_name || gpuInfo.name || (gpuAvailable ? "CUDA GPU" : "CPU Fallback");
  const cleanGpuName = rawName.replace(/^NVIDIA\s+GeForce\s+/i, '').replace(/\s+Laptop\s+GPU/i, '');

  let gpuDisplay = "Telemetry unavailable";
  if (!gpuAvailable) {
    gpuDisplay = "CPU Fallback";
  } else if (typeof gpuInfo.gpu_util_pct === 'number') {
    gpuDisplay = `${cleanGpuName} (${gpuInfo.gpu_util_pct}% Util)`;
  } else if (Number.isFinite(gpuInfo.vram_pct)) {
    gpuDisplay = `${cleanGpuName} (${gpuInfo.vram_pct.toFixed(0)}% VRAM)`;
  } else {
    gpuDisplay = `${cleanGpuName} (N/A)`;
  }

  // Authoritative threat level string and CSS class
  let threatLevel = propThreatLevel || "NORMAL";
  if (!propThreatLevel) {
    if (threatScore >= 20) {
      threatLevel = "CRITICAL";
    } else if (threatScore >= 12) {
      threatLevel = "HIGH";
    } else if (threatScore >= 6) {
      threatLevel = "ELEVATED";
    } else if (threatScore >= 2) {
      threatLevel = "GUARDED";
    }
  }
  const threatClass = `threat-${threatLevel.toLowerCase()}`;

  const allCamsOnline = activeCameras >= totalCameras && totalCameras > 0;

  return (
    <div className="cc-telemetry-strip" role="region" aria-label="System Telemetry">
      <div className="cc-telemetry-item" title="Hardware GPU / Inference Device">
        <span className="cc-telemetry-icon">
          <Cpu style={{ width: 16, height: 16 }} />
        </span>
        <span>GPU: <strong>{gpuDisplay}</strong></span>
      </div>

      <div className="cc-telemetry-item" title="Active Camera Video Streams">
        <span className={`cc-status-dot ${allCamsOnline ? 'online' : 'warning'}`} />
        <span className="cc-telemetry-icon">
          <Video style={{ width: 16, height: 16 }} />
        </span>
        <span>STREAMS: <strong>{activeCameras}/{totalCameras} Online</strong></span>
      </div>

      <div className={`cc-threat-chip ${threatClass}`} title={`Active threat evaluation score: ${threatScore}`}>
        <Shield style={{ width: 15, height: 15 }} />
        <span>THREAT: {threatLevel}</span>
      </div>
    </div>
  );
}
