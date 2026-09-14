import React from 'react';
import { Maximize2, Minimize, Search } from 'lucide-react';

export function CameraTelemetry({
  cameraId,
  cameraName,
  aiFps = 0.0,
  capFps = 0.0,
  objCount = 0,
  peopleCount = 0,
  vehicleCount = 0,
  isFullscreen = false,
  onFocus,
  onToggleFullscreen
}) {
  return (
    <div className="cc-cam-bottom-bar">
      <div className="cc-cam-telemetry-text" title={`AI: ${aiFps} FPS · Ingestion: ${capFps} FPS · Objects: ${objCount} (${peopleCount} People, ${vehicleCount} Vehicles)`}>
        <span>AI: <strong className="highlight">{aiFps}</strong> FPS</span>
        <span>|</span>
        <span>Cap: <strong className="highlight">{capFps}</strong> FPS</span>
        <span>|</span>
        <span>Objects: <strong className="highlight">{objCount}</strong> ({peopleCount}P, {vehicleCount}V)</span>
      </div>

      <div className="cc-cam-actions">
        <button
          className="cc-btn-cam-action"
          onClick={() => onFocus && onFocus(cameraId, cameraName)}
          title="Open Focus Zoom Modal"
          type="button"
        >
          <Search style={{ width: 12, height: 12 }} />
          <span>Focus</span>
        </button>

        <button
          className="cc-btn-cam-action"
          onClick={onToggleFullscreen}
          title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
          type="button"
        >
          {isFullscreen ? (
            <>
              <Minimize style={{ width: 12, height: 12 }} />
              <span>Exit</span>
            </>
          ) : (
            <>
              <Maximize2 style={{ width: 12, height: 12 }} />
              <span>Full</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
