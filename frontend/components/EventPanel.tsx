import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Cloud,
  CloudDrizzle,
  AlertTriangle,
  Megaphone,
  Globe,
  Settings,
  X,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Plus,
  Trash2,
  Loader2,
} from 'lucide-react';

export interface ExternalEvent {
  id: string;
  event_type: 'policy' | 'market' | 'news' | 'custom' | 'manual';
  source: string;
  title: string;
  content: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  metadata?: Record<string, unknown>;
  url?: string;
}

interface EventPanelProps {
  simulationId?: string;
  onEventApply?: (event: ExternalEvent) => void;
}

const severityConfig = {
  low: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-700',
    icon: Cloud,
    label: 'low',
  },
  medium: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    text: 'text-yellow-700',
    icon: CloudDrizzle,
    label: 'medium',
  },
  high: {
    bg: 'bg-orange-50',
    border: 'border-orange-200',
    text: 'text-orange-700',
    icon: AlertTriangle,
    label: 'high',
  },
  critical: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-700',
    icon: AlertTriangle,
    label: 'critical',
  },
};

const eventTypeConfig: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string }> = {
  policy: { icon: Globe, color: 'text-purple-600' },
  market: { icon: CloudDrizzle, color: 'text-green-600' },
  news: { icon: Megaphone, color: 'text-blue-600' },
  custom: { icon: Settings, color: 'text-gray-600' },
  manual: { icon: Plus, color: 'text-indigo-600' },
};

function EventCard({
  event,
  onApply,
}: {
  event: ExternalEvent;
  onApply?: (event: ExternalEvent) => void;
}) {
  const { t } = useTranslation();
  const severity = severityConfig[event.severity] || severityConfig.medium;
  const typeConfig = eventTypeConfig[event.event_type] || eventTypeConfig.custom;
  const SeverityIcon = severity.icon;
  const TypeIcon = typeConfig.icon;

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <div className={`border rounded-lg p-4 ${severity.bg} ${severity.border}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <TypeIcon className={`w-4 h-4 ${typeConfig.color}`} />
          <span className="text-sm font-medium capitalize">{event.event_type}</span>
          <span className="text-xs text-gray-500">• {event.source}</span>
        </div>
        <div className={`flex items-center gap-1 ${severity.text}`}>
          <SeverityIcon className="w-3 h-3" />
          <span className="text-xs capitalize">{t(`event.severity.${severity.label}`)}</span>
        </div>
      </div>

      <h4 className="font-medium text-gray-900 mb-1">{event.title}</h4>
      <p className="text-sm text-gray-600 mb-2">{event.content}</p>

      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">{formatTime(event.timestamp)}</span>
        <div className="flex gap-2">
          {event.url && (
            <a
              href={event.url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2 py-1 text-xs text-blue-600 hover:text-blue-700"
            >
              {t('event.viewSource')}
            </a>
          )}
          {onApply && (
            <button
              onClick={() => onApply(event)}
              className="px-3 py-1 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 transition-colors"
            >
              {t('event.apply')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export const EventPanel: React.FC<EventPanelProps> = ({ simulationId, onEventApply }) => {
  const { t } = useTranslation();
  const [events, setEvents] = useState<ExternalEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'policy' | 'market' | 'news' | 'manual'>('all');

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const { apiClient } = await import('../services/client');
      const params = new URLSearchParams();
      if (simulationId) params.set('simulation_id', simulationId);
      const response = await apiClient.get(`/events/external?${params.toString()}`);
      let events = response.data?.events || [];

      // Auto-seed demo events if queue is empty
      if (events.length === 0 && simulationId) {
        try {
          await apiClient.post(`/events/seed?simulation_id=${simulationId}`);
          const reResp = await apiClient.get(`/events/external?${params.toString()}`);
          events = reResp.data?.events || [];
        } catch (e) {
          console.warn('Auto-seed failed', e);
        }
      }

      setEvents(events);
    } catch (e) {
      console.warn('Failed to fetch external events', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [simulationId]);

  const handleApply = (event: ExternalEvent) => {
    onEventApply?.(event);
  };

  const filteredEvents = activeTab === 'all'
    ? events
    : events.filter(e => e.event_type === activeTab);

  const tabCounts = {
    all: events.length,
    policy: events.filter(e => e.event_type === 'policy').length,
    market: events.filter(e => e.event_type === 'market').length,
    news: events.filter(e => e.event_type === 'news').length,
    manual: events.filter(e => e.event_type === 'manual').length,
  };

  return (
    <div className="border rounded-lg bg-white shadow-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-indigo-600" />
          <h3 className="font-medium text-gray-900">{t('event.panel.title')}</h3>
          <span className="text-xs text-gray-500">({events.length})</span>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="border-t">
          <div className="flex border-b overflow-x-auto">
            {(['all', 'policy', 'market', 'news', 'manual'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                {t(`event.tab.${tab}`)}
                {tabCounts[tab] > 0 && (
                  <span className="ml-1 text-xs text-gray-400">({tabCounts[tab]})</span>
                )}
              </button>
            ))}
          </div>

          <div className="p-4 max-h-96 overflow-y-auto">
            {loading && events.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="animate-spin h-6 w-6 text-indigo-600" />
                <span className="ml-2 text-gray-600">{t('event.loading')}</span>
              </div>
            ) : filteredEvents.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Globe className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p>{t('event.empty')}</p>
                <p className="text-xs text-gray-400 mt-1">{t('event.emptyHint')}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredEvents.map(event => (
                  <EventCard key={event.id} event={event} onApply={onEventApply ? handleApply : undefined} />
                ))}
              </div>
            )}
          </div>

          <div className="p-3 border-t bg-gray-50 flex justify-between">
            <button
              onClick={fetchEvents}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              {t('event.refresh')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default EventPanel;