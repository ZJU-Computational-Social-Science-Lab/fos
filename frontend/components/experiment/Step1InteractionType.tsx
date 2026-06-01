/**
 * Step 1: Scenario Picker
 *
 * Displays a grid of scenario cards fetched from the backend.
 * Users select one scenario to proceed with experiment configuration.
 */

import React, { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useExperimentBuilder } from '../../store/experiment-builder';
import { getAllScenarios, ScenarioData } from '../../services/scenarios';
import {
  deleteExperimentTemplate,
  listExperimentTemplates,
  mapExperimentTemplateToScenario,
  type PersonalTemplateScenarioData,
} from '../../services/experiment-templates';

type SelectableScenario = ScenarioData | PersonalTemplateScenarioData;

interface ScenarioCardProps {
  scenario: SelectableScenario;
  selected: boolean;
  onClick: () => void;
  onDelete?: () => void;
  deleting?: boolean;
  t: any;
}

const CATEGORY_ORDER = [
  'game_theory',
  'discussion',
  'spatial',
  'social_deduction',
  'sociology',
  'custom',
] as const;

const CATEGORY_COLORS: Record<string, string> = {
  game_theory: '#3b82f6',
  discussion: '#10b981',
  spatial: '#f59e0b',
  social_deduction: '#ef4444',
  sociology: '#ec4899',
  custom: '#6b7280',
};

const ScenarioCard: React.FC<ScenarioCardProps> = ({
  scenario,
  selected,
  onClick,
  onDelete,
  deleting = false,
  t,
}) => {
  // Build translation key for scenario name/description
  const scenarioNameKey = `scenario.${scenario.category}.${scenario.id}.name`;
  const scenarioDescKey = `scenario.${scenario.category}.${scenario.id}.description`;

  // Use translation with fallback to original value
  const translatedName = t(scenarioNameKey, scenario.name);
  const translatedDesc = t(scenarioDescKey, scenario.description);

  const isPersonalTemplate = 'templateSource' in scenario && scenario.templateSource === 'user_template';

  return (
    <div
      className={`
        relative rounded-lg border-2 transition-all
        ${selected ? 'shadow-sm' : 'hover:shadow-sm'}
      `}
      style={selected
        ? { background: 'var(--ss-accent-warm-soft)', borderColor: 'var(--ss-brand-primary)', boxShadow: '0 0 0 2px var(--ss-brand-soft)' }
        : { background: 'var(--ss-page-surface)', borderColor: 'var(--ss-border)' }
      }
    >
      <button onClick={onClick} className="w-full p-4 text-left">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="mb-1 flex items-center gap-2">
              <h3 className="font-semibold truncate pr-2" style={{ color: 'var(--ss-heading)' }}>
                {translatedName}
              </h3>
            </div>
            <p className="text-sm line-clamp-2" style={{ color: 'var(--ss-text)' }}>
              {translatedDesc}
            </p>
          </div>
          <div className="ml-2 flex-shrink-0">
            {selected ? (
              <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{ background: 'var(--ss-brand-primary)' }}>
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            ) : (
              <div className="w-6 h-6 rounded-full border-2" style={{ borderColor: 'var(--ss-border-strong)' }} />
            )}
          </div>
        </div>
      </button>

      {isPersonalTemplate && onDelete ? (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          disabled={deleting}
          className="absolute right-3 top-3 rounded-lg border p-1.5 transition disabled:opacity-60"
          style={{ borderColor: 'var(--ss-border)', background: 'var(--ss-surface)', color: 'var(--ss-text-muted)' }}
          title={t('experimentBuilder.step1.deletePersonalTemplate', { defaultValue: 'Delete template' })}
          aria-label={t('experimentBuilder.step1.deletePersonalTemplate', { defaultValue: 'Delete template' })}
        >
          <Trash2 size={14} />
        </button>
      ) : null}
    </div>
  );
};

export const Step1InteractionType: React.FC = () => {
  const { t } = useTranslation();
  const {
    selectedScenarioId,
    setSelectedScenarioId,
    setSelectedScenarioData,
    setScenarioParams,
    markStepComplete,
  } = useExperimentBuilder();

  const [scenarios, setScenarios] = useState<SelectableScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openCategories, setOpenCategories] = useState<Set<string>>(new Set());
  const [deletingTemplateId, setDeletingTemplateId] = useState<number | null>(null);

  useEffect(() => {
    const fetchScenarios = async () => {
      setLoading(true);
      setError(null);
      try {
        const [scenarioData, templateData] = await Promise.all([
          getAllScenarios(),
          listExperimentTemplates().catch(() => ({ templates: [], count: 0 })),
        ]);
        const personalTemplates = templateData.templates.map(mapExperimentTemplateToScenario);
        setScenarios([...scenarioData, ...personalTemplates]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch scenarios');
      } finally {
        setLoading(false);
      }
    };

    fetchScenarios();
  }, []);

  const toggleCategory = (category: string) => {
    setOpenCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  // Auto-expand selected scenario's category
  useEffect(() => {
    if (selectedScenarioId) {
      const scenario = scenarios.find(s => s.id === selectedScenarioId);
      if (scenario) {
        setOpenCategories(prev => new Set(prev).add(scenario.category));
      }
    }
  }, [selectedScenarioId, scenarios]);

  const handleSelectScenario = (scenario: SelectableScenario) => {
    setSelectedScenarioId(scenario.id);
    setSelectedScenarioData(scenario);
    if ('templateSource' in scenario && scenario.templateSource === 'user_template') {
      setScenarioParams({ ...(scenario.templateSettings || {}) });
    }
    markStepComplete(1);
  };

  const handleRetry = () => {
    const fetchScenarios = async () => {
      setLoading(true);
      setError(null);
      try {
        const [scenarioData, templateData] = await Promise.all([
          getAllScenarios(),
          listExperimentTemplates().catch(() => ({ templates: [], count: 0 })),
        ]);
        const personalTemplates = templateData.templates.map(mapExperimentTemplateToScenario);
        setScenarios([...scenarioData, ...personalTemplates]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch scenarios');
      } finally {
        setLoading(false);
      }
    };

    fetchScenarios();
  };

  const handleDeleteTemplate = async (scenario: PersonalTemplateScenarioData) => {
    setDeletingTemplateId(scenario.templateId);
    try {
      await deleteExperimentTemplate(scenario.templateId);
      setScenarios((current) => current.filter((item) => item.id !== scenario.id));
      if (selectedScenarioId === scenario.id) {
        setSelectedScenarioId(null);
        setSelectedScenarioData(null);
        setScenarioParams({});
      }
    } finally {
      setDeletingTemplateId(null);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold" style={{ color: 'var(--ss-heading)' }}>
          {t('experimentBuilder.step1.chooseScenario')}
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--ss-text)' }}>
          {t('experimentBuilder.step1.selectTemplate')}
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 mb-2" style={{ borderColor: 'var(--ss-brand-primary)' }} />
            <p className="text-sm" style={{ color: 'var(--ss-text)' }}>{t('common.loading')}</p>
          </div>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="text-center mb-4">
            <svg className="w-12 h-12 mx-auto mb-2" style={{ color: 'var(--ss-danger)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm" style={{ color: 'var(--ss-text)' }}>{error}</p>
          </div>
          <button
            onClick={handleRetry}
            className="px-4 py-2 text-white rounded-lg transition-colors"
            style={{ background: 'var(--ss-brand-primary)' }}
          >
            {t('experimentBuilder.step1.retry')}
          </button>
        </div>
      )}

      {!loading && !error && scenarios.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <p className="text-sm" style={{ color: 'var(--ss-text)' }}>{t('experimentBuilder.step1.noScenariosAvailable')}</p>
        </div>
      )}

      {!loading && !error && scenarios.length > 0 && (
        <div className="space-y-4">
          {CATEGORY_ORDER.map(category => {
            const categoryScenarios = scenarios.filter(s => s.category === category);
            if (categoryScenarios.length === 0) return null;

            const isOpen = openCategories.has(category);
            const color = CATEGORY_COLORS[category] || '#6b7280';

            return (
              <div key={category} className="border rounded-lg" style={{ borderColor: 'var(--ss-border-strong)' }}>
                <button
                  onClick={() => toggleCategory(category)}
                  className="w-full px-4 py-3 flex items-center justify-between"
                  style={{ background: 'var(--ss-page-surface)' }}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="px-2 py-1 rounded text-xs font-medium text-white flex-shrink-0"
                      style={{ backgroundColor: color }}
                    >
                      {t(`scenario.category.${category}`)}
                    </span>
                    <span className="font-medium" style={{ color: 'var(--ss-heading)' }}>
                      {t(`scenario.category.${category}`)}
                    </span>
                    <span className="text-sm" style={{ color: 'var(--ss-text-muted)' }}>
                      {t('experimentBuilder.step1.scenariosCount', { count: categoryScenarios.length })}
                    </span>
                  </div>
                  <svg
                    className={`w-5 h-5 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    style={{ color: 'var(--ss-text-muted)' }}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {isOpen && (
                  <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {categoryScenarios.map(scenario => (
                      <ScenarioCard
                        key={scenario.id}
                        scenario={scenario}
                        selected={selectedScenarioId === scenario.id}
                        onClick={() => handleSelectScenario(scenario)}
                        onDelete={
                          'templateSource' in scenario && scenario.templateSource === 'user_template'
                            ? () => void handleDeleteTemplate(scenario)
                            : undefined
                        }
                        deleting={
                          'templateSource' in scenario && scenario.templateSource === 'user_template'
                            ? deletingTemplateId === scenario.templateId
                            : false
                        }
                        t={t}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
