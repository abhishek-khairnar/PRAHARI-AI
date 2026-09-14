import React from 'react';
import { CameraCard } from './CameraCard';

const DEFAULT_CAMERA_DEFS = [
  { id: 'CAM-01', name: 'Border Post Alpha' },
  { id: 'CAM-02', name: 'Night Surveillance Bravo' },
  { id: 'CAM-03', name: 'Perimeter Activity Charlie' },
  { id: 'CAM-04', name: 'Urban Facility Delta' },
];

export function CameraGrid({
  telemetryMap = {},
  isWebcamRunning = false,
  onFocusCamera
}) {
  return (
    <section className="cc-camera-section" aria-label="Surveillance Camera Feeds">
      <div
        className={`cc-camera-grid ${isWebcamRunning ? 'has-webcam' : ''}`}
        id="commandCenterCameraGrid"
      >
        {DEFAULT_CAMERA_DEFS.map((cam) => (
          <CameraCard
            key={cam.id}
            cameraId={cam.id}
            cameraName={cam.name}
            telemetry={telemetryMap[cam.id] || {}}
            onFocus={onFocusCamera}
          />
        ))}

        {isWebcamRunning && (
          <CameraCard
            key="CAM-WEBCAM"
            cameraId="CAM-WEBCAM"
            cameraName="Live Integrated/USB Webcam"
            telemetry={telemetryMap['CAM-WEBCAM'] || {}}
            onFocus={onFocusCamera}
          />
        )}
      </div>
    </section>
  );
}
