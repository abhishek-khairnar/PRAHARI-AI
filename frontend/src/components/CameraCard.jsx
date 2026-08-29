import React from 'react';
import { Maximize2 } from 'lucide-react';
import { CameraStream } from './CameraStream';

export function CameraCard({
  cameraId,
  cameraName,
  telemetry = {},
  onFocus
}) {
  const isConnected = telemetry.connected !== false;
  const aiFps = Number.isFinite(telemetry.fps) ? telemetry.fps.toFixed(1) : "0.0";
  const capFps = Number.isFinite(telemetry.capture_fps) ? telemetry.capture_fps.toFixed(1) : "0.0";
  
  const pCount = (telemetry.people_count !== undefined) ? telemetry.people_count : (telemetry.detected_objects?.people_count || 0);
  const vCount = (telemetry.vehicle_count !== undefined) ? telemetry.vehicle_count : (telemetry.detected_objects?.vehicle_count || 0);
  const objCount = (telemetry.total_objects !== undefined) ? telemetry.total_objects : (pCount + vCount);

  const isNight = telemetry.is_night_mode || telemetry.night_mode;
  const brightness = Number.isFinite(telemetry.brightness) ? telemetry.brightness.toFixed(0) : "0";
  const faceCount = Number.isFinite(telemetry.face_count) ? telemetry.face_count : 0;

  return (
    <div className="camera-card" id={`card-${cameraId}`}>
      <div className="camera-header">
        <div className="camera-title-wrap">
          <span className="cam-badge-id">{cameraId}</span>
          <span>{cameraName}</span>
        </div>
        <div className="camera-header-badges">
          <span className={`badge ${isConnected ? 'badge-live' : 'badge-night'}`}>
            {isConnected ? '● LIVE' : 'OFFLINE'}
          </span>
          {isNight ? (
            <span className="badge badge-night">🌙 NIGHT ({brightness})</span>
          ) : (
            <span className="badge badge-day">☀ DAY</span>
          )}
          <span className="badge badge-face">👤 Faces: {faceCount}</span>
        </div>
      </div>
      <div className="video-box">
        <CameraStream cameraId={cameraId} altText={`${cameraId} - ${cameraName}`} />
        <div className="video-overlay-bar">
          <span>AI: {aiFps} FPS | Cap: {capFps} FPS | Objects: {objCount} ({pCount}P, {vCount}V)</span>
          <button className="btn-focus" onClick={() => onFocus(cameraId, cameraName)}>
            <Maximize2 style={{ width: 11, height: 11 }} /> Focus
          </button>
        </div>
      </div>
    </div>
  );
}
