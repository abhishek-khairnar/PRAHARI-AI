import React from 'react';
import { DashboardHeader } from './DashboardHeader';
import { DashboardMetrics } from './DashboardMetrics';
import { CameraGrid } from './CameraGrid';
import { LiveIncidents } from './LiveIncidents';

export function Dashboard({
  dashboardData = {},
  verifiedAnprCount = 0,
  eventsFeed = [],
  activeTab = 'all',
  onSelectTab,
  isWebcamRunning = false,
  isWebcamTransitioning = false,
  onToggleWebcam,
  onFocusCamera,
  onOpenLightbox,
  onOpenIncident,
  onOpenAnalytics,
  onNavigateToAdmin,
  currentUser = null,
  // Notification State & Controls
  unreadCount = 0,
  activeIncidentsCount = 0,
  attentionSeverity = null,
  notificationConnectionStatus = 'disconnected',
  isNotificationDrawerOpen = false,
  onToggleNotificationDrawer,
  onViewAllNotifications
}) {
  const agg = dashboardData.aggregate || {};
  const camerasList = dashboardData.cameras || [];
  const telemetryMap = {};
  camerasList.forEach((c) => {
    if (c.camera_id) telemetryMap[c.camera_id] = c;
    else if (c.id) telemetryMap[c.id] = c;
  });

  const activeCameras = agg.active_cameras !== undefined ? agg.active_cameras : 4;
  const totalCameras = agg.total_cameras !== undefined ? agg.total_cameras : 4;
  const aggregateAiFps = agg.aggregate_ai_fps || 0.0;
  const captureFps = agg.aggregate_capture_fps || 0.0;
  const threatScore = agg.threat_score !== undefined ? agg.threat_score : 0;
  const threatLevel = agg.threat_level || (threatScore >= 20 ? "CRITICAL" : (threatScore >= 12 ? "HIGH" : (threatScore >= 6 ? "ELEVATED" : "NORMAL")));
  const systemHealth = agg.system_health || (activeCameras >= totalCameras && aggregateAiFps > 0 ? "OPTIMAL" : "DEGRADED");
  const systemHealthDesc = agg.system_health_desc || (systemHealth === "OPTIMAL" ? "All pipelines nominal" : "Channel degradation detected");
  const totalSessionAlerts = agg.total_session_alerts || 0;
  const totalSessionSuspicious = agg.total_session_suspicious || 0;

  // Active Critical Incidents count directly from authoritative SQLite incident records
  const activeCriticalCount = typeof agg.active_critical_incidents === 'number'
    ? agg.active_critical_incidents
    : (typeof agg.active_critical_count === 'number' ? agg.active_critical_count : 0);

  // Total active security incidents directly from authoritative SQLite incident records
  const resolvedActiveIncidents = typeof agg.active_security_incidents === 'number'
    ? agg.active_security_incidents
    : (typeof agg.active_incidents_count === 'number' ? agg.active_incidents_count : activeIncidentsCount);

  // Verified ANPR Reads from persisted SQLite records
  const resolvedVerifiedAnpr = typeof agg.verified_anpr_reads === 'number'
    ? agg.verified_anpr_reads
    : verifiedAnprCount;

  return (
    <div className="prahari-command-center">
      {/* 1. Header with System Telemetry Strip & Actions */}
      <DashboardHeader
        gpuInfo={agg.gpu || {}}
        aggregateAiFps={aggregateAiFps}
        activeCameras={activeCameras}
        totalCameras={totalCameras}
        threatScore={threatScore}
        threatLevel={threatLevel}
        isWebcamRunning={isWebcamRunning}
        isWebcamTransitioning={isWebcamTransitioning}
        onToggleWebcam={onToggleWebcam}
        onOpenAnalytics={onOpenAnalytics}
        onNavigateToAdmin={onNavigateToAdmin}
        currentUser={currentUser}
        unreadCount={unreadCount}
        attentionSeverity={attentionSeverity}
        notificationConnectionStatus={notificationConnectionStatus}
        isNotificationDrawerOpen={isNotificationDrawerOpen}
        onToggleNotificationDrawer={onToggleNotificationDrawer}
      />

      {/* 2. Operational KPI Strip (6 Cards) */}
      <DashboardMetrics
        activeCameras={activeCameras}
        totalCameras={totalCameras}
        aggregateAiFps={aggregateAiFps}
        captureFps={captureFps}
        activeCriticalCount={activeCriticalCount}
        activeIncidentsCount={resolvedActiveIncidents}
        totalSessionAlerts={totalSessionAlerts}
        totalSessionSuspicious={totalSessionSuspicious}
        verifiedAnprCount={resolvedVerifiedAnpr}
        systemHealth={systemHealth}
        systemHealthDesc={systemHealthDesc}
      />

      {/* 3. Primary Command Center Workspace: 2x2 Cameras + Live Incidents Rail */}
      <main className="cc-workspace" role="main">
        {/* Left: 4-Camera Command Center Grid */}
        <CameraGrid
          telemetryMap={telemetryMap}
          isWebcamRunning={isWebcamRunning}
          onFocusCamera={onFocusCamera}
        />

        {/* Right: Live Incidents Rail (340px) */}
        <LiveIncidents
          events={eventsFeed}
          activeTab={activeTab}
          onSelectTab={onSelectTab}
          onOpenLightbox={onOpenLightbox}
          onOpenIncident={onOpenIncident}
          onViewAll={onViewAllNotifications || (() => onNavigateToAdmin && onNavigateToAdmin())}
        />
      </main>

      {/* NOTE: Bottom Analytics Section intentionally excluded per design mandate */}
    </div>
  );
}
