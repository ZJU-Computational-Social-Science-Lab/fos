/**
 * This file checks that log labels use the real app language setting.
 * test_map_backend_events_to_logs_uses_english_labels_by_default checks English labels are used by default.
 * test_map_backend_events_to_logs_uses_chinese_labels_after_language_switch checks Chinese labels after switching to zh.
 * test_map_backend_events_to_logs_changes_output_when_language_changes checks output changes when language changes at runtime.
 * test_step_group_label_includes_the_step_number_in_english checks the English log step title has a number slot.
 * test_step_group_label_includes_the_step_number_in_chinese checks the Chinese log step title has a number slot.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import i18n from '../../i18n';
import en from '../../locales/en.json';
import zh from '../../locales/zh.json';
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

  it('test_step_group_label_includes_the_step_number_in_english', () => {
    expect(en.components.logViewer.stepGroup).toBe('Step {{step}}');
  });

  it('test_step_group_label_includes_the_step_number_in_chinese', () => {
    expect(zh.components.logViewer.stepGroup).toBe('步骤 {{step}}');
  });

  it('test_policy_thread_reply_keeps_discussion_message_visible', () => {
    (i18n as { language: string }).language = 'zh';
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'policy_thread_reply',
          data: {
            kind: 'peer_consult',
            sender: '智能体 3',
            recipient: '智能体 4',
            message: '我们需要统一阶段性薪酬调整的解释口径。',
          },
        },
      ],
      'node-1',
      2,
      [
        { id: 'a3', name: '智能体 3' },
        { id: 'a4', name: '智能体 4' },
      ] as any,
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0]?.type).toBe('AGENT_SAY');
    expect(logs[0]?.agentId).toBe('a3');
    expect(logs[0]?.content).toContain('政策后续讨论回复');
    expect(logs[0]?.content).toContain('智能体 3 -> 智能体 4');
    expect(logs[0]?.content).toContain('统一阶段性薪酬调整');
  });

  it('test_policy_adjustment_event_shows_adjustment_content', () => {
    (i18n as { language: string }).language = 'zh';
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'policy_adjustment_issued',
          data: {
            sender: '智能体 3',
            tier: 'mid',
            recipients: ['智能体 5'],
            message: '【政策调整】统一补充稳岗安排和申诉反馈渠道。',
          },
        },
      ],
      'node-1',
      2,
      [
        { id: 'a3', name: '智能体 3' },
        { id: 'a5', name: '智能体 5' },
      ] as any,
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0]?.type).toBe('ENVIRONMENT');
    expect(logs[0]?.content).toContain('政策调整已发布');
    expect(logs[0]?.content).toContain('智能体 3 (mid)');
    expect(logs[0]?.content).toContain('接收者: 智能体 5');
    expect(logs[0]?.content).toContain('稳岗安排');
  });

  it('test_cascade_network_dead_end_event_shows_blocked_tier_details', () => {
    (i18n as { language: string }).language = 'zh';
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'cascade_network_dead_end',
          data: {
            agent: '智能体 3',
            tier: 'mid',
            next_tier: 'low',
            direct_connections: ['智能体 1'],
            next_tier_candidates: ['智能体 5'],
            next_tier_connections: [],
          },
        },
      ],
      'node-1',
      2,
      [{ id: 'a3', name: '智能体 3' }] as any,
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0]?.type).toBe('SYSTEM');
    expect(logs[0]?.content).toContain('政策传递因网络断点停止');
    expect(logs[0]?.content).toContain('下一层级: low');
    expect(logs[0]?.content).toContain('可达下一层智能体: 无');
  });

  it('test_policy_thread_ignored_event_shows_notice_text', () => {
    (i18n as { language: string }).language = 'zh';
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'policy_thread_ignored',
          data: {
            kind: 'peer_consult',
            agent: '智能体 4',
            notice: '智能体 4 暂未处理该线程。',
          },
        },
      ],
      'node-1',
      2,
      [{ id: 'a4', name: '智能体 4' }] as any,
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0]?.type).toBe('AGENT_METADATA');
    expect(logs[0]?.content).toContain('政策后续讨论暂未回应');
    expect(logs[0]?.content).toContain('智能体 4 暂未处理该线程');
  });
});
