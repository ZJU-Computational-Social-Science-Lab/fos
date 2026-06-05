import React, { useState } from 'react';
import { useSimulationStore } from '@/store';
import { useAuthStore } from '@/store/auth';
import { listMetrics, computeMetricTrajectories, computeMetricAggregate, computeEventCountByAgent, hydrateAgentHistoryFromLogs } from '@/utils/resultsComputations';
import { generateMarkdownReport } from '@/utils/markdownReport';
import { AggregateTrajectoryChart } from './AggregateTrajectoryChart';
import { MetricTrajectoryChart } from './MetricTrajectoryChart';
import { CountBarChart } from './CountBarChart';
import { AiSummarySection } from './AiSummarySection';
import { ExportSection } from './ExportSection';

export type ResultsLabels = {
  noData: string; generate: string; generating: string; metric: string;
  exportCsv: string; exportReport: string; noActivity: string;
  reportSummary: string; reportNoSummary: string; reportFinalValues: string;
  reportAgent: string; reportFinalValue: string;
  perAgent: string; aggregate: string; mean: string; range: string;
};

type Props = { labels: ResultsLabels; language: 'en' | 'zh' };

function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ResultsView({ labels, language }: Props) {
  const agents = useSimulationStore((s: any) => s.agents);
  const logs = useSimulationStore((s: any) => s.logs);
  const currentSimulation = useSimulationStore((s: any) => s.currentSimulation);
  const engineConfig = useSimulationStore((s: any) => s.engineConfig);
  const resultsSummary = useSimulationStore((s: any) => s.resultsSummary);
  const isGeneratingResultsSummary = useSimulationStore((s: any) => s.isGeneratingResultsSummary);
  const resultsSummaryError = useSimulationStore((s: any) => s.resultsSummaryError);
  const generateResultsSummary = useSimulationStore((s: any) => s.generateResultsSummary);

  const [selectedMetric, setSelectedMetric] = useState<string>('');

  if (!currentSimulation || !Array.isArray(logs)) {
    return <div>{labels.noData}</div>;
  }

  const AGGREGATE_THRESHOLD = 12;
  const [viewMode, setViewMode] = useState<'per-agent' | 'aggregate'>(() =>
    agents.length > AGGREGATE_THRESHOLD ? 'aggregate' : 'per-agent'
  );

  const hydratedAgents = hydrateAgentHistoryFromLogs(logs, agents);
  const title: string = currentSimulation.name;
  const metrics = listMetrics(hydratedAgents);
  const activeMetric = metrics.includes(selectedMetric)
    ? selectedMetric
    : (metrics.length > 0 ? metrics[0] : '');
  const series = metrics.length > 0
    ? computeMetricTrajectories(hydratedAgents, activeMetric)
    : [];

  const onGenerate = () => { generateResultsSummary(title, language); };
  const onExportCsv = async () => {
    const token = (engineConfig as any).token ?? useAuthStore.getState().accessToken ?? undefined;
    const baseUrl = engineConfig.endpoint;

    const response = await fetch(
      `${baseUrl}/simulations/${currentSimulation.id}/export?format=csv`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`);
    }

    const contentDisp = response.headers.get('Content-Disposition');
    const filenameMatch = contentDisp?.match(/filename="(.+)"/);
    const filename = filenameMatch ? filenameMatch[1] : `${title}_export.csv`;

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };
  const onExportMarkdown = () => {
    const md = generateMarkdownReport(
      { title, metrics: metrics.map((m) => ({ name: m, series: computeMetricTrajectories(hydratedAgents, m) })), summary: resultsSummary },
      { summary: labels.reportSummary, noSummary: labels.reportNoSummary, finalValues: labels.reportFinalValues, agent: labels.reportAgent, finalValue: labels.reportFinalValue },
    );
    downloadFile(title + '_report.md', md, 'text/markdown');
  };

  const nameById = new Map((hydratedAgents as any[]).map((a) => [a.id, a.name]));
  const activityBars = computeEventCountByAgent(logs).map((c) => ({
    label: nameById.has(c.agentId) ? (nameById.get(c.agentId) as string) : c.agentId,
    value: c.count,
  }));

  return (
    <div className="h-full overflow-auto">
      <div className="p-6" style={{ maxWidth: '800px', margin: '0 auto' }}>

        {metrics.length > 0 && (
          <div className="rounded-lg border p-4 mb-4"
            style={{ background: 'var(--ss-workspace-surface)', borderColor: 'var(--ss-workspace-border)' }}>
            <div className="text-xs font-semibold uppercase mb-3"
              style={{ color: 'var(--ss-workspace-muted)', letterSpacing: '0.05em' }}>
              AI Analysis
            </div>
            <AiSummarySection
              summary={resultsSummary}
              isGenerating={isGeneratingResultsSummary}
              error={resultsSummaryError}
              onGenerate={onGenerate}
              labels={{ generate: labels.generate, generating: labels.generating }}
            />
          </div>
        )}

        <div className="rounded-lg border p-4 mb-4"
          style={{ background: 'var(--ss-workspace-surface)', borderColor: 'var(--ss-workspace-border)' }}>
          <div className="text-xs font-semibold uppercase mb-3"
            style={{ color: 'var(--ss-workspace-muted)', letterSpacing: '0.05em' }}>
            {metrics.length > 0 ? labels.metric : 'Activity'}
          </div>
          {metrics.length > 0 ? (
            <div>
              <select value={activeMetric} aria-label={labels.metric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="mb-3 text-sm rounded border px-2 py-1"
                style={{ background: 'var(--ss-workspace-surface)', color: 'var(--ss-workspace-text)', borderColor: 'var(--ss-workspace-border)' }}>
                {metrics.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>

              {metrics.length > 0 && (
                <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
                  {(['per-agent', 'aggregate'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setViewMode(mode)}
                      style={{
                        padding: '2px 8px', fontSize: '11px', borderRadius: '4px', cursor: 'pointer',
                        border: '1px solid var(--ss-workspace-border)',
                        background: viewMode === mode ? 'var(--ss-brand-soft)' : 'transparent',
                        color: viewMode === mode ? 'var(--ss-brand-primary)' : 'var(--ss-workspace-muted)',
                      }}
                    >
                      {mode === 'per-agent' ? labels.perAgent : labels.aggregate}
                    </button>
                  ))}
                </div>
              )}

              {metrics.length > 0 ? (
                viewMode === 'aggregate' && series.length > 0 ? (
                  <AggregateTrajectoryChart
                    points={computeMetricAggregate(series)}
                    metric={activeMetric}
                    meanLabel={labels.mean}
                    rangeLabel={labels.range}
                  />
                ) : (
                  <MetricTrajectoryChart series={series} metric={activeMetric} />
                )
              ) : activityBars.length > 0 ? (
                <CountBarChart bars={activityBars} />
              ) : (
                <div className="text-sm" style={{ color: 'var(--ss-workspace-muted)' }}>{labels.noActivity}</div>
              )}
            </div>
          ) : activityBars.length > 0 ? (
            <CountBarChart bars={activityBars} />
          ) : (
            <div className="text-sm" style={{ color: 'var(--ss-workspace-muted)' }}>{labels.noActivity}</div>
          )}
        </div>

        <div className="rounded-lg border p-4"
          style={{ background: 'var(--ss-workspace-surface)', borderColor: 'var(--ss-workspace-border)' }}>
          <div className="text-xs font-semibold uppercase mb-3"
            style={{ color: 'var(--ss-workspace-muted)', letterSpacing: '0.05em' }}>
            Export
          </div>
          <ExportSection
            onExportCsv={onExportCsv}
            onExportMarkdown={onExportMarkdown}
            labels={{ csv: labels.exportCsv, markdown: labels.exportReport }}
          />
        </div>

      </div>
    </div>
  );
}
