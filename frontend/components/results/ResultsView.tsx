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
    <div>
      <AiSummarySection
        summary={resultsSummary}
        isGenerating={isGeneratingResultsSummary}
        error={resultsSummaryError}
        onGenerate={onGenerate}
        labels={{ generate: labels.generate, generating: labels.generating }}
      />
      {metrics.length > 0 ? (
        <div>
          <select value={activeMetric} aria-label={labels.metric} onChange={(e) => setSelectedMetric(e.target.value)}>
            {metrics.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <MetricTrajectoryChart series={computeMetricTrajectories(agents, activeMetric)} metric={activeMetric} />
        </div>
      ) : activityBars.length > 0 ? (
        <CountBarChart bars={activityBars} />
      ) : (
        <div>{labels.noActivity}</div>
      )}
      <ExportSection
        onExportCsv={onExportCsv}
        onExportMarkdown={onExportMarkdown}
        labels={{ csv: labels.exportCsv, markdown: labels.exportReport }}
      />
    </div>
  );
}
