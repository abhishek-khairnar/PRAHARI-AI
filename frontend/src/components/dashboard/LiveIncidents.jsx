import React, { useMemo } from 'react';
import { Shield, ShieldCheck } from 'lucide-react';
import { IncidentItem } from './IncidentItem';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'critical', label: 'Critical' },
  { id: 'high', label: 'High' },
  { id: 'anpr', label: 'ANPR' },
  { id: 'suspicious', label: 'Suspicious' }
];

export function LiveIncidents({
  events = [],
  activeTab = 'all',
  onSelectTab,
  onOpenLightbox,
  onOpenIncident,
  onViewAll
}) {
  const safeEvents = Array.isArray(events) ? events : [];

  // Client-side filtering to guarantee instant UI tab switching even between polling ticks
  const filteredEvents = useMemo(() => {
    if (activeTab === 'all') return safeEvents;
    if (activeTab === 'anpr') {
      return safeEvents.filter(e => e.event_type === 'anpr' || (e.plate_text && e.plate_text !== 'N/A' && e.plate_text !== 'PLATE NOT READ'));
    }
    if (activeTab === 'suspicious') {
      return safeEvents.filter(e => e.event_type === 'suspicious_activity' || e.event_type === 'night_movement');
    }
    if (activeTab === 'critical') {
      return safeEvents.filter(e => {
        const sev = (e.severity || '').toUpperCase();
        if (sev === 'CRITICAL') return true;
        // High-severity intrusions / virtual fence breaches
        return e.event_type === 'intrusion' || (!e.plate_text && e.object_type);
      });
    }
    if (activeTab === 'high') {
      return safeEvents.filter(e => {
        const sev = (e.severity || '').toUpperCase();
        return sev === 'HIGH' || e.event_type === 'suspicious_activity';
      });
    }
    return safeEvents;
  }, [safeEvents, activeTab]);

  return (
    <aside className="cc-incident-rail" aria-label="Live Incidents Rail">
      {/* Rail Header */}
      <div className="cc-incident-header">
        <div className="cc-incident-header-title">
          <Shield style={{ width: 16, height: 16, color: 'var(--cc-primary)' }} />
          <span>Live Incidents</span>
        </div>

        <div className="cc-incident-header-right">
          <span className="cc-incident-count-pill" title={`Displaying latest ${filteredEvents.length} events`}>
            LATEST {filteredEvents.length}
          </span>
          <button
            className="cc-incident-view-all"
            onClick={onViewAll}
            title="View All Incidents in Incident Management"
            type="button"
          >
            View All
          </button>
        </div>
      </div>

      {/* Filter Chips Bar */}
      <div className="cc-incident-filters" role="tablist" aria-label="Filter Incidents">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            role="tab"
            aria-selected={activeTab === f.id}
            className={`cc-filter-chip ${activeTab === f.id ? 'active' : ''}`}
            onClick={() => onSelectTab && onSelectTab(f.id)}
            type="button"
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Scrollable Incidents List */}
      <div className="cc-incident-list" role="region" aria-live="polite">
        {filteredEvents.length === 0 ? (
          <div className="cc-incident-empty">
            <ShieldCheck style={{ width: 32, height: 32, color: 'var(--cc-text-muted)' }} />
            <div>No incidents match this filter.</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--cc-text-subtle)' }}>
              Surveillance perimeter secure.
            </div>
          </div>
        ) : (
          filteredEvents.slice(0, 35).map((ev, idx) => (
            <IncidentItem
              key={ev.id || `${ev.camera_id}-${ev.timestamp}-${idx}`}
              event={ev}
              onOpenLightbox={onOpenLightbox}
              onOpenIncident={onOpenIncident}
            />
          ))
        )}
      </div>
    </aside>
  );
}
