import React from 'react';
import { ShieldAlert, BarChart3, Camera, ShieldCheck, User } from 'lucide-react';
import { SystemTelemetry } from './SystemTelemetry';
import { NotificationBell } from '../notifications/NotificationBell';

export function DashboardHeader({
  gpuInfo = {},
  aggregateAiFps = 0.0,
  activeCameras = 4,
  totalCameras = 4,
  threatScore = 0,
  threatLevel = 'NORMAL',
  isWebcamRunning = false,
  isWebcamTransitioning = false,
  onToggleWebcam,
  onOpenAnalytics,
  onNavigateToAdmin,
  currentUser = null,
  unreadCount = 0,
  attentionSeverity = null,
  notificationConnectionStatus = 'disconnected',
  isNotificationDrawerOpen = false,
  onToggleNotificationDrawer
}) {
  let webcamLabel = isWebcamRunning ? "Disconnect Webcam" : "+ Connect Webcam";
  if (isWebcamTransitioning) {
    webcamLabel = isWebcamRunning ? "Stopping..." : "Connecting...";
  }

  return (
    <header className="cc-header" role="banner">
      {/* Left Brand Identity */}
      <div className="cc-header-left">
        <div className="cc-brand-badge" title="PRAHARI-AI Unified Defense">
          <ShieldAlert style={{ width: 24, height: 24 }} />
        </div>
        <div className="cc-brand-titles">
          <div className="cc-brand-name">
            PRAHARI<span>-AI</span>
          </div>
          <div className="cc-brand-subtitle">
            AI Surveillance Command Center
          </div>
        </div>
      </div>

      {/* Center System Telemetry Strip */}
      <SystemTelemetry
        gpuInfo={gpuInfo}
        aggregateAiFps={aggregateAiFps}
        activeCameras={activeCameras}
        totalCameras={totalCameras}
        threatScore={threatScore}
        threatLevel={threatLevel}
      />

      {/* Right Actions: Webcam, Existing Alert Bell, Analytics, Admin Panel, User Menu */}
      <div className="cc-header-right">
        {/* Dynamic Webcam Control */}
        <button
          className={`cc-btn cc-btn-webcam ${isWebcamRunning ? 'active' : ''}`}
          onClick={onToggleWebcam}
          disabled={isWebcamTransitioning}
          title="Connect or disconnect integrated/USB webcam"
          type="button"
        >
          <Camera style={{ width: 16, height: 16 }} />
          <span>{webcamLabel}</span>
        </button>

        {/* STRICT PRESERVATION: Existing PRAHARI-AI Alerts Icon/Button */}
        <NotificationBell
          unreadCount={unreadCount}
          attentionSeverity={attentionSeverity}
          connectionStatus={notificationConnectionStatus}
          isOpen={isNotificationDrawerOpen}
          onToggle={onToggleNotificationDrawer}
        />

        {/* Analytics Navigation */}
        <button
          className="cc-btn cc-btn-primary"
          onClick={onOpenAnalytics}
          title="Open Historical Analytics & Intelligence"
          type="button"
        >
          <BarChart3 style={{ width: 16, height: 16 }} />
          <span>Analytics</span>
        </button>

        {/* Admin Panel Navigation */}
        <button
          className="cc-btn cc-btn-admin"
          onClick={onNavigateToAdmin}
          title="Open System Administration & Configuration"
          type="button"
        >
          <ShieldCheck style={{ width: 16, height: 16 }} />
          <span>Admin Panel</span>
        </button>

        {/* Authenticated User Status */}
        {currentUser && (
          <div className="cc-user-pill" title={`Logged in as ${currentUser.username || currentUser.email || 'Admin'}`}>
            <span className="cc-user-avatar">
              {(currentUser.username || 'A').charAt(0).toUpperCase()}
            </span>
            <span style={{ fontWeight: 600 }}>{currentUser.username || 'Admin'}</span>
          </div>
        )}
      </div>
    </header>
  );
}
