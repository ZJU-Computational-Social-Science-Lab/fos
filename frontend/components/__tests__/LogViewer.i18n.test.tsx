/**
 * This file checks that backend events are mapped to log text using the real app language setting.
 * test_map_backend_events_to_logs_uses_english_labels_by_default checks English labels are used by default.
 * test_map_backend_events_to_logs_uses_chinese_labels_after_language_switch checks Chinese labels after switching to zh.
 * test_map_backend_events_to_logs_changes_output_when_language_changes checks output changes when language changes at runtime.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import i18n from '../../i18n';
import { mapBackendEventsToLogs } from '../../store/helpers';

describe('LogViewer i18n runtime seam', () => {
  beforeEach(() => {
    (i18n as { language: string }).language = 'en';
  });

  afterEach(() => {
    (i18n as { language: string }).language = 'en';
  });

  it('test_map_backend_events_to_logs_uses_english_labels_by_default', () => {
    const logs = mapBackendEventsToLogs([{ type: 'plan_update', data: { agent: 'TestAgent' } }], 'node-1', 1, [], true);
    expect(i18n.language).toBe('en');
    expect(logs[0]?.content).toBe('Plan updated');
  });

  it('test_map_backend_events_to_logs_uses_chinese_labels_after_language_switch', () => {
    (i18n as { language: string }).language = 'zh';
    const logs = mapBackendEventsToLogs([{ type: 'plan_update', data: { agent: 'TestAgent' } }], 'node-1', 1, [], true);
    expect(i18n.language).toBe('zh');
    expect(logs[0]?.content).toBe('更新计划');
  });

  it('test_map_backend_events_to_logs_changes_output_when_language_changes', () => {
    const event = [{ type: 'plan_update', data: { agent: 'TestAgent' } }];
    const englishLogs = mapBackendEventsToLogs(event, 'node-1', 1, [], true);
    (i18n as { language: string }).language = 'zh';
    const chineseLogs = mapBackendEventsToLogs(event, 'node-1', 1, [], true);
    expect(englishLogs[0]?.content).toBe('Plan updated');
    expect(chineseLogs[0]?.content).toBe('更新计划');
    expect(englishLogs[0]?.content).not.toBe(chineseLogs[0]?.content);
  });
});
