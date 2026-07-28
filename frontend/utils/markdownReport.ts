/*
This file builds a markdown report from result data that was already computed.
generateMarkdownReport checks the input, writes the title and summary, and adds one final-values table for each metric.
buildMetricSection makes the markdown block for one metric.
buildTableRows makes the table rows for one metric and stops if an agent has no values.
getLastValue picks the final number from one agent's value list and stops if the list is empty.
*/

import type { Series } from './resultsComputations';
import type {
  AgentCount,
  ResultsBranchSnapshot,
  ResultsComparisonSnapshot,
  RoundCount,
} from './resultsComputations';

export type ReportLabels = {
  summary: string;
  noSummary: string;
  finalValues: string;
  agent: string;
  finalValue: string;
  reproducibility?: string;
  generatedAt?: string;
  model?: string;
  selectedBranch?: string;
  inputSnapshot?: string;
  activity?: string;
  count?: string;
  round?: string;
  branchComparison?: string;
  baseline?: string;
  intervention?: string;
  uniqueEvents?: string;
  agentDiffFields?: string;
};

export type ReportInput = {
  title: string;
  metrics: { name: string; series: Series[] }[];
  summary: string | null;
  activityByAgent?: AgentCount[];
  activityByRound?: RoundCount[];
  branch?: ResultsBranchSnapshot | null;
  comparison?: ResultsComparisonSnapshot | null;
  summaryMeta?: {
    generatedAt: string;
    providerId: number;
    model: string;
    selectedBranchId: string | null;
    prompt: string;
    inputSnapshot: unknown;
  } | null;
};

export function generateMarkdownReport(input: ReportInput, labels: ReportLabels): string {
  if (typeof input.title !== 'string' || input.title.length === 0) {
    throw new Error('generateMarkdownReport: title must be a non-empty string');
  }

  if (!Array.isArray(input.metrics)) {
    throw new Error('generateMarkdownReport: metrics must be an array');
  }

  const sections = [
    `# ${input.title}`,
    `## ${labels.summary}`,
    input.summary === null ? labels.noSummary : input.summary,
  ];

  if (input.metrics.length === 0) {
    appendActivitySection(sections, input, labels);
    appendComparisonSection(sections, input, labels);
    appendReproducibilitySections(sections, input, labels);
    return sections.join('\n\n');
  }

  sections.push(`## ${labels.finalValues}`);

  for (const metric of input.metrics) {
    sections.push(buildMetricSection(metric.name, metric.series, labels));
  }

  appendActivitySection(sections, input, labels);
  appendComparisonSection(sections, input, labels);
  appendReproducibilitySections(sections, input, labels);

  return sections.join('\n\n');
}

function buildMetricSection(metricName: string, seriesList: Series[], labels: ReportLabels): string {
  const tableLines = [
    `| ${labels.agent} | ${labels.finalValue} |`,
    '| --- | --- |',
    ...buildTableRows(metricName, seriesList),
  ];

  return `### ${metricName}\n\n${tableLines.join('\n')}`;
}

function buildTableRows(metricName: string, seriesList: Series[]): string[] {
  const rows: string[] = [];

  for (const series of seriesList) {
    const lastValue = getLastValue(metricName, series);
    rows.push(`| ${series.agentName} | ${String(lastValue)} |`);
  }

  return rows;
}

function getLastValue(metricName: string, series: Series): number {
  if (series.values.length === 0) {
    throw new Error(
      `generateMarkdownReport: series for agent "${series.agentName}" in metric "${metricName}" has no values`,
    );
  }

  return series.values[series.values.length - 1];
}

function appendActivitySection(sections: string[], input: ReportInput, labels: ReportLabels): void {
  const activityByAgent = input.activityByAgent ?? [];
  const activityByRound = input.activityByRound ?? [];
  if (activityByAgent.length === 0 && activityByRound.length === 0) {
    return;
  }

  const countLabel = labels.count ?? 'Count';
  const blocks = [`## ${labels.activity ?? 'Activity'}`];

  if (activityByAgent.length > 0) {
    blocks.push([
      `| ${labels.agent} | ${countLabel} |`,
      '| --- | --- |',
      ...activityByAgent.map((item) => `| ${item.agentId} | ${item.count} |`),
    ].join('\n'));
  }

  if (activityByRound.length > 0) {
    blocks.push([
      `| ${labels.round ?? 'Round'} | ${countLabel} |`,
      '| --- | --- |',
      ...activityByRound.map((item) => `| ${item.round} | ${item.count} |`),
    ].join('\n'));
  }

  sections.push(blocks.join('\n\n'));
}

function appendComparisonSection(sections: string[], input: ReportInput, labels: ReportLabels): void {
  if (!input.comparison) {
    return;
  }

  const comparison = input.comparison;
  sections.push([
    `## ${labels.branchComparison ?? 'Branch comparison'}`,
    `- ${labels.baseline ?? 'Baseline'}: ${comparison.baselineLabel ?? comparison.baselineNodeId ?? ''}`,
    `- ${labels.intervention ?? 'Intervention'}: ${comparison.interventionLabel ?? comparison.interventionNodeId ?? ''}`,
    `- ${labels.uniqueEvents ?? 'Unique events'}: ${comparison.baselineOnlyEventCount} / ${comparison.interventionOnlyEventCount}`,
    `- ${labels.agentDiffFields ?? 'Agent diff fields'}: ${comparison.agentDiffFieldCount}`,
    comparison.summary ? `- ${labels.summary}: ${comparison.summary}` : '',
  ].filter(Boolean).join('\n'));
}

function appendReproducibilitySections(sections: string[], input: ReportInput, labels: ReportLabels): void {
  const meta = input.summaryMeta;
  if (!meta && !input.branch) {
    return;
  }

  const lines = [`## ${labels.reproducibility ?? 'Reproducibility'}`];
  if (meta) {
    lines.push(`- ${labels.generatedAt ?? 'Generated at'}: ${meta.generatedAt}`);
    lines.push(`- ${labels.model ?? 'Model'}: ${meta.model}`);
  }

  const selectedBranch = input.branch?.selectedBranchLabel
    ?? meta?.selectedBranchId
    ?? input.branch?.selectedNodeId
    ?? null;
  if (selectedBranch) {
    lines.push(`- ${labels.selectedBranch ?? 'Selected branch'}: ${selectedBranch}`);
  }

  if (meta) {
    lines.push('');
    lines.push(`### ${labels.inputSnapshot ?? 'Input snapshot'}`);
    lines.push('```json');
    lines.push(JSON.stringify(meta.inputSnapshot, null, 2));
    lines.push('```');
  }

  sections.push(lines.join('\n'));
}
