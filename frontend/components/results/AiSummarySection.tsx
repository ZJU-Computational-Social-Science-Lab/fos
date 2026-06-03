// This file shows a results summary area with a button, an error message, and a summary message.
// AiSummarySection shows the button text from the labels it is given, shows an error when there is one,
// and shows the summary only when a summary exists and loading has finished.
import React from 'react';

interface AiSummarySectionProps {
  summary: string | null;
  isGenerating: boolean;
  error: string | null;
  onGenerate: () => void;
  labels: {
    generate: string;
    generating: string;
  };
}

export function AiSummarySection({
  summary,
  isGenerating,
  error,
  onGenerate,
  labels,
}: AiSummarySectionProps): React.JSX.Element {
  return (
    <section>
      <button type="button" onClick={onGenerate} disabled={isGenerating}>
        {isGenerating ? labels.generating : labels.generate}
      </button>
      {error !== null ? <div role="alert">{error}</div> : null}
      {summary !== null && isGenerating === false ? <div>{summary}</div> : null}
    </section>
  );
}
