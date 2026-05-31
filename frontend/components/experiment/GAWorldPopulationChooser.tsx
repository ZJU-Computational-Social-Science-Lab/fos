/**
 * This file shows the first GAWorld resident picker in the Agents step.
 *
 * Each part does one simple job:
 * - PopulationChooserOption draws one count choice card.
 * - GAWorldPopulationChooser lets the user pick how many residents to load.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';
import { RECOMMENDED_STARTER_POPULATION, STARTER_POPULATION_OPTIONS } from './gaworldStarterCohorts';

interface PopulationChooserOptionProps {
  count: number;
  selected: boolean;
  recommended: boolean;
  onClick: (count: number) => void;
}

function PopulationChooserOption({
  count,
  selected,
  recommended,
  onClick,
}: PopulationChooserOptionProps) {
  const { t } = useTranslation();
  const label = t('experimentBuilder.step4.gaworld.populationOptionLabel', {
    count,
    defaultValue: `${count} residents`,
  });
  const description = count === 50
    ? t('experimentBuilder.step4.gaworld.populationOptionFull', {
      defaultValue: 'Load the full city.',
    })
    : t('experimentBuilder.step4.gaworld.populationOptionStarter', {
      count,
      defaultValue: `Start with ${count} residents for a lighter run.`,
    });

  return (
    <button
      type="button"
      onClick={() => onClick(count)}
      className="rounded-lg border p-4 text-left transition-all"
      aria-pressed={selected}
      aria-label={label}
      style={selected
        ? { background: 'var(--ss-brand-soft)', borderColor: 'var(--ss-brand-primary)' }
        : { background: 'var(--ss-page-surface)', borderColor: 'var(--ss-border)' }}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-base font-semibold" style={{ color: 'var(--ss-heading)' }}>
            {label}
          </div>
          <div className="mt-1 text-sm" style={{ color: 'var(--ss-text-muted)' }}>
            {description}
          </div>
        </div>
        {recommended && (
          <span
            className="rounded-full px-2 py-1 text-xs font-medium"
            style={{ background: 'var(--ss-accent-warm-soft)', color: 'var(--ss-heading)' }}
          >
            {t('experimentBuilder.step4.gaworld.recommended', { defaultValue: 'Recommended' })}
          </span>
        )}
      </div>
    </button>
  );
}

interface GAWorldPopulationChooserProps {
  selectedCount: number;
  isLoading: boolean;
  onSelectCount: (count: number) => void;
  onLoadResidents: () => void;
}

export function GAWorldPopulationChooser({
  selectedCount,
  isLoading,
  onSelectCount,
  onLoadResidents,
}: GAWorldPopulationChooserProps) {
  const { t } = useTranslation();

  return (
    <div
      className="rounded-lg border p-4"
      style={{ background: 'var(--ss-page-surface)', borderColor: 'var(--ss-border)' }}
    >
      <h4 className="font-semibold" style={{ color: 'var(--ss-heading)' }}>
        {t('experimentBuilder.step4.gaworld.populationTitle', {
          defaultValue: 'Choose starting population',
        })}
      </h4>
      <p className="mt-2 text-sm" style={{ color: 'var(--ss-text)' }}>
        {t('experimentBuilder.step4.gaworld.populationHint', {
          defaultValue: 'GAWorld includes 50 residents. Start with a smaller group for a lighter, more readable run, or load the full city.',
        })}
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {STARTER_POPULATION_OPTIONS.map((count) => (
          <PopulationChooserOption
            key={count}
            count={count}
            selected={selectedCount === count}
            recommended={count === RECOMMENDED_STARTER_POPULATION}
            onClick={onSelectCount}
          />
        ))}
      </div>

      <div className="mt-4 flex justify-end">
        <Button type="button" onClick={onLoadResidents} disabled={isLoading}>
          {isLoading
            ? t('experimentBuilder.step4.gaworld.loadingResidents', { defaultValue: 'Loading residents...' })
            : t('experimentBuilder.step4.gaworld.loadResidents', { defaultValue: 'Load residents' })}
        </Button>
      </div>
    </div>
  );
}

export default GAWorldPopulationChooser;
