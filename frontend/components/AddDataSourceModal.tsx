import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';
import { dataSourceApi, DataSource } from '../services/dataSourceApi';

interface AddDataSourceModalProps {
  source?: DataSource | null;
  onClose: () => void;
}

export const AddDataSourceModal: React.FC<AddDataSourceModalProps> = ({ source, onClose }) => {
  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: source?.name || '',
    api_url: source?.api_url || '',
    auth_type: source?.auth_type || 'none',
    auth_token: source?.auth_token || '',
    poll_interval_seconds: source?.poll_interval_seconds || 300,
    event_type: source?.event_type || 'market',
    is_global: source?.is_global ?? true,
    simulation_id: source?.simulation_id || '',
    field_mapping: source?.field_mapping || { title_path: '', content_path: '', timestamp_path: '', url_path: '' },
    is_enabled: source?.is_enabled ?? true,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.api_url.trim()) return;

    setSaving(true);
    try {
      const payload = {
        ...form,
        simulation_id: form.is_global ? null : (form.simulation_id || null),
        poll_interval_seconds: parseInt(String(form.poll_interval_seconds), 10),
        field_mapping: form.field_mapping,
      };

      if (source?.id) {
        await dataSourceApi.update(source.id, payload);
      } else {
        await dataSourceApi.create(payload);
      }
      onClose();
    } catch (e) {
      console.warn('Failed to save data source', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-medium">{source ? t('dataSource.editTitle') : t('dataSource.addTitle')}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.name')} *</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              required
            />
          </div>

          {/* API URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.apiUrl')} *</label>
            <input
              type="url"
              value={form.api_url}
              onChange={e => setForm(f => ({ ...f, api_url: e.target.value }))}
              placeholder="https://api.example.com/events"
              className="w-full border rounded px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              required
            />
          </div>

          {/* Auth Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.authType')}</label>
            <div className="flex gap-4">
              {(['none', 'bearer', 'api_key'] as const).map(type => (
                <label key={type} className="flex items-center gap-1.5 text-sm">
                  <input
                    type="radio"
                    name="auth_type"
                    value={type}
                    checked={form.auth_type === type}
                    onChange={e => setForm(f => ({ ...f, auth_type: e.target.value as typeof form.auth_type }))}
                  />
                  {t(`dataSource.form.auth${type.charAt(0).toUpperCase() + type.slice(1).replace('_', '')}`)}
                </label>
              ))}
            </div>
          </div>

          {/* Auth Token */}
          {(form.auth_type === 'bearer' || form.auth_type === 'api_key') && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.authToken')}</label>
              <input
                type="password"
                value={form.auth_token}
                onChange={e => setForm(f => ({ ...f, auth_token: e.target.value }))}
                className="w-full border rounded px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                placeholder="••••••••"
              />
            </div>
          )}

          {/* Poll Interval */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.pollInterval')}</label>
            <input
              type="number"
              value={form.poll_interval_seconds}
              onChange={e => setForm(f => ({ ...f, poll_interval_seconds: parseInt(e.target.value, 10) }))}
              min={60}
              max={86400}
              className="w-full border rounded px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
            />
          </div>

          {/* Event Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.eventType')}</label>
            <select
              value={form.event_type}
              onChange={e => setForm(f => ({ ...f, event_type: e.target.value }))}
              className="w-full border rounded px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none bg-white"
            >
              <option value="market">{t('dataSource.form.eventTypeMarket')}</option>
              <option value="policy">{t('dataSource.form.eventTypePolicy')}</option>
              <option value="news">{t('dataSource.form.eventTypeNews')}</option>
              <option value="custom">{t('dataSource.form.eventTypeCustom')}</option>
            </select>
          </div>

          {/* Scope */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.scope')}</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  name="is_global"
                  value="true"
                  checked={form.is_global === true}
                  onChange={() => setForm(f => ({ ...f, is_global: true }))}
                />
                {t('dataSource.form.scopeGlobal')}
              </label>
              <label className="flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  name="is_global"
                  value="false"
                  checked={form.is_global === false}
                  onChange={() => setForm(f => ({ ...f, is_global: false }))}
                />
                {t('dataSource.form.scopeSimulation')}
              </label>
            </div>
          </div>

          {/* Simulation ID (shown when is_global is false) */}
          {!form.is_global && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('dataSource.form.simulationId')}</label>
              <input
                type="text"
                value={form.simulation_id}
                onChange={e => setForm(f => ({ ...f, simulation_id: e.target.value }))}
                className="w-full border rounded px-3 py-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
              />
            </div>
          )}

          {/* Field Mapping */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('dataSource.form.fieldMapping')}</label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 block mb-0.5">{t('dataSource.form.titleField')}</label>
                <input
                  type="text"
                  value={form.field_mapping.title_path || ''}
                  onChange={e => setForm(f => ({ ...f, field_mapping: { ...f.field_mapping, title_path: e.target.value } }))}
                  placeholder="data.items[].title"
                  className="w-full border rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-0.5">{t('dataSource.form.contentField')}</label>
                <input
                  type="text"
                  value={form.field_mapping.content_path || ''}
                  onChange={e => setForm(f => ({ ...f, field_mapping: { ...f.field_mapping, content_path: e.target.value } }))}
                  placeholder="data.items[].content"
                  className="w-full border rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-0.5">{t('dataSource.form.timestampField')}</label>
                <input
                  type="text"
                  value={form.field_mapping.timestamp_path || ''}
                  onChange={e => setForm(f => ({ ...f, field_mapping: { ...f.field_mapping, timestamp_path: e.target.value } }))}
                  placeholder="data.items[].timestamp"
                  className="w-full border rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-0.5">{t('dataSource.form.urlField')}</label>
                <input
                  type="text"
                  value={form.field_mapping.url_path || ''}
                  onChange={e => setForm(f => ({ ...f, field_mapping: { ...f.field_mapping, url_path: e.target.value } }))}
                  placeholder="data.items[].url"
                  className="w-full border rounded px-2 py-1.5 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2 border-t">
            <button
              type="submit"
              disabled={saving || !form.name.trim() || !form.api_url.trim()}
              className="flex-1 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? '...' : t('dataSource.form.save')}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50"
            >
              {t('dataSource.form.cancel')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};