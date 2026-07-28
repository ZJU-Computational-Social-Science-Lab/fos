/**
 * This file shows the analysis page for a simulation.
 *
 * ResultsView lets people generate an AI summary, pick metrics, and inspect
 * charts for the currently selected branch.
 * downloadFile saves report text onto the user's computer.
 * getBranchDisplayId gets the best short label for a branch.
 * sortBranchNodes orders branches from root to deeper child branches.
 * formatBranchOption turns a branch into readable dropdown text.
 * getSelectedBranchValue keeps the dropdown valid while branch data loads.
 * reportBranchSelectionError logs a failed branch switch.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { useSimulationStore } from '@/store';
import { useAuthStore } from '@/store/auth';
import type { SimNode } from '@/types';
import {
  buildResultsComparisonSnapshot,
  buildResultsDataset,
  buildResultsSummaryInputSnapshot,
  computeMetricAggregate,
} from '@/utils/resultsComputations';
import { generateMarkdownReport } from '@/utils/markdownReport';
import * as experimentsApi from '@/services/experiments';
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
  branch: string; selectBranch: string;
  perAgent: string; aggregate: string; mean: string; range: string;
  baselineBranch?: string; interventionBranch?: string; branchComparison?: string;
  comparisonLoading?: string; comparisonUnavailable?: string;
  comparisonUniqueEvents?: string; comparisonAgentDiffs?: string; comparisonEventTypes?: string;
  reproducibility?: string; generatedAt?: string; model?: string; selectedBranch?: string;
  inputSnapshot?: string; activity?: string; count?: string; round?: string;
  baseline?: string; intervention?: string; uniqueEvents?: string; agentDiffFields?: string;
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

function getBranchDisplayId(node: SimNode): string {
  return node.display_id || node.id;
}

function sortBranchNodes(nodes: SimNode[]): SimNode[] {
  return [...nodes].sort(
    (left, right) =>
      left.depth - right.depth || getBranchDisplayId(left).localeCompare(getBranchDisplayId(right)),
  );
}

function formatBranchOption(node: SimNode): string {
  const baseLabel = `${getBranchDisplayId(node)} - ${node.name || node.id}`;
  if (!node.worldTime) {
    return baseLabel;
  }

  return `${baseLabel} (${node.worldTime})`;
}

function getSelectedBranchValue(nodes: SimNode[], selectedNodeId: string | null): string {
  if (!selectedNodeId) {
    return '';
  }

  return nodes.some((node) => node.id === selectedNodeId) ? selectedNodeId : '';
}

function inferBaselineNodeId(nodes: SimNode[], selectedNodeId: string | null): string {
  const selectedNode = selectedNodeId
    ? nodes.find((node) => node.id === selectedNodeId)
    : null;
  if (selectedNode?.parentId && nodes.some((node) => node.id === selectedNode.parentId)) {
    return selectedNode.parentId;
  }

  const rootNode = nodes.find((node) => node.parentId === null) ?? nodes[0];
  return rootNode?.id ?? '';
}

function reportBranchSelectionError(error: unknown): void {
  console.error('Failed to select simulation branch', error);
}

export function ResultsView({ labels, language }: Props) {
  const agents = useSimulationStore((state) => state.agents);
  const logs = useSimulationStore((state) => state.logs);
  const nodes = useSimulationStore((state) => state.nodes);
  const selectedNodeId = useSimulationStore((state) => state.selectedNodeId);
  const selectNode = useSimulationStore((state) => state.selectNode);
  const currentSimulation = useSimulationStore((state) => state.currentSimulation);
  const engineConfig = useSimulationStore((state) => state.engineConfig);
  const resultsSummary = useSimulationStore((state) => state.resultsSummary);
  const resultsSummaryMeta = useSimulationStore((state) => state.resultsSummaryMeta);
  const isGeneratingResultsSummary = useSimulationStore((state) => state.isGeneratingResultsSummary);
  const resultsSummaryError = useSimulationStore((state) => state.resultsSummaryError);
  const generateResultsSummary = useSimulationStore((state) => state.generateResultsSummary);

  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [baselineBranchId, setBaselineBranchId] = useState<string>('');
  const [interventionBranchId, setInterventionBranchId] = useState<string>('');
  const [compareData, setCompareData] = useState<any | null>(null);
  const [isLoadingComparison, setIsLoadingComparison] = useState(false);
  const AGGREGATE_THRESHOLD = 12;
  const [viewMode, setViewMode] = useState<'per-agent' | 'aggregate'>(() =>
    agents.length > AGGREGATE_THRESHOLD ? 'aggregate' : 'per-agent'
  );
  const sortedNodes = React.useMemo(() => sortBranchNodes(nodes), [nodes]);
  const selectedBranchValue = getSelectedBranchValue(sortedNodes, selectedNodeId);
  const defaultBaselineId = useMemo(
    () => inferBaselineNodeId(sortedNodes, selectedNodeId),
    [sortedNodes, selectedNodeId],
  );
  const effectiveBaselineBranchId = baselineBranchId || defaultBaselineId || '';
  const effectiveInterventionBranchId = interventionBranchId || selectedBranchValue || '';

  useEffect(() => {
    setBaselineBranchId('');
    setInterventionBranchId('');
  }, [selectedNodeId]);

  useEffect(() => {
    let mounted = true;

    if (
      !currentSimulation?.id
      || !effectiveBaselineBranchId
      || !effectiveInterventionBranchId
      || effectiveBaselineBranchId === effectiveInterventionBranchId
    ) {
      setCompareData(null);
      setIsLoadingComparison(false);
      return () => {
        mounted = false;
      };
    }

    const baseline = Number(effectiveBaselineBranchId);
    const intervention = Number(effectiveInterventionBranchId);
    if (!Number.isFinite(baseline) || !Number.isFinite(intervention)) {
      setCompareData(null);
      setIsLoadingComparison(false);
      return () => {
        mounted = false;
      };
    }

    setIsLoadingComparison(true);
    experimentsApi.compareNodes(
      currentSimulation.id,
      baseline,
      intervention,
      false,
      language,
    ).then((data) => {
      if (mounted) {
        setCompareData(data || null);
        setIsLoadingComparison(false);
      }
    }).catch((error) => {
      console.error('Results branch comparison failed', error);
      if (mounted) {
        setCompareData(null);
        setIsLoadingComparison(false);
      }
    });

    return () => {
      mounted = false;
    };
  }, [currentSimulation?.id, effectiveBaselineBranchId, effectiveInterventionBranchId, language]);

  if (!currentSimulation || !Array.isArray(logs)) {
    return <div>{labels.noData}</div>;
  }

  const title: string = currentSimulation.name;
  const comparisonSnapshot = buildResultsComparisonSnapshot({
    nodes,
    baselineNodeId: effectiveBaselineBranchId || null,
    interventionNodeId: effectiveInterventionBranchId || null,
    compareData,
  });
  const dataset = buildResultsDataset({
    title,
    agents,
    logs,
    nodes,
    selectedNodeId,
    comparison: comparisonSnapshot,
  });
  const hydratedAgents = dataset.hydratedAgents;
  const metrics = dataset.metricNames;
  const activeMetric = metrics.includes(selectedMetric)
    ? selectedMetric
    : (metrics.length > 0 ? metrics[0] : '');
  const activeMetricResult = dataset.metrics.find((metric) => metric.name === activeMetric) ?? null;
  const series = activeMetricResult?.series ?? [];

  const onGenerate = () => {
    generateResultsSummary(title, language, buildResultsSummaryInputSnapshot(dataset));
  };
  const onExportCsv = async () => {
    const token = engineConfig.token ?? useAuthStore.getState().accessToken ?? undefined;
    const baseUrl = engineConfig.endpoint;

    const response = await fetch(
      `${baseUrl}/simulations/${currentSimulation.id}/export?format=csv&results=true${selectedNodeId && Number.isFinite(Number(selectedNodeId)) ? `&node_id=${encodeURIComponent(selectedNodeId)}` : ''}`,
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
  const onBranchChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    if (!event.target.value) {
      return;
    }

    void Promise.resolve(selectNode(event.target.value)).catch(reportBranchSelectionError);
  };
  const onExportMarkdown = () => {
    const md = generateMarkdownReport(
      {
        title,
        metrics: dataset.metrics.map((metric) => ({ name: metric.name, series: metric.series })),
        summary: resultsSummary,
        activityByAgent: dataset.activityByAgent,
        activityByRound: dataset.activityByRound,
        branch: dataset.branch,
        comparison: dataset.comparison,
        summaryMeta: resultsSummaryMeta,
      },
      {
        summary: labels.reportSummary,
        noSummary: labels.reportNoSummary,
        finalValues: labels.reportFinalValues,
        agent: labels.reportAgent,
        finalValue: labels.reportFinalValue,
        reproducibility: labels.reproducibility,
        generatedAt: labels.generatedAt,
        model: labels.model,
        selectedBranch: labels.selectedBranch,
        inputSnapshot: labels.inputSnapshot,
        activity: labels.activity,
        count: labels.count,
        round: labels.round,
        branchComparison: labels.branchComparison,
        baseline: labels.baseline,
        intervention: labels.intervention,
        uniqueEvents: labels.uniqueEvents,
        agentDiffFields: labels.agentDiffFields,
      },
    );
    downloadFile(title + '_report.md', md, 'text/markdown');
  };

  const nameById = new Map(hydratedAgents.map((agent) => [agent.id, agent.name]));
  const activityBars = dataset.activityByAgent.map((c) => ({
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
            {sortedNodes.length > 0 && (
              <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <label
                  htmlFor="results-branch-select"
                  style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ss-workspace-muted)', whiteSpace: 'nowrap' }}
                >
                  {labels.branch}
                </label>
                <select
                  id="results-branch-select"
                  aria-label={labels.branch}
                  value={selectedBranchValue}
                  onChange={onBranchChange}
                  style={{
                    fontSize: '13px',
                    borderRadius: '4px',
                    border: '1px solid var(--ss-workspace-border)',
                    background: 'var(--ss-workspace-surface)',
                    color: 'var(--ss-workspace-text)',
                    padding: '2px 6px',
                    flex: 1,
                    maxWidth: '320px',
                  }}
                >
                  {selectedBranchValue === '' && (
                    <option value="">{labels.selectBranch}</option>
                  )}
                  {sortedNodes.map((node) => (
                    <option key={node.id} value={node.id}>
                      {formatBranchOption(node)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {sortedNodes.length > 1 && (
              <div
                style={{
                  marginBottom: '12px',
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
                  gap: '8px',
                }}
              >
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', fontWeight: 600, color: 'var(--ss-workspace-muted)' }}>
                  {labels.baselineBranch ?? 'Baseline branch'}
                  <select
                    aria-label={labels.baselineBranch ?? 'Baseline branch'}
                    value={effectiveBaselineBranchId}
                    onChange={(event) => setBaselineBranchId(event.target.value)}
                    style={{
                      fontSize: '13px',
                      borderRadius: '4px',
                      border: '1px solid var(--ss-workspace-border)',
                      background: 'var(--ss-workspace-surface)',
                      color: 'var(--ss-workspace-text)',
                      padding: '4px 6px',
                    }}
                  >
                    {sortedNodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {formatBranchOption(node)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', fontWeight: 600, color: 'var(--ss-workspace-muted)' }}>
                  {labels.interventionBranch ?? 'Intervention branch'}
                  <select
                    aria-label={labels.interventionBranch ?? 'Intervention branch'}
                    value={effectiveInterventionBranchId}
                    onChange={(event) => setInterventionBranchId(event.target.value)}
                    style={{
                      fontSize: '13px',
                      borderRadius: '4px',
                      border: '1px solid var(--ss-workspace-border)',
                      background: 'var(--ss-workspace-surface)',
                      color: 'var(--ss-workspace-text)',
                      padding: '4px 6px',
                    }}
                  >
                    {sortedNodes.map((node) => (
                      <option key={node.id} value={node.id}>
                        {formatBranchOption(node)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            {sortedNodes.length > 1 && (
              <div
                className="mb-3 rounded border p-3 text-xs"
                style={{
                  borderColor: 'var(--ss-workspace-border)',
                  background: 'var(--ss-workspace-surface-strong)',
                  color: 'var(--ss-workspace-text)',
                }}
              >
                <div className="font-semibold mb-2" style={{ color: 'var(--ss-workspace-heading)' }}>
                  {labels.branchComparison ?? 'Branch comparison'}
                </div>
                {isLoadingComparison ? (
                  <div style={{ color: 'var(--ss-workspace-muted)' }}>
                    {labels.comparisonLoading ?? 'Loading comparison...'}
                  </div>
                ) : comparisonSnapshot ? (
                  <div style={{ display: 'grid', gap: '4px' }}>
                    <div>
                      {(labels.comparisonUniqueEvents ?? 'Unique events')}: {comparisonSnapshot.baselineOnlyEventCount} / {comparisonSnapshot.interventionOnlyEventCount}
                    </div>
                    <div>
                      {(labels.comparisonAgentDiffs ?? 'Agent diff fields')}: {comparisonSnapshot.agentDiffFieldCount}
                    </div>
                    <div>
                      {(labels.comparisonEventTypes ?? 'Event types')}: {comparisonSnapshot.eventTypeCount}
                    </div>
                    {comparisonSnapshot.summary ? (
                      <div style={{ color: 'var(--ss-workspace-muted)' }}>
                        {comparisonSnapshot.summary}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div style={{ color: 'var(--ss-workspace-muted)' }}>
                    {labels.comparisonUnavailable ?? 'Select two backend branches to compare.'}
                  </div>
                )}
              </div>
            )}
            <AiSummarySection
              summary={resultsSummary}
              meta={resultsSummaryMeta}
              isGenerating={isGeneratingResultsSummary}
              error={resultsSummaryError}
              onGenerate={onGenerate}
              labels={{
                generate: labels.generate,
                generating: labels.generating,
                generatedAt: labels.generatedAt,
                model: labels.model,
                selectedBranch: labels.selectedBranch,
              }}
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
                    points={activeMetricResult?.aggregate ?? computeMetricAggregate(series)}
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
