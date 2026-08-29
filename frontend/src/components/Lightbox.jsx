import React from 'react';
import { X } from 'lucide-react';

export function Lightbox({
  isOpen,
  imageUrl,
  caption,
  onClose
}) {
  if (!isOpen || !imageUrl) return null;

  return (
    <div className="lightbox-modal active" onClick={onClose}>
      <div className="lightbox-box" onClick={(e) => e.stopPropagation()}>
        <img className="lightbox-img" src={imageUrl} alt={caption || "Incident Snapshot"} />
        <div className="lightbox-footer">
          <span>{caption || "Incident Snapshot"}</span>
          <button className="btn-close" onClick={onClose}>
            <X style={{ width: 16, height: 16 }} />
          </button>
        </div>
      </div>
    </div>
  );
}
