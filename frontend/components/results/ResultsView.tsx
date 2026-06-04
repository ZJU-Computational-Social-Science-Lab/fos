import React, { useState } from 'react';
import { useSimulationStore } from '@/store';
import { listMetrics, computeMetricTrajectories, computeEventCountByAgent } from '@/utils/resultsComputations';
import { generateMarkdownReport } from '@/utils/markdownReport';
import { logsToCsv } from '@/utils/logsToCsv';
import { MetricTrajectoryChart } from './MetricTrajectoryChart';
import { CountBarChart } from './CountBarChart';
import { AiSummarySection } from './AiSummarySection';
import { ExportSection } from './ExportSection';

export type ResultsLabels = {
  noData: string; generate: string; generating: string; metric: string;
  exportCsv: string; exportReport: string; noActivity: string;
  reportSummary: string; reportNoSummary: string; reportFinalValues: string;
  reportAgent: string; reportFinalValue: string;
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
  const resultsSummary = useSimulationStore((s: any) => s.resultsSummary);
  const isGeneratingResultsSummary = useSimulationStore((s: any) => s.isGeneratingResultsSummary);
  const resultsSummaryError = useSimulationStore((s: any) => s.resultsSummaryError);
  const generateResultsSummary = useSimulationStore((s: any) => s.generateResultsSummary);

  const [selectedMetric, setSelectedMetric] = useState<string>('');

  if (!currentSimulation || !Array.isArray(logs) || logs.length === 0) {
    return <div>{labels.noData}</div>;
  }

  const title: string = currentSimulation.name;
  const metrics = listMetrics(agents);
  const activeMetric = metrics.includes(selectedMetric)
    ? selectedMetric
    : (metrics.length > 0 ? metrics[0] : '');

  const onGenerate = () => { generateResultsSummary(title, language); };
  const onExportCsv = () => { downloadFile(title + '_results.csv', logsToCsv(logs), 'text/csv'); };
  const onExportMarkdown = () => {
    const md = generateMarkdownReport(
      { title, metrics: metrics.map((m) => ({ name: m, series: computeMetricTrajectories(agents, m) })), summary: resultsSummary },
      { summary: labels.reportSummary, noSummary: labels.reportNoSummary, finalValues: labels.reportFinalValues, agent: labels.reportAgent, finalValue: labels.reportFinalValue },
    );
    downloadFile(title + '_report.md', md, 'text/markdown');
  };

  const nameById = new Map((agents as any[]).map((a) => [a.id, a.name]));
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
              <MetricTrajectoryChart series={computeMetricTrajectories(agents, activeMetric)} metric={activeMetric} />
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
