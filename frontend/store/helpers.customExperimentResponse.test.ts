import { describe, expect, it } from 'vitest';
import { mapBackendEventsToLogs } from './helpers';

describe('mapBackendEventsToLogs - experiment_response', () => {
  it('maps custom experiment response events into AGENT_SAY logs', () => {
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'experiment_response',
          data: {
            agent: 'Resident1',
            action: 'persuade_others',
            response: '我会先提醒邻居保费不高，但家庭风险是真实存在的。',
            reason: '我更看重家庭医疗负担，也更相信政府背书。',
            round: 1,
          },
        },
      ],
      '1',
      1,
      [{ id: 'r1', name: 'Resident1' } as any],
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0].type).toBe('AGENT_SAY');
    expect(logs[0].content).toContain('我会先提醒邻居保费不高');
    expect(logs[0].content).toContain('Why this action');
  });

  it('maps runtime failures into readable system logs', () => {
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'run_failed',
          data: {
            node: 2,
            error: 'gaworld.error.path_not_set',
            message: 'GAWorld path is not configured. Set GAWORLD_PATH on the server.',
          },
        },
      ],
      '2',
      1,
      [],
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0].type).toBe('SYSTEM');
    expect(logs[0].content).toContain('Runtime failed');
    expect(logs[0].content).toContain('GAWorld path is not configured');
  });

  it('maps policy idle events into visible agent metadata logs', () => {
    const logs = mapBackendEventsToLogs(
      [
        {
          type: 'agent_idle',
          data: {
            agent: '智能体 4',
            mode: 'follow_up',
            reason: '智能体 4 当前等待 top 层先处理活跃私有线程。',
          },
        },
      ],
      '3',
      2,
      [{ id: 'a4', name: '智能体 4' } as any],
      true,
    );

    expect(logs).toHaveLength(1);
    expect(logs[0].type).toBe('AGENT_METADATA');
    expect(logs[0].agentId).toBe('a4');
    expect(logs[0].content).toContain('智能体 4');
    expect(logs[0].content).toContain('等待');
  });
});
