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
  Loader2,
} from 'lucide-react';

export interface ExternalEvent {
  id: string;
  event_type: 'policy' | 'market' | 'news' | 'custom' | 'manual';
  source: string;
  source_name?: string | null;
  title: string;
  content: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  metadata?: Record<string, unknown>;
  url?: string;
  status?: 'pending' | 'applied' | 'dismissed';
}

interface EventPanelProps {
  simulationId?: string;
  onEventApply?: (event: ExternalEvent) => void;
}

const severityConfig = {
  low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', icon: Cloud, label: 'low' },
  medium: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', icon: CloudDrizzle, label: 'medium' },
  high: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', icon: AlertTriangle, label: 'high' },
  critical: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: AlertTriangle, label: 'critical' },
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
    <div className={`border rounded-lg p-4 ${severity.bg} ${severity.border} relative`}>
      {event.source_name && (
        <span className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-indigo-50 text-indigo-600 border border-indigo-100">
          <Globe className="w-3 h-3" />
          {event.source_name}
        </span>
      )}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <TypeIcon className={`w-4 h-4 ${typeConfig.color}`} />
          <span className="text-sm font-medium capitalize">{t(`components.event.tab.${event.event_type}`)}</span>
          <span className="text-xs text-gray-500">• {event.source}</span>
          {event.status && event.status !== 'pending' && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              event.status === 'applied' ? 'bg-green-100 text-green-700' :
              event.status === 'dismissed' ? 'bg-gray-100 text-gray-600' : ''
            }`}>
              {t(`components.event.status.${event.status}`)}
            </span>
          )}
        </div>
        <div className={`flex items-center gap-1 ${severity.text}`}>
          <SeverityIcon className="w-3 h-3" />
          <span className="text-xs capitalize">{t(`components.event.severity.${severity.label}`)}</span>
        </div>
      </div>
      <h4 className="font-medium text-gray-900 mb-1">{event.title}</h4>
      <p className="text-sm text-gray-600 mb-2">{event.content}</p>
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">{formatTime(event.timestamp)}</span>
        <div className="flex gap-2">
          {event.url && (
            <a href={event.url} target="_blank" rel="noopener noreferrer" className="px-2 py-1 text-xs text-blue-600 hover:text-blue-700">
              {t('components.event.viewSource')}
            </a>
          )}
          {onApply && (
            <button
              onClick={() => onApply(event)}
              className="px-3 py-1 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 transition-colors"
            >
              {t('components.event.apply')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface AddEventFormProps {
  onAdd: (event: Omit<ExternalEvent, 'id' | 'timestamp' | 'source'>) => void;
  onCancel: () => void;
  saving: boolean;
}

function AddEventForm({ onAdd, onCancel, saving }: AddEventFormProps) {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [severity, setSeverity] = useState<'low' | 'medium' | 'high' | 'critical'>('medium');
  const [url, setUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    onAdd({ event_type: 'manual', title: title.trim(), content: content.trim(), severity, url: url.trim() || undefined });
  };

  return (
    <form onSubmit={handleSubmit} className="border rounded-lg p-4 bg-indigo-50 border-indigo-200 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-indigo-900">{t('components.event.addTitle')}</h4>
        <button type="button" onClick={onCancel} className="text-gray-400 hover:text-gray-600">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div>
        <label className="text-xs text-gray-600 block mb-1">{t('components.event.form.title')}</label>
        <input
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder={t('components.event.form.titlePlaceholder')}
          className="w-full text-sm border rounded px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
          required
        />
      </div>
      <div>
        <label className="text-xs text-gray-600 block mb-1">{t('components.event.form.content')}</label>
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={t('components.event.form.contentPlaceholder')}
          rows={3}
          className="w-full text-sm border rounded px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none resize-none"
          required
        />
      </div>
      <div className="flex gap-2">
        <div className="flex-1">
          <label className="text-xs text-gray-600 block mb-1">{t('components.event.form.severity')}</label>
          <select
            value={severity}
            onChange={e => setSeverity(e.target.value as typeof severity)}
            className="w-full text-sm border rounded px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none bg-white"
          >
            <option value="low">{t('components.event.severity.low')}</option>
            <option value="medium">{t('components.event.severity.medium')}</option>
            <option value="high">{t('components.event.severity.high')}</option>
            <option value="critical">{t('components.event.severity.critical')}</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-600 block mb-1">{t('components.event.form.url')} ({t('components.event.form.optional')})</label>
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://..."
            className="w-full text-sm border rounded px-2 py-1.5 focus:ring-1 focus:ring-indigo-500 outline-none"
          />
        </div>
      </div>
      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={saving || !title.trim() || !content.trim()}
          className="flex-1 py-1.5 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {saving ? t('components.event.form.saving') + '...' : t('components.event.form.add')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
        >
          {t('components.event.form.cancel')}
        </button>
      </div>
    </form>
  );
}

export const EventPanel: React.FC<EventPanelProps> = ({ simulationId, onEventApply }) => {
  const { t } = useTranslation();
  const [events, setEvents] = useState<ExternalEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'dataSources' | 'policy' | 'market' | 'news' | 'manual'>('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [addingEvent, setAddingEvent] = useState(false);
  // Track last fetch time for auto-update indicator
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const { apiClient } = await import('../services/client');
      const params = new URLSearchParams();
      if (simulationId) params.set('simulation_id', simulationId);
      const response = await apiClient.get(`/events/external?${params.toString()}`);
      const events = response.data?.events || [];

      setEvents(events);
      setLastUpdate(new Date());
    } catch (e) {
      console.warn('Failed to fetch external events', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 30 * 1000);
    return () => clearInterval(interval);
  }, [simulationId]);

  const handleApply = (event: ExternalEvent) => {
    onEventApply?.(event);
  };

  const handleAddEvent = async (eventData: Omit<ExternalEvent, 'id' | 'timestamp' | 'source'>) => {
    if (!simulationId) return;
    setAddingEvent(true);
    try {
      const { apiClient } = await import('../services/client');
      await apiClient.post(`/events/external?simulation_id=${simulationId}`, {
        event_type: eventData.event_type,
        title: eventData.title,
        content: eventData.content,
        severity: eventData.severity,
        url: eventData.url,
        metadata: {},
      });
      setShowAddForm(false);
      fetchEvents();
    } catch (e) {
      console.warn('Failed to add event', e);
    } finally {
      setAddingEvent(false);
    }
  };

  const filteredEvents = activeTab === 'all'
    ? events
    : activeTab === 'dataSources'
    ? events.filter(e => e.source_name)
    : events.filter(e => e.event_type === activeTab);

  const tabCounts = {
    all: events.length,
    dataSources: events.filter(e => e.source_name).length,
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
          <h3 className="font-medium text-gray-900">{t('components.event.panel.title')}</h3>
          <span className="text-xs text-gray-500">({events.length})</span>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="border-t">
          <div className="flex border-b overflow-x-auto">
            {(['all', 'dataSources', 'policy', 'market', 'news', 'manual'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors flex items-center gap-1 ${
                  activeTab === tab ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                {tab === 'dataSources' && <Globe className="w-3.5 h-3.5" />}
                {tab === 'dataSources' ? t('components.event.tab.dataSources') : t(`components.event.tab.${tab}`)}
                {tabCounts[tab] > 0 && <span className="ml-1 text-xs text-gray-400">({tabCounts[tab]})</span>}
              </button>
            ))}
          </div>

          <div className="p-4 max-h-96 overflow-y-auto space-y-3">
            {showAddForm && (
              <AddEventForm onAdd={handleAddEvent} onCancel={() => setShowAddForm(false)} saving={addingEvent} />
            )}
            {loading && events.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="animate-spin h-6 w-6 text-indigo-600" />
                <span className="ml-2 text-gray-600">{t('components.event.loading')}</span>
              </div>
            ) : filteredEvents.length === 0 && !showAddForm ? (
              <div className="text-center py-8 text-gray-500">
                <Globe className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p>{t('components.event.empty')}</p>
                <p className="text-xs text-gray-400 mt-1">{t('components.event.emptyHint')}</p>
              </div>
            ) : (
              filteredEvents.map(event => (
                <EventCard key={event.id} event={event} onApply={onEventApply ? handleApply : undefined} />
              ))
            )}
          </div>

          <div className="p-3 border-t bg-gray-50 flex justify-between items-center">
            <button
              onClick={fetchEvents}
              className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 transition-colors"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              {t('components.event.refresh')}
            </button>
            {lastUpdate && (
              <span className="text-xs text-gray-400">
                {t('components.event.lastUpdate', '更新于')}: {lastUpdate.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default EventPanel;
