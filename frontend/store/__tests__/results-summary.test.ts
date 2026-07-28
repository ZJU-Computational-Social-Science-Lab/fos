/**
 * These tests check how the store builds an AI analysis summary.
 *
 * They verify metric extraction, empty data handling, branch filtering, and the
 * request sent to the summary service.
 */

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
    llmProviders: [{ id: 7, name: 'OpenAI', provider: 'openai', model: 'gpt-test' }],
    resultsSummary: null,
    resultsSummaryMeta: null,
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
    expect(s.resultsSummaryMeta.model).toBe('openai:gpt-test');
    expect(s.resultsSummaryMeta.providerId).toBe(7);
    expect(s.resultsSummaryMeta.inputSnapshot.metrics[0].name).toBe('score');
    expect(s.isGeneratingResultsSummary).toBe(false);
    expect(s.resultsSummaryError).toBeNull();
  });

  it('preserves a provided input snapshot for reproducible AI summaries', async () => {
    post.mockResolvedValue({ data: { text: 'Branch comparison is stable.' } } as any);
    const inputSnapshot = {
      title: 'Snapshot test',
      branch: {
        selectedNodeId: '2',
        selectedBranchLabel: '0.2 - Intervention',
        selectedBranchPath: ['0 - Root', '0.2 - Intervention'],
      },
      metrics: [
        {
          name: 'payoff',
          series: [{ agentId: 'a', agentName: 'Alice', values: [5, 8] }],
          aggregate: [{ round: 1, mean: 5, min: 5, max: 5 }, { round: 2, mean: 8, min: 8, max: 8 }],
          finalValues: [{ agentId: 'a', agentName: 'Alice', value: 8 }],
        },
      ],
      activityByAgent: [{ agentId: 'a', count: 2 }],
      activityByRound: [{ round: 1, count: 1 }, { round: 2, count: 1 }],
      comparison: {
        baselineNodeId: '1',
        interventionNodeId: '2',
        baselineLabel: '0.1 - Baseline',
        interventionLabel: '0.2 - Intervention',
        baselineOnlyEventCount: 1,
        interventionOnlyEventCount: 2,
        agentDiffCount: 1,
        agentDiffFieldCount: 3,
        eventTypeCount: 2,
        summary: 'Intervention changed payoff.',
      },
    };

    await (useSimulationStore.getState() as any).generateResultsSummary('Snapshot test', 'en', inputSnapshot);

    const [, body] = post.mock.calls[0] as any;
    expect(body.prompt).toContain('Branch comparison:');
    expect(body.prompt).toContain('agent_diff_fields=3');

    const s = useSimulationStore.getState() as any;
    expect(s.resultsSummaryMeta.selectedBranchId).toBe('2');
    expect(s.resultsSummaryMeta.inputSnapshot).toEqual(inputSnapshot);
    expect(s.resultsSummaryMeta.generatedAt).toMatch(/T/);
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

  it('surfaces the backend error detail when refine_report fails', async () => {
    post.mockRejectedValue(
      Object.assign(new Error('Request failed with status code 500'), {
        response: { data: { error: 'DeepSeek API: 401 Unauthorized' } },
      }),
    );
    useSimulationStore.setState({
      agents: [
        agent('a', 'Alice', {}),
        agent('b', 'Bob', {}),
      ],
      logs: [
        logWithOutcome('a', 1, { payoff: 10 }),
        logWithOutcome('b', 1, { payoff: 8 }),
      ],
      currentProviderId: 7,
    } as any);

    try {
      await expect(
        (useSimulationStore.getState() as any).generateResultsSummary('Test', 'en'),
      ).rejects.toThrow('Request failed with status code 500');

      expect((useSimulationStore.getState() as any).resultsSummaryError).toBe(
        'DeepSeek API: 401 Unauthorized',
      );
    } finally {
      useSimulationStore.setState({ logs: [] } as any);
    }
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

  it('builds the summary from the selected branch path only', async () => {
    post.mockResolvedValue({ data: { text: 'Branch A only.' } } as any);
    useSimulationStore.setState({
      selectedNodeId: '4',
      nodes: [
        { id: '0', parentId: null, name: 'Root', depth: 0, isLeaf: false },
        { id: '1', parentId: '0', name: 'Branch A', depth: 1, isLeaf: false },
        { id: '2', parentId: '0', name: 'Branch B', depth: 1, isLeaf: false },
        { id: '4', parentId: '1', name: 'Leaf A', depth: 2, isLeaf: true },
        { id: '5', parentId: '2', name: 'Leaf B', depth: 2, isLeaf: true },
      ],
      agents: [agent('a', 'Alice', {})],
      logs: [
        { ...logWithOutcome('a', 1, { amount: 5 }), id: 'branch-a', nodeId: '4' },
        { ...logWithOutcome('a', 1, { amount: 10 }), id: 'branch-b', nodeId: '5' },
      ],
      currentProviderId: 7,
    } as any);

    await (useSimulationStore.getState() as any).generateResultsSummary('Test', 'en');

    const [, body] = post.mock.calls[0] as any;
    expect(body.prompt).toContain('- Alice: 5 (final: 5)');
    expect(body.prompt).not.toContain('- Alice: 10 (final: 10)');
  });
});
