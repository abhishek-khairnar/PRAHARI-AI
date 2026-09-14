import React, { useState } from 'react';
import {
  ShieldAlert, LayoutDashboard, Users, Video, Sliders,
  BellRing, AlertTriangle, Activity, FileText, ArrowLeft,
  LogOut, UserCheck, Bell
} from 'lucide-react';

import { ErrorBoundary } from '../common/ErrorBoundary';
import { AdminOverview } from './AdminOverview';
import { AdminUsers } from './AdminUsers';
import { AdminCameras } from './AdminCameras';
import { AdminZones } from './AdminZones';
import { AdminAlertRules } from './AdminAlertRules';
import { AdminIncidents } from './AdminIncidents';
import { AdminSystemHealth } from './AdminSystemHealth';
import { AdminAuditLogs } from './AdminAuditLogs';
import { AdminNotifications } from './AdminNotifications';

export function AdminLayout({
  currentUser,
  activeTab = 'overview',
  onTabChange,
  onLogout,
  onBackToDashboard
}) {
  const isSuperAdminOrAdmin = ['SUPER_ADMIN', 'ADMIN'].includes(currentUser?.role);

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard, visible: true },
    { id: 'users', label: 'Users & Roles', icon: Users, visible: isSuperAdminOrAdmin },
    { id: 'cameras', label: 'Cameras', icon: Video, visible: true },
    { id: 'zones', label: 'Zones & Fences', icon: Sliders, visible: true },
    { id: 'alerts', label: 'Alert Rules', icon: BellRing, visible: true },
    { id: 'incidents', label: 'Incidents', icon: AlertTriangle, visible: true },
    { id: 'notifications', label: 'Notifications', icon: Bell, visible: true },
    { id: 'system', label: 'System Health', icon: Activity, visible: true },
    { id: 'audit', label: 'Audit Logs', icon: FileText, visible: isSuperAdminOrAdmin },
  ];

  const renderActiveView = () => {
    switch (activeTab) {
      case 'overview':
        return <AdminOverview onNavigate={onTabChange} currentUser={currentUser} />;
      case 'users':
        return <AdminUsers currentUser={currentUser} />;
      case 'cameras':
        return <AdminCameras currentUser={currentUser} />;
      case 'zones':
        return <AdminZones currentUser={currentUser} />;
      case 'alerts':
        return <AdminAlertRules currentUser={currentUser} />;
      case 'incidents':
        return <AdminIncidents currentUser={currentUser} />;
      case 'notifications':
        return <AdminNotifications currentUser={currentUser} onNavigate={onTabChange} />;
      case 'system':
        return <AdminSystemHealth />;
      case 'audit':
        return <AdminAuditLogs currentUser={currentUser} />;
      default:
        return <AdminOverview onNavigate={onTabChange} currentUser={currentUser} />;
    }
  };

  return (
    <div className="admin-shell">
      {/* Sidebar Navigation */}
      <aside className="admin-sidebar">
        <div className="admin-sidebar-brand">
          <div className="brand-logo">
            <ShieldAlert style={{ width: 20, height: 20 }} />
          </div>
          <div className="brand-text">
            <h1>PRAHARI<span>-AI</span></h1>
            <p>Admin Control Console</p>
          </div>
        </div>

        <nav className="admin-nav-list">
          {navItems.filter(item => item.visible).map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                className={`admin-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => onTabChange(item.id)}
              >
                <Icon style={{ width: 16, height: 16 }} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="admin-sidebar-footer">
          <button className="btn-back-dashboard" onClick={onBackToDashboard}>
            <ArrowLeft style={{ width: 15, height: 15 }} />
            <span>Operations Dashboard</span>
          </button>
        </div>
      </aside>

      {/* Main Admin Area */}
      <div className="admin-main-wrapper">
        {/* Top Header */}
        <header className="admin-topbar">
          <div className="admin-topbar-breadcrumb">
            <span style={{ color: 'var(--text-muted)' }}>Admin Panel</span>
            <span style={{ color: 'var(--border-medium)' }}>/</span>
            <strong style={{ textTransform: 'capitalize' }}>
              {activeTab.replace('-', ' ')}
            </strong>
          </div>

          <div className="admin-topbar-actions">
            <div className="admin-user-pill">
              <UserCheck style={{ width: 15, height: 15, color: 'var(--accent-teal)' }} />
              <span>{currentUser?.username || 'Administrator'}</span>
              <span className={`role-badge role-${(currentUser?.role || 'officer').toLowerCase()}`}>
                {currentUser?.role || 'OFFICER'}
              </span>
            </div>

            <button className="btn-admin-logout" onClick={onLogout} title="Sign Out">
              <LogOut style={{ width: 15, height: 15 }} />
              <span>Sign Out</span>
            </button>
          </div>
        </header>

        {/* View Content */}
        <main className="admin-view-body">
          <ErrorBoundary onRetry={() => onTabChange(activeTab)}>
            {renderActiveView()}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
