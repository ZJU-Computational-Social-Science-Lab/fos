/**
 * Tests for Step 4 GAWorld agent loading.
 *
 * Checks that Step 4 asks for GAWorld profile agents if the builder reaches the
 * agent screen without any agents already loaded.
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Step4Agents } from '../Step4Agents';
import { useExperimentBuilder } from '../../../store/experiment-builder';

vi.mock('../../../store/experiment-builder', () => ({
  useExperimentBuilder: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: () => ({
    getTotalSize: () => 0,
    getVirtualItems: () => [],
  }),
}));

vi.mock('../../wizard/Step2DemographicsEditor', () => ({
  Step2DemographicsEditor: () => <div />,
}));

vi.mock('../../../store/helpers', () => ({
  generateAgentsWithDemographics: vi.fn(),
  isZh: () => false,
}));

describe('Step4Agents GAWorld defaults', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('test_gaworld_step_four_loads_profile_agents_when_empty', async () => {
    const loadDefaultAgentsForScenario = vi.fn(() => Promise.resolve());
    vi.mocked(useExperimentBuilder).mockReturnValue({
      agentMode: 'manual',
      setAgentMode: vi.fn(),
      agentTypes: [],
      addAgentType: vi.fn(),
      removeAgentType: vi.fn(),
      updateAgentType: vi.fn(),
      llmProviders: [],
      selectedProviderId: null,
      setSelectedProviderId: vi.fn(),
      scenarioParams: { agent_ids: '34,35' },
      setScenarioParams: vi.fn(),
      loadProviders: vi.fn(),
      getSelectedProviderId: vi.fn(() => null),
      selectedScenarioId: 'gaworld',
      selectedScenarioData: {
        id: 'gaworld',
        name: 'GAWorld',
        category: 'generative_city',
        description: 'GAWorld',
        parameters: [],
        actions: [],
      },
      loadDefaultAgentsForScenario,
    } as ReturnType<typeof useExperimentBuilder>);

    render(<Step4Agents />);

    await waitFor(() => {
      expect(loadDefaultAgentsForScenario).toHaveBeenCalledWith('gaworld', '34,35');
    });
  });

  it('test_gaworld_step_four_retries_profile_agents_after_failed_load', async () => {
    const loadDefaultAgentsForScenario = vi.fn()
      .mockRejectedValueOnce(new Error('backend was not ready'))
      .mockResolvedValueOnce(undefined);
    vi.mocked(useExperimentBuilder).mockReturnValue({
      agentMode: 'manual',
      setAgentMode: vi.fn(),
      agentTypes: [],
      addAgentType: vi.fn(),
      removeAgentType: vi.fn(),
      updateAgentType: vi.fn(),
      llmProviders: [],
      selectedProviderId: null,
      setSelectedProviderId: vi.fn(),
      scenarioParams: { agent_ids: '34,35' },
      setScenarioParams: vi.fn(),
      loadProviders: vi.fn(),
      getSelectedProviderId: vi.fn(() => null),
      selectedScenarioId: 'gaworld',
      selectedScenarioData: {
        id: 'gaworld',
        name: 'GAWorld',
        category: 'generative_city',
        description: 'GAWorld',
        parameters: [],
        actions: [],
      },
      loadDefaultAgentsForScenario,
    } as ReturnType<typeof useExperimentBuilder>);

    render(<Step4Agents />);

    await waitFor(() => {
      expect(loadDefaultAgentsForScenario).toHaveBeenCalledTimes(2);
    });
  });
});
