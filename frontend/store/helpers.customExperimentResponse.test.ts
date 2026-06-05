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
});
