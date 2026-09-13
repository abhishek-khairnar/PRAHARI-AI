import React, { useState, useCallback, useEffect } from 'react';
import { Header } from './components/Header';
import { SystemStatus } from './components/SystemStatus';
import { CameraGrid } from './components/CameraGrid';
import { ActivityFeed } from './components/ActivityFeed';
import { FocusModal } from './components/FocusModal';
import { AnalyticsDrawer } from './components/AnalyticsDrawer';
import { Lightbox } from './components/Lightbox';
import { usePolling } from './hooks/usePolling';

import { AdminLayout } from './components/admin/AdminLayout';
import { AdminLogin } from './components/admin/AdminLogin';
import {
  getStoredUser,
  fetchCurrentUser,
  logout,
  getAuthToken
} from './services/adminApi';

import {
  fetchDashboardStats,
  fetchAnalytics,
  fetchAlerts,
  fetchAllEvents,
  fetchAnprLog,
  fetchSecurityEvents,
  startWebcam,
  stopWebcam
} from './services/api';

const parseRoute = () => {
  const path = window.location.pathname;
  if (path === '/login') {
    return { view: 'login', tab: 'overview' };
  }
  if (path.startsWith('/admin')) {
    const parts = path.split('/').filter(Boolean);
    const tab = parts[1] || 'overview';
    return { view: 'admin', tab };
  }
  return { view: 'dashboard', tab: 'overview' };
};

export function App() {
  const [currentRoute, setCurrentRoute] = useState(parseRoute);
  const [currentUser, setCurrentUser] = useState(getStoredUser);

  const [dashboardData, setDashboardData] = useState({});
  const [verifiedAnprCount, setVerifiedAnprCount] = useState(0);
  const [eventsFeed, setEventsFeed] = useState([]);
  const [activeTab, setActiveTab] = useState('all');

  const [isWebcamRunning, setIsWebcamRunning] = useState(false);
  const [isWebcamTransitioning, setIsWebcamTransitioning] = useState(false);

  const [focusModal, setFocusModal] = useState({ isOpen: false, cameraId: null, cameraTitle: '' });
  const [analyticsModal, setAnalyticsModal] = useState({ isOpen: false, data: {} });
  const [lightboxModal, setLightboxModal] = useState({ isOpen: false, imgUrl: '', caption: '' });

  // URL Navigation & Session Listeners
  useEffect(() => {
    const handlePopState = () => {
      setCurrentRoute(parseRoute());
    };
    const handleUnauthorized = () => {
      setCurrentUser(null);
      navigateTo('login');
    };
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('prahari:unauthorized', handleUnauthorized);

    if (getAuthToken()) {
      fetchCurrentUser()
        .then(u => setCurrentUser(u))
        .catch(() => setCurrentUser(null));
    }

    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('prahari:unauthorized', handleUnauthorized);
    };
  }, []);

  const navigateTo = (view, tab = 'overview') => {
    let path = '/dashboard';
    if (view === 'login') path = '/login';
    else if (view === 'admin') path = tab === 'overview' ? '/admin' : `/admin/${tab}`;
    window.history.pushState({}, '', path);
    setCurrentRoute({ view, tab });
  };

  const isDashboardView = currentRoute.view === 'dashboard';

  // 1. Telemetry Polling (1000ms) - active when in dashboard view
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

  usePolling(pollTelemetry, 1000, isDashboardView);

  // 2. Events Feed Polling (1500ms) - active when in dashboard view
  const pollEvents = useCallback(async () => {
    try {
      let events = [];
      if (activeTab === 'anpr') {
        events = await fetchAnprLog(25);
      } else if (activeTab === 'suspicious') {
        events = await fetchSecurityEvents(25, 'suspicious_activity');
      } else if (activeTab === 'intrusions') {
        events = await fetchAlerts(25);
      } else {
        events = await fetchAllEvents(25);
      }
      setEventsFeed(events);
    } catch (err) {
      console.error("Events feed error:", err);
    }
  }, [activeTab]);

  usePolling(pollEvents, 1500, isDashboardView);

  // 3. Analytics Summary KPI Polling (5000ms)
  const pollAnalyticsKpi = useCallback(async () => {
    try {
      const stats = await fetchAnalytics();
      setVerifiedAnprCount(stats.verified_plates_count || 0);
    } catch (err) {
      console.error("Analytics KPI error:", err);
    }
  }, []);

  usePolling(pollAnalyticsKpi, 5000, isDashboardView);

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
      } catch (err) {
        alert("Webcam error: " + err.message);
        setIsWebcamRunning(false);
      } finally {
        setIsWebcamTransitioning(false);
      }
    } else {
      try {
        await stopWebcam();
        setIsWebcamRunning(false);
      } catch (err) {
        console.error("Error stopping webcam:", err);
      } finally {
        setIsWebcamTransitioning(false);
      }
    }
  };

  const handleOpenAnalytics = async () => {
    try {
      const data = await fetchAnalytics();
      setAnalyticsModal({ isOpen: true, data });
    } catch (err) {
      console.error("Failed to open analytics:", err);
    }
  };

  const handleFocusCamera = (cameraId, cameraTitle) => {
    setFocusModal({ isOpen: true, cameraId, cameraTitle });
  };

  const handleOpenLightbox = (imgUrl, caption) => {
    setLightboxModal({ isOpen: true, imgUrl, caption });
  };

  // ─── RENDER ADMIN LOGIN VIEW ───
  if (currentRoute.view === 'login') {
    return (
      <AdminLogin
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          navigateTo('admin', 'overview');
        }}
        onBackToDashboard={() => navigateTo('dashboard')}
      />
    );
  }

  // ─── RENDER ADMIN PANEL VIEW ───
  if (currentRoute.view === 'admin') {
    if (!currentUser) {
      return (
        <AdminLogin
          onLoginSuccess={(user) => {
            setCurrentUser(user);
            navigateTo('admin', currentRoute.tab || 'overview');
          }}
          onBackToDashboard={() => navigateTo('dashboard')}
        />
      );
    }

    return (
      <AdminLayout
        currentUser={currentUser}
        activeTab={currentRoute.tab || 'overview'}
        onTabChange={(tab) => navigateTo('admin', tab)}
        onLogout={async () => {
          await logout();
          setCurrentUser(null);
          navigateTo('dashboard');
        }}
        onBackToDashboard={() => navigateTo('dashboard')}
      />
    );
  }

  // ─── RENDER OPERATIONS DASHBOARD VIEW ───
  const agg = dashboardData.aggregate || {};
  const camerasList = dashboardData.cameras || [];
  const telemetryMap = {};
  camerasList.forEach(c => {
    if (c.camera_id) telemetryMap[c.camera_id] = c;
  });

  return (
    <>
      <Header
        gpuInfo={agg.gpu || {}}
        aggregateAiFps={agg.aggregate_ai_fps || 0.0}
        activeCameras={agg.active_cameras || 0}
        totalCameras={agg.total_cameras || 4}
        threatScore={agg.threat_score || 0}
        isWebcamRunning={isWebcamRunning}
        isWebcamTransitioning={isWebcamTransitioning}
        onToggleWebcam={handleToggleWebcam}
        onOpenAnalytics={handleOpenAnalytics}
        onNavigateToAdmin={() => navigateTo(currentUser ? 'admin' : 'login', 'overview')}
      />

      <SystemStatus
        totalPeopleCount={agg.total_people_count || 0}
        totalVehicleCount={agg.total_vehicle_count || 0}
        aggregateAiFps={agg.aggregate_ai_fps || 0.0}
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
