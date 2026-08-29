import React from 'react';
import { X } from 'lucide-react';
import { CameraStream } from './CameraStream';

const FOCUS_CAMERAS = [
  { id: 'CAM-01', title: 'Border Post Alpha' },
  { id: 'CAM-02', title: 'Night Surveillance Bravo' },
  { id: 'CAM-03', title: 'Perimeter Activity Charlie' },
  { id: 'CAM-04', title: 'Urban Facility Delta' },
];

export function FocusModal({
  isOpen,
  selectedCameraId,
  isWebcamRunning = false,
  onSelectCamera,
  onClose
}) {
  if (!isOpen || !selectedCameraId) return null;

  const currentCam = [...FOCUS_CAMERAS, { id: 'CAM-WEBCAM', title: 'Live Integrated/USB Webcam' }]
    .find(c => c.id === selectedCameraId) || { id: selectedCameraId, title: selectedCameraId };

  const handleBackdropClick = (e) => {
    if (e.target.className && typeof e.target.className === 'string' && e.target.className.includes('modal-overlay')) {
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleBackdropClick}>
      <div className="focus-modal-card">
        <div className="focus-modal-header">
          <div className="focus-modal-title">
            <span className="cam-badge-id">{currentCam.id}</span>
            <span>{currentCam.title}</span>
            <span className="badge badge-live" style={{ marginLeft: '0.5rem' }}>● LIVE FOCUS</span>
          </div>
          <button className="btn-close" onClick={onClose}>
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>
        <div className="focus-modal-body">
          <CameraStream
            cameraId={currentCam.id}
            altText={`Focus View - ${currentCam.id}`}
            className="focus-video-stream"
          />
        </div>
        <div className="focus-switcher-bar">
          {FOCUS_CAMERAS.map(cam => (
            <button
              key={cam.id}
              className={`btn-switch-cam ${selectedCameraId === cam.id ? 'active' : ''}`}
              onClick={() => onSelectCamera(cam.id, cam.title)}
            >
              {cam.id}
            </button>
          ))}
          {isWebcamRunning && (
            <button
              className={`btn-switch-cam ${selectedCameraId === 'CAM-WEBCAM' ? 'active' : ''}`}
              onClick={() => onSelectCamera('CAM-WEBCAM', 'Live Integrated/USB Webcam')}
            >
              WEBCAM
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
