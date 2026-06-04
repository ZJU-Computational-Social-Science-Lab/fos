import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResultsView } from './ResultsView';
import { useSimulationStore } from '@/store';

const labels = {
  noData: 'No data', generate: 'Generate', generating: 'Generating', metric: 'Metric',
  exportCsv: 'CSV', exportReport: 'Report', noActivity: 'No activity',
  reportSummary: 'Summary', reportNoSummary: 'None', reportFinalValues: 'Finals',
  reportAgent: 'Agent', reportFinalValue: 'Final',
};
const agent = (id: string, name: string, history: Record<string, number[]>) => ({
  id, name, role: '', avatarUrl: '', profile: '', llmConfig: { provider: 'mock', model: 'default' },
  properties: {}, history, memory: [], knowledgeBase: [],
});
const sim = (name: string) => ({ id: 's1', name, templateId: 't', status: 'active', createdAt: '', timeConfig: {}, socialNetwork: {} });

describe('ResultsView', () => {
  it('renders the trajectory chart with real agent data plus the generate and export buttons', () => {
    useSimulationStore.setState({
      currentSimulation: sim('Public goods'),
      agents: [agent('a', 'Alice', { score: [10, 12, 15] }), agent('b', 'Bob', { score: [8, 9, 9] })],
      logs: [{ id: 'l1', nodeId: 'n1', round: 1, type: 'AGENT_ACTION', agentId: 'a', content: 'x', timestamp: '2026-05-21T10:00:00.000Z' }],
      resultsSummary: null, isGeneratingResultsSummary: false, resultsSummaryError: null,
    } as any);
    const { container } = render(<ResultsView labels={labels} language="en" />);
    expect(container.querySelectorAll('polyline')).toHaveLength(2);
    expect(screen.getByText('Alice')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Generate' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'CSV' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Report' })).toBeTruthy();
  });

  it('falls back to activity bars when no metrics are recorded', () => {
    useSimulationStore.setState({
      currentSimulation: sim('Discussion'),
      agents: [agent('a', 'Alice', {})],
      logs: [
        { id: 'l1', nodeId: 'n1', round: 1, type: 'AGENT_SAY', agentId: 'a', content: 'x', timestamp: '2026-05-21T10:00:00.000Z' },
        { id: 'l2', nodeId: 'n1', round: 2, type: 'AGENT_SAY', agentId: 'a', content: 'y', timestamp: '2026-05-21T10:00:01.000Z' },
      ],
      resultsSummary: null, isGeneratingResultsSummary: false, resultsSummaryError: null,
    } as any);
    const { container } = render(<ResultsView labels={labels} language="en" />);
    expect(container.querySelectorAll('polyline')).toHaveLength(0);
    expect(screen.getByText('Alice')).toBeTruthy();
    expect(screen.getByText('2')).toBeTruthy();
  });

  it('shows the no-data message when there is no simulation', () => {
    useSimulationStore.setState({ currentSimulation: null, agents: [], logs: [], resultsSummary: null, isGeneratingResultsSummary: false, resultsSummaryError: null } as any);
    render(<ResultsView labels={labels} language="en" />);
    expect(screen.getByText('No data')).toBeTruthy();
  });

  it('does not render the generate button in the activity fallback (no scored metrics)', () => {
    useSimulationStore.setState({
      currentSimulation: sim('Discussion'),
      agents: [agent('a', 'Alice', {})],
      logs: [
        { id: 'l1', nodeId: 'n1', round: 1, type: 'AGENT_SAY', agentId: 'a', content: 'x', timestamp: '2026-05-21T10:00:00.000Z' },
        { id: 'l2', nodeId: 'n1', round: 2, type: 'AGENT_SAY', agentId: 'a', content: 'y', timestamp: '2026-05-21T10:00:01.000Z' },
      ],
      resultsSummary: null, isGeneratingResultsSummary: false, resultsSummaryError: null,
    } as any);
    render(<ResultsView labels={labels} language="en" />);
    expect(screen.queryByRole('button', { name: 'Generate' })).toBeNull();
  });
});
