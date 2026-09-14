import React from 'react';
import { Video, Activity, ShieldAlert, AlertTriangle, CreditCard, CheckCircle2 } from 'lucide-react';
import { MetricCard } from './MetricCard';

export function DashboardMetrics({
  activeCameras = 4,
  totalCameras = 4,
  aggregateAiFps = 0.0,
  captureFps = 0.0,
  activeCriticalCount = 0,
  activeIncidentsCount = 0,
  totalSessionAlerts = 0,
  totalSessionSuspicious = 0,
  verifiedAnprCount = 0,
  systemHealth: propSystemHealth,
  systemHealthDesc: propSystemHealthDesc
}) {
  const allOnline = activeCameras >= totalCameras && totalCameras > 0;
  const isHealthy = allOnline && aggregateAiFps > 0;
  const systemHealth = propSystemHealth || (isHealthy ? "OPTIMAL" : (aggregateAiFps > 0 ? "ATTENTION" : "DEGRADED"));
  const healthSubtext = propSystemHealthDesc || (isHealthy ? "All pipelines nominal" : "Stream degradation detected");
  const healthVariant = systemHealth === "OPTIMAL" ? "success" : (systemHealth === "OFFLINE" ? "critical" : "warning");

  return (
    <section className="cc-kpi-container" aria-label="Operational KPI Overview">
      <div className="cc-kpi-grid">
        {/* 1. LIVE INPUTS */}
        <MetricCard
          title="LIVE INPUTS"
          value={`${activeCameras}/${totalCameras} Online`}
          subtext={allOnline ? "All channels operational" : `${totalCameras - activeCameras} channel(s) offline`}
          icon={Video}
          variant={allOnline ? "success" : "warning"}
        />

        {/* 2. SYSTEM AI PERFORMANCE */}
        <MetricCard
          title="SYSTEM AI PERFORMANCE"
          value={`${(aggregateAiFps || 0).toFixed(1)} FPS`}
          subtext={`Capture: ${(captureFps || 0).toFixed(1)} FPS`}
          icon={Activity}
          variant="primary"
        />

        {/* 3. ACTIVE CRITICAL */}
        <MetricCard
          title="ACTIVE CRITICAL"
          value={activeCriticalCount}
          subtext={activeCriticalCount > 0 ? "Immediate action required" : "Zero critical threats"}
          icon={ShieldAlert}
          variant={activeCriticalCount > 0 ? "critical" : "default"}
          isAlert={activeCriticalCount > 0}
        />

        {/* 4. ACTIVE SECURITY INCIDENTS */}
        <MetricCard
          title="ACTIVE SECURITY INCIDENTS"
          value={activeIncidentsCount}
          subtext={`Intrusions: ${totalSessionAlerts} | Suspicious: ${totalSessionSuspicious}`}
          icon={AlertTriangle}
          variant={activeIncidentsCount > 0 ? "warning" : "default"}
        />

        {/* 5. VALIDATED ANPR READS */}
        <MetricCard
          title="VALIDATED ANPR READS"
          value={(verifiedAnprCount || 0).toLocaleString()}
          subtext="Format Valid & Consensus (Conf ≥ 45%)"
          icon={CreditCard}
          variant="primary"
        />

        {/* 6. SYSTEM HEALTH */}
        <MetricCard
          title="SYSTEM HEALTH"
          value={systemHealth}
          subtext={healthSubtext}
          icon={CheckCircle2}
          variant={healthVariant}
        />
      </div>
    </section>
  );
}
