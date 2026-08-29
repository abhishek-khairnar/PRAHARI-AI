import React from 'react';

/**
 * CameraStream Component
 * Renders browser-native MJPEG video stream via standard <img> element.
 */
export function CameraStream({ cameraId, altText, className = "video-stream" }) {
  const streamUrl = `/video_feed/${cameraId}`;

  return (
    <img
      className={className}
      src={streamUrl}
      alt={altText || `${cameraId} Video Stream`}
      loading="eager"
      onError={(e) => {
        // Fallback or retry handling if needed
        console.warn(`Stream error on ${cameraId}`);
      }}
    />
  );
}
