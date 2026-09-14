import React, { useRef, useState, useEffect } from 'react';
import { CameraStream } from '../CameraStream';
import { CameraTelemetry } from './CameraTelemetry';

export function CameraCard({
  cameraId,
  cameraName,
  telemetry = {},
  onFocus
}) {
  const cardRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(document.fullscreenElement === cardRef.current);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  const handleToggleFullscreen = () => {
    if (!cardRef.current) return;
    if (!document.fullscreenElement) {
      cardRef.current.requestFullscreen().catch(err => {
        console.warn(`Fullscreen error for ${cameraId}:`, err);
      });
    } else {
      document.exitFullscreen().catch(err => {
        console.warn(`Exit fullscreen error:`, err);
      });
    }
  };

  const isConnected = telemetry.connected !== false && telemetry.active !== false;
  const aiFps = Number.isFinite(telemetry.fps) ? telemetry.fps.toFixed(1) : "0.0";
  const capFps = Number.isFinite(telemetry.capture_fps) ? telemetry.capture_fps.toFixed(1) : "0.0";

  const pCount = (telemetry.people_count !== undefined) ? telemetry.people_count : (telemetry.detected_objects?.people_count || 0);
  const vCount = (telemetry.vehicle_count !== undefined) ? telemetry.vehicle_count : (telemetry.detected_objects?.vehicle_count || 0);
  const objCount = (telemetry.total_objects !== undefined) ? telemetry.total_objects : (pCount + vCount);

  const isNight = telemetry.is_night_mode || telemetry.night_mode;
  const brightness = Number.isFinite(telemetry.brightness) ? telemetry.brightness.toFixed(0) : "0";
  const faceCount = (isConnected && Number.isFinite(telemetry.face_count)) ? telemetry.face_count : 0;
  const cardPlacementClass = `cc-cam-card-${cameraId.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;

  return (
    <div
      ref={cardRef}
      className={`cc-camera-card ${cardPlacementClass} ${isFullscreen ? 'is-fullscreen' : ''}`}
      id={`card-${cameraId}`}
    >
      {/* Header */}
      <div className="cc-cam-header">
        <div className="cc-cam-title-box">
          <span className="cc-cam-id-pill">{cameraId}</span>
          <span className="cc-cam-name" title={cameraName}>{cameraName}</span>
        </div>

        <div className="cc-cam-header-badges">
          <span className={`cc-badge ${isConnected ? 'badge-live' : 'badge-offline'}`}>
            {isConnected ? '● LIVE' : 'OFFLINE'}
          </span>

          {isNight ? (
            <span className="cc-badge badge-night" title={`Ambient Luminance (Luma): ${brightness} / 255`}>
              🌙 NIGHT (Luma: {brightness})
            </span>
          ) : (
            <span className="cc-badge badge-day" title={`Ambient Luminance (Luma): ${brightness} / 255`}>
              ☀ DAY
            </span>
          )}

          <span className="cc-badge badge-faces" title={`${faceCount} currently detected face(s)`}>
            👤 Faces: {faceCount}
          </span>
        </div>
      </div>

      {/* Video Stage */}
      <div className="cc-cam-video-box">
        <CameraStream
          cameraId={cameraId}
          altText={`${cameraId} - ${cameraName}`}
          className="cc-cam-stream-img"
        />
      </div>

      {/* Bottom Telemetry & Controls */}
      <CameraTelemetry
        cameraId={cameraId}
        cameraName={cameraName}
        aiFps={aiFps}
        capFps={capFps}
        objCount={objCount}
        peopleCount={pCount}
        vehicleCount={vCount}
        isFullscreen={isFullscreen}
        onFocus={onFocus}
        onToggleFullscreen={handleToggleFullscreen}
      />
    </div>
  );
}
