import React, { useState, useCallback, useEffect } from 'react';
import { Dashboard } from './components/dashboard/Dashboard';
import { FocusModal } from './components/FocusModal';
import { AnalyticsDrawer } from './components/AnalyticsDrawer';
import { Lightbox } from './components/Lightbox';
import { usePolling } from './hooks/usePolling';
import './styles/dashboard.css';

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

import { useNotificationSocket } from './hooks/useNotificationSocket';
import { NotificationDrawer } from './components/notifications/NotificationDrawer';
import { ToastContainer } from './components/notifications/ToastContainer';
import { NotificationsPage } from './components/notifications/NotificationsPage';
import { ErrorBoundary } from './components/common/ErrorBoundary';

const parseRoute = () => {
  const path = window.location.pathname;
  if (path === '/login') {
    return { view: 'login', tab: 'overview' };
  }
  if (path === '/notifications') {
    return { view: 'notifications', tab: 'all' };
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
      const path = window.location.pathname;
      if (path.startsWith('/admin') || path === '/notifications') {
        navigateTo('login');
      }
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

  // Ensure #root has cc-root class for zero padding on operations dashboard
  useEffect(() => {
    const rootEl = document.getElementById('root');
    if (rootEl) {
      if (currentRoute.view === 'dashboard') {
        rootEl.classList.add('cc-root');
      } else {
        rootEl.classList.remove('cc-root');
      }
    }
  }, [currentRoute.view]);

  const [isNotificationDrawerOpen, setIsNotificationDrawerOpen] = useState(false);

  const navigateTo = (view, tab = 'overview') => {
    let path = '/dashboard';
    if (view === 'login') path = '/login';
    else if (view === 'notifications') path = '/notifications';
    else if (view === 'admin') path = tab === 'overview' ? '/admin' : `/admin/${tab}`;
    window.history.pushState({}, '', path);
    setCurrentRoute({ view, tab });
  };

  const handleOpenIncident = useCallback((incidentId) => {
    navigateTo('admin', 'incidents');
  }, []);

  const {
    status: notifStatus,
    error: notifError,
    notifications,
    unreadCount,
    activeIncidentsCount,
    attentionSeverity,
    connectionStatus: notifConnectionStatus,
    toasts,
    soundActive,
    desktopPermission,
    dismissToast,
    handleMarkRead,
    handleMarkAllRead,
    toggleSound,
    requestDesktopPermission,
    refreshNotifications
  } = useNotificationSocket({
    onOpenIncident: handleOpenIncident
  });

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
      <ErrorBoundary onRetry={() => navigateTo('admin', currentRoute.tab || 'overview')}>
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
        <ToastContainer
          toasts={toasts}
          onDismiss={dismissToast}
          onOpenIncident={handleOpenIncident}
        />
      </ErrorBoundary>
    );
  }

  // ─── RENDER NOTIFICATIONS VIEW ───
  if (currentRoute.view === 'notifications') {
    return (
      <ErrorBoundary onRetry={() => navigateTo('notifications')}>
        <NotificationsPage
          onNavigateToIncident={(incidentId) => navigateTo('admin', 'incidents')}
          onBack={() => navigateTo('dashboard')}
        />
        <ToastContainer
          toasts={toasts}
          onDismiss={dismissToast}
          onOpenIncident={handleOpenIncident}
        />
      </ErrorBoundary>
    );
  }

  // ─── RENDER OPERATIONS DASHBOARD VIEW ───
  return (
    <>
      <Dashboard
        dashboardData={dashboardData}
        verifiedAnprCount={verifiedAnprCount}
        eventsFeed={eventsFeed}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isWebcamRunning={isWebcamRunning}
        isWebcamTransitioning={isWebcamTransitioning}
        onToggleWebcam={handleToggleWebcam}
        onFocusCamera={handleFocusCamera}
        onOpenLightbox={handleOpenLightbox}
        onOpenIncident={(incidentId) => navigateTo('admin', 'incidents')}
        onOpenAnalytics={handleOpenAnalytics}
        onNavigateToAdmin={() => navigateTo(currentUser ? 'admin' : 'login', 'overview')}
        currentUser={currentUser}
        unreadCount={unreadCount}
        activeIncidentsCount={activeIncidentsCount}
        attentionSeverity={attentionSeverity}
        notificationConnectionStatus={notifConnectionStatus}
        isNotificationDrawerOpen={isNotificationDrawerOpen}
        onToggleNotificationDrawer={() => setIsNotificationDrawerOpen(prev => !prev)}
        onViewAllNotifications={() => navigateTo('notifications')}
      />

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

      <NotificationDrawer
        isOpen={isNotificationDrawerOpen}
        onClose={() => setIsNotificationDrawerOpen(false)}
        status={notifStatus}
        error={notifError}
        onRetry={refreshNotifications}
        onNavigateToLogin={() => navigateTo('login')}
        notifications={notifications}
        unreadCount={unreadCount}
        activeIncidentsCount={activeIncidentsCount}
        connectionStatus={notifConnectionStatus}
        soundActive={soundActive}
        onToggleSound={toggleSound}
        desktopPermission={desktopPermission}
        onRequestDesktopPermission={requestDesktopPermission}
        onMarkRead={handleMarkRead}
        onMarkAllRead={handleMarkAllRead}
        onOpenIncident={(incidentId) => navigateTo('admin', 'incidents')}
        onViewAll={() => navigateTo('notifications')}
      />

      <ToastContainer
        toasts={toasts}
        onDismiss={dismissToast}
        onOpenIncident={(incidentId) => navigateTo('admin', 'incidents')}
      />
    </>
  );
}
