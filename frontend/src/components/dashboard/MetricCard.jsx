import React from 'react';

export function MetricCard({
  title,
  value,
  subtext,
  icon: Icon,
  variant = 'default',
  isAlert = false
}) {
  return (
    <div className={`cc-kpi-card variant-${variant} ${isAlert ? 'has-critical-threat' : ''}`}>
      <div className="cc-kpi-content">
        <div className="cc-kpi-title">{title}</div>
        <div className="cc-kpi-value">{value}</div>
        <div className="cc-kpi-sub">{subtext}</div>
      </div>
      {Icon && (
        <div className="cc-kpi-icon-wrap">
          <Icon style={{ width: 17, height: 17 }} />
        </div>
      )}
    </div>
  );
}
