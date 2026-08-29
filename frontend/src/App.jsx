import React, { useState, useCallback } from 'react';
import { Header } from './components/Header';
import { SystemStatus } from './components/SystemStatus';
import { CameraGrid } from './components/CameraGrid';
import { ActivityFeed } from './components/ActivityFeed';
import { FocusModal } from './components/FocusModal';
import { AnalyticsDrawer } from './components/AnalyticsDrawer';
import { Lightbox } from './components/Lightbox';
import { usePolling } from './hooks/usePolling';
import {
  fetchDashboardStats,
  fetchAnalytics,
  fetchAlerts,
  fetchAnprLog,
  fetchSecurityEvents,
  startWebcam,
  stopWebcam
} from './services/api';

export function App() {
  const [dashboardData, setDashboardData] = useState({});
  const [verifiedAnprCount, setVerifiedAnprCount] = useState(0);
  const [eventsFeed, setEventsFeed] = useState([]);
  const [activeTab, setActiveTab] = useState('all');

  const [isWebcamRunning, setIsWebcamRunning] = useState(false);
  const [isWebcamTransitioning, setIsWebcamTransitioning] = useState(false);

  const [focusModal, setFocusModal] = useState({ isOpen: false, cameraId: null, cameraTitle: '' });
  const [analyticsModal, setAnalyticsModal] = useState({ isOpen: false, data: {} });
  const [lightboxModal, setLightboxModal] = useState({ isOpen: false, imgUrl: '', caption: '' });

  // 1. Telemetry Polling (1000ms)
  const pollTelemetry = useCallback(async () => {
    try {
      const data = await fetchDashboardStats();
      setDashboardData(data);

      const activeCams = data.cameras || [];
      const webcamActive = activeCams.some(c => c.camera_id === 'CAM-WEBCAM' && (c.connected || c.active));
      if (webcamActive && !isWebcamRunning) {
        setIsWebcamRunning(true);
      } else if (!webcamActive && isWebcamRunning && !isWebcamTransitioning) {
        setIsWebcamRunning(false);
      }
    } catch (err) {
      console.error("Telemetry fetch error:", err);
    }
  }, [isWebcamRunning, isWebcamTransitioning]);

  usePolling(pollTelemetry, 1000, true);

  // 2. Events Feed Polling (1500ms)
  const pollEvents = useCallback(async () => {
    try {
      let events = [];
      if (activeTab === 'anpr') {
        events = await fetchAnprLog(25);
      } else if (activeTab === 'suspicious') {
        events = await fetchSecurityEvents(25);
      } else {
        events = await fetchAlerts(25);
      }
      setEventsFeed(events);
    } catch (err) {
      console.error("Events feed error:", err);
    }
  }, [activeTab]);

  usePolling(pollEvents, 1500, true);

  // 3. Analytics Summary KPI Polling (5000ms)
  const pollAnalyticsKpi = useCallback(async () => {
    try {
      const stats = await fetchAnalytics();
      setVerifiedAnprCount(stats.verified_plates_count || 0);
    } catch (err) {
      console.error("Analytics KPI error:", err);
    }
  }, []);

  usePolling(pollAnalyticsKpi, 5000, true);

  // Handlers
  const handleToggleWebcam = async () => {
    if (isWebcamTransitioning) return;
    setIsWebcamTransitioning(true);

    if (!isWebcamRunning) {
      try {
        const res = await startWebcam(0);
        if (res.status === 'started' || res.status === 'already_running') {
          setIsWebcamRunning(true);
        } else {
          alert("Could not start webcam: " + (res.error || "Device unavailable"));
          setIsWebcamRunning(false);
        }
      } catch (e) {
        alert("Webcam connection error.");
        setIsWebcamRunning(false);
      } finally {
        setIsWebcamTransitioning(false);
      }
    } else {
      try {
        await stopWebcam();
        setIsWebcamRunning(false);
        if (focusModal.cameraId === 'CAM-WEBCAM') {
          setFocusModal({ isOpen: false, cameraId: null, cameraTitle: '' });
        }
      } catch (e) {
        setIsWebcamRunning(false);
      } finally {
        setIsWebcamTransitioning(false);
      }
    }
  };

  const handleOpenAnalytics = async () => {
    setAnalyticsModal({ isOpen: true, data: {} });
    try {
      const stats = await fetchAnalytics();
      setAnalyticsModal({ isOpen: true, data: stats });
    } catch (err) {
      console.error("Failed to load analytics modal data:", err);
    }
  };

  const handleFocusCamera = (cameraId, cameraTitle) => {
    setFocusModal({ isOpen: true, cameraId, cameraTitle });
  };

  const handleOpenLightbox = (imgUrl, caption) => {
    if (!imgUrl) return;
    setLightboxModal({ isOpen: true, imgUrl, caption });
  };

  // Telemetry mappings
  const agg = dashboardData.aggregate || {};
  const gpuInfo = agg.gpu || {};
  const activeCamsList = dashboardData.cameras || [];
  
  const telemetryMap = {};
  activeCamsList.forEach(c => {
    telemetryMap[c.camera_id] = c;
  });

  const threatScore = ((agg.total_session_alerts || 0) * 1) + ((agg.total_session_suspicious || 0) * 3);

  return (
    <>
      <Header
        gpuInfo={gpuInfo}
        aggregateAiFps={agg.aggregate_ai_fps || 0.0}
        activeCameras={agg.active_cameras || 0}
        totalCameras={agg.total_cameras || 4}
        threatScore={threatScore}
        isWebcamRunning={isWebcamRunning}
        isWebcamTransitioning={isWebcamTransitioning}
        onToggleWebcam={handleToggleWebcam}
        onOpenAnalytics={handleOpenAnalytics}
      />

      <SystemStatus
        activeFeeds={agg.active_cameras || 0}
        totalFeeds={agg.total_cameras || 4}
        captureFps={agg.aggregate_capture_fps || 0.0}
        totalLiveFaces={agg.total_live_faces || 0}
        verifiedAnprCount={verifiedAnprCount}
        totalSessionAlerts={agg.total_session_alerts || 0}
        totalSessionSuspicious={agg.total_session_suspicious || 0}
      />

      <div className="workspace">
        <CameraGrid
          telemetryMap={telemetryMap}
          isWebcamRunning={isWebcamRunning}
          onFocusCamera={handleFocusCamera}
        />

        <ActivityFeed
          events={eventsFeed}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          onOpenLightbox={handleOpenLightbox}
        />
      </div>

      <FocusModal
        isOpen={focusModal.isOpen}
        selectedCameraId={focusModal.cameraId}
        isWebcamRunning={isWebcamRunning}
        onSelectCamera={(id, title) => setFocusModal({ isOpen: true, cameraId: id, cameraTitle: title })}
        onClose={() => setFocusModal({ isOpen: false, cameraId: null, cameraTitle: '' })}
      />

      <AnalyticsDrawer
        isOpen={analyticsModal.isOpen}
        analyticsData={analyticsModal.data}
        onClose={() => setAnalyticsModal({ isOpen: false, data: {} })}
      />

      <Lightbox
        isOpen={lightboxModal.isOpen}
        imageUrl={lightboxModal.imgUrl}
        caption={lightboxModal.caption}
        onClose={() => setLightboxModal({ isOpen: false, imgUrl: '', caption: '' })}
      />
    </>
  );
}
