import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/scenarios', () => ({
  getAllScenarios: vi.fn(),
  getScenario: vi.fn(),
  getScenarioActions: vi.fn(),
  getScenarioDefaultAgents: vi.fn(() => Promise.resolve([
    {
      id: '34',
      name: 'Xu Guilan',
      profile: 'Age: 42',
      role_prompt: 'Real GAWorld profile',
      properties: {
        residence: 'Hangzhou',
      },
      llm_config: {},
    },
  ])),
}));

import { useExperimentBuilder } from './experiment-builder';


describe('Experiment Builder Store', () => {
  beforeEach(() => {
    useExperimentBuilder.getState().reset();
  });

  it('inherits sequential round visibility from scenario defaults', () => {
    useExperimentBuilder.getState().setSelectedScenarioData({
      id: 'policy_erosion',
      name: 'Policy Meaning Erosion',
      category: 'sociology',
      description: 'A hierarchy transmits a policy.',
      interaction_mode: 'sequential',
      parameters: [],
      actions: [],
    });

    expect(useExperimentBuilder.getState().roundVisibility).toBe('sequential');
  });

  it('keeps simultaneous round visibility for simultaneous scenarios', () => {
    useExperimentBuilder.getState().setSelectedScenarioData({
      id: 'social_norm_disruption',
      name: 'Social Norm Disruption',
      category: 'sociology',
      description: 'A new rule is imposed.',
      interaction_mode: 'simultaneous',
      parameters: [],
      actions: [],
    });

    expect(useExperimentBuilder.getState().roundVisibility).toBe('simultaneous');
  });

  it('starts custom scenario with sequential ordering for v1', () => {
    useExperimentBuilder.getState().setSelectedScenarioData({
      id: 'custom',
      name: 'Custom Scenario',
      category: 'custom',
      description: 'Open ended conversation.',
      interaction_mode: 'simultaneous',
      parameters: [],
      actions: [],
    });

    expect(useExperimentBuilder.getState().roundVisibility).toBe('sequential');
  });

  it('test_gaworld_selection_loads_profile_agents', async () => {
    await useExperimentBuilder.getState().loadDefaultAgentsForScenario('gaworld', '34');

    expect(useExperimentBuilder.getState().agentMode).toBe('manual');
    expect(useExperimentBuilder.getState().agentTypes).toEqual([
      {
        id: '34',
        label: 'Xu Guilan',
        count: 1,
        rolePrompt: 'Real GAWorld profile',
        userProfile: 'Age: 42',
        properties: {
          residence: 'Hangzhou',
        },
        providerId: null,
      },
    ]);
  });
});
