import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/services/client', () => ({ apiClient: { post: vi.fn() } }));

import { apiClient } from '@/services/client';
import { useSimulationStore } from '@/store';
import type { Agent, LogEntry } from '@/types';

const post = vi.mocked(apiClient.post);

const agent = (id: string, name: string, history: Record<string, number[]>): Agent => ({
  id, name, role: '', avatarUrl: '', profile: '',
  llmConfig: { provider: 'mock', model: 'default' },
  properties: {}, history, memory: [], knowledgeBase: [],
});

const logWithOutcome = (agentId: string, round: number, outcome: Record<string, number>): LogEntry => ({
  id: `lo-${round}-${agentId}`,
  nodeId: 'n1',
  round,
  type: 'AGENT_ACTION',
  agentId,
  content: 'x',
  timestamp: '2026-05-21T10:00:00.000Z',
  outcome,
});

beforeEach(() => {
  post.mockReset();
  useSimulationStore.setState({
    agents: [agent('a', 'Alice', { score: [10, 12, 15] })],
    currentProviderId: 7,
    resultsSummary: null,
    isGeneratingResultsSummary: false,
    resultsSummaryError: null,
  } as any);
});

describe('generateResultsSummary', () => {
  it('sends the computed metrics to the LLM and stores the returned prose', async () => {
    post.mockResolvedValue({ data: { text: 'The agents cooperated.' } } as any);

    await (useSimulationStore.getState() as any).generateResultsSummary('Public goods game', 'en');

    expect(post).toHaveBeenCalledTimes(1);
    const [endpoint, body] = post.mock.calls[0] as any;
    expect(endpoint).toBe('llm/refine_report');
    expect(body.provider_id).toBe(7);
    expect(body.prompt).toContain('- Alice: 10, 12, 15 (final: 15)');

    const s = useSimulationStore.getState() as any;
    expect(s.resultsSummary).toBe('The agents cooperated.');
    expect(s.isGeneratingResultsSummary).toBe(false);
    expect(s.resultsSummaryError).toBeNull();
  });

  it('records the error and rethrows when the LLM call fails, storing no fake summary', async () => {
    post.mockRejectedValue(new Error('network down'));

    await expect(
      (useSimulationStore.getState() as any).generateResultsSummary('X', 'en'),
    ).rejects.toThrow('network down');

    const s = useSimulationStore.getState() as any;
    expect(s.resultsSummary).toBeNull();
    expect(s.isGeneratingResultsSummary).toBe(false);
    expect(s.resultsSummaryError).toBe('network down');
  });

  it('throws when no LLM provider is selected, without calling the LLM', async () => {
    useSimulationStore.setState({ currentProviderId: null } as any);
    await expect(
      (useSimulationStore.getState() as any).generateResultsSummary('X', 'en'),
    ).rejects.toThrow();
    expect(post).not.toHaveBeenCalled();
    expect((useSimulationStore.getState() as any).resultsSummary).toBeNull();
  });

  it('throws when there are no scored metrics, without calling the LLM', async () => {
    useSimulationStore.setState({ agents: [agent('a', 'Alice', {})] } as any);
    await expect(
      (useSimulationStore.getState() as any).generateResultsSummary('X', 'en'),
    ).rejects.toThrow();
    expect(post).not.toHaveBeenCalled();
  });

  it('generates a summary by hydrating history from log outcomes when agent.history is empty', async () => {
    post.mockResolvedValue({ data: { text: 'The agents cooperated.' } } as any);
    useSimulationStore.setState({
      agents: [
        agent('a', 'Alice', {}),
        agent('b', 'Bob', {}),
      ],
      logs: [
        logWithOutcome('a', 1, { payoff: 10 }),
        logWithOutcome('b', 1, { payoff: 8 }),
        logWithOutcome('a', 2, { payoff: 12 }),
        logWithOutcome('b', 2, { payoff: 9 }),
      ],
      currentProviderId: 7,
    } as any);

    await (useSimulationStore.getState() as any).generateResultsSummary('Test', 'en');

    const s = useSimulationStore.getState() as any;
    expect(s.resultsSummary).toBe('The agents cooperated.');
    expect(s.resultsSummaryError).toBeNull();
  });
});
