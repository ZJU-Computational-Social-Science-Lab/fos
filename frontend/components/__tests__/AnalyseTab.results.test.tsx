import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useSimulationStore } from '@/store';
import { AnalyseTab } from '../AnalyseTab';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));

const agent = (id: string, name: string, history: Record<string, number[]>) => ({
  id, name, role: '', avatarUrl: '', profile: '',
  llmConfig: { provider: 'mock', model: 'default' },
  properties: {}, history, memory: [], knowledgeBase: [],
});

beforeEach(() => {
  useSimulationStore.setState({
    currentSimulation: { id: 's1', name: 'Test sim', templateId: 't', status: 'active', createdAt: '', timeConfig: {}, socialNetwork: {} },
    agents: [agent('a', 'Alice', { score: [10, 12, 15] })],
    logs: [{ id: 'l1', nodeId: 'n1', round: 1, type: 'AGENT_ACTION', agentId: 'a', content: 'x', timestamp: '2026-05-21T10:00:00.000Z' }],
    resultsSummary: null,
    isGeneratingResultsSummary: false,
    resultsSummaryError: null,
    toggleAnalytics: vi.fn(),
    toggleReportModal: vi.fn(),
  } as any);
});

describe('AnalyseTab - results sub-view', () => {
  it('defaults to the results sub-view and renders the real generate button and a chart polyline', () => {
    const { container } = render(<AnalyseTab />);
    expect(screen.getByRole('button', { name: 'results.generate' })).toBeTruthy();
    expect(container.querySelectorAll('polyline').length).toBeGreaterThan(0);
    expect(screen.getByText('Alice')).toBeTruthy();
  });
});
