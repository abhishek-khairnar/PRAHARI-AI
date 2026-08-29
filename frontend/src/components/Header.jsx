import React from 'react';
import { ShieldAlert, Cpu, Activity, Video, Camera, BarChart3 } from 'lucide-react';

export function Header({
  gpuInfo = {},
  aggregateAiFps = 0.0,
  activeCameras = 0,
  totalCameras = 4,
  threatScore = 0,
  isWebcamRunning = false,
  isWebcamTransitioning = false,
  onToggleWebcam,
  onOpenAnalytics
}) {
  const gpuAvailable = gpuInfo.available;
  const gpuName = gpuInfo.device_name || gpuInfo.name || (gpuAvailable ? "CUDA GPU" : "CPU Fallback");
  const vramPct = Number.isFinite(gpuInfo.vram_pct) ? gpuInfo.vram_pct.toFixed(0) : "0";
  const gpuText = gpuAvailable ? `GPU: ${gpuName} (${vramPct}%)` : "GPU: CPU Fallback";

  // Calculate threat level pill state
  let threatLevel = "NORMAL";
  let threatClass = "threat-normal";
  if (threatScore >= 20) {
    threatLevel = "CRITICAL";
    threatClass = "threat-critical";
  } else if (threatScore >= 12) {
    threatLevel = "HIGH";
    threatClass = "threat-high";
  } else if (threatScore >= 6) {
    threatLevel = "ELEVATED";
    threatClass = "threat-elevated";
  } else if (threatScore >= 2) {
    threatLevel = "GUARDED";
    threatClass = "threat-guarded";
  }

  let webcamLabel = isWebcamRunning ? "Disconnect Webcam" : "+ Connect Webcam";
  if (isWebcamTransitioning) {
    webcamLabel = isWebcamRunning ? "Stopping..." : "Connecting...";
  }

  return (
    <header>
      <div className="brand-section">
        <div className="brand-logo">
          <ShieldAlert style={{ width: 20, height: 20 }} />
        </div>
        <div className="brand-text">
          <h1>PRAHARI<span>-AI</span></h1>
          <p>AI Surveillance Command Center</p>
        </div>
      </div>

      <div className="header-center-chips">
        <div className="status-chip" title="Hardware GPU / Inference Status">
          <Cpu style={{ width: 14, height: 14 }} />
          <span>{gpuText}</span>
        </div>
        <div className="status-chip" title="Aggregate AI Processing Throughput">
          <Activity style={{ width: 14, height: 14 }} />
          <span>{(aggregateAiFps || 0).toFixed(1)} AI FPS</span>
        </div>
        <div className="status-chip" title="Active Surveillance Camera Streams">
          <Video style={{ width: 14, height: 14 }} />
          <span>{activeCameras}/{totalCameras} Streams</span>
        </div>
        <div className={`threat-pill ${threatClass}`} title="Based on active validated security incidents">
          <div className="threat-dot"></div>
          <span>THREAT: {threatLevel}</span>
        </div>
      </div>

      <div className="header-actions">
        <button
          className="btn-header"
          onClick={onToggleWebcam}
          disabled={isWebcamTransitioning}
          style={{
            borderColor: isWebcamRunning ? 'var(--status-live)' : undefined,
            color: isWebcamRunning ? '#1a7a52' : undefined
          }}
        >
          <Camera style={{ width: 15, height: 15 }} />
          <span>{webcamLabel}</span>
        </button>
        <button className="btn-header btn-primary" onClick={onOpenAnalytics}>
          <BarChart3 style={{ width: 15, height: 15 }} />
          <span>Analytics</span>
        </button>
      </div>
    </header>
  );
}
