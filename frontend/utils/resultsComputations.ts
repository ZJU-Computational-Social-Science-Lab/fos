/*
This file turns saved agent history into simple result data.
listMetrics looks through every agent and returns all metric names in sorted order.
computeMetricTrajectories builds one value series per agent for one chosen metric.
computeMetricAggregate combines many agent series into one mean line with min and max bounds.
computeEventCountByAgent counts how many saved events belong to each agent.
computeEventCountByRound counts how many saved events happened in each round.
*/

import type { Agent, LogEntry, SimNode } from '@/types';

export type Series = { agentId: string; agentName: string; values: number[] };
export type MetricAggregatePoint = { round: number; mean: number; min: number; max: number };
export type AgentCount = { agentId: string; count: number };
export type RoundCount = { round: number; count: number };
export type ResultsMetric = {
  name: string;
  series: Series[];
  aggregate: MetricAggregatePoint[];
  finalValues: { agentId: string; agentName: string; value: number }[];
};
export type ResultsBranchSnapshot = {
  selectedNodeId: string | null;
  selectedBranchLabel: string | null;
  selectedBranchPath: string[];
};
export type ResultsComparisonSnapshot = {
  baselineNodeId: string | null;
  interventionNodeId: string | null;
  baselineLabel: string | null;
  interventionLabel: string | null;
  baselineOnlyEventCount: number;
  interventionOnlyEventCount: number;
  agentDiffCount: number;
  agentDiffFieldCount: number;
  eventTypeCount: number;
  summary: string | null;
};
export type ResultsDataset = {
  title: string;
  branchLogs: LogEntry[];
  hydratedAgents: Agent[];
  metrics: ResultsMetric[];
  metricNames: string[];
  activityByAgent: AgentCount[];
  activityByRound: RoundCount[];
  branch: ResultsBranchSnapshot;
  comparison: ResultsComparisonSnapshot | null;
};
export type ResultsDatasetInput = {
  title: string;
  agents: Agent[];
  logs: LogEntry[];
  nodes: SimNode[];
  selectedNodeId?: string | null;
  comparison?: ResultsComparisonSnapshot | null;
};
export type ResultsSummaryInputSnapshot = {
  title: string;
  branch: ResultsBranchSnapshot;
  metrics: {
    name: string;
    series: Series[];
    aggregate: MetricAggregatePoint[];
    finalValues: { agentId: string; agentName: string; value: number }[];
  }[];
  activityByAgent: AgentCount[];
  activityByRound: RoundCount[];
  comparison: ResultsComparisonSnapshot | null;
};

export function filterLogsToSelectedBranch(
  logs: LogEntry[],
  nodes: SimNode[],
  selectedNodeId: string | null | undefined,
): LogEntry[] {
  if (!Array.isArray(logs)) {
    throw new Error('filterLogsToSelectedBranch: logs must be an array');
  }

  if (!selectedNodeId || !Array.isArray(nodes) || nodes.length === 0) {
    return logs;
  }

  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  if (!nodesById.has(selectedNodeId)) {
    return logs;
  }

  const branchIds = new Set<string>();
  let currentId: string | null | undefined = selectedNodeId;

  while (currentId) {
    const currentNode = nodesById.get(currentId);
    if (!currentNode || branchIds.has(currentNode.id)) {
      break;
    }
    branchIds.add(currentNode.id);
    currentId = currentNode.parentId;
  }

  return logs.filter(
    (log) => !log.nodeId || !nodesById.has(log.nodeId) || branchIds.has(log.nodeId),
  );
}

export function listMetrics(agents: Agent[]): string[] {
  if (!Array.isArray(agents)) {
    throw new Error('listMetrics: agents must be an array');
  }

  const metrics = new Set<string>();

  for (const agent of agents) {
    for (const metric of Object.keys(agent.history)) {
      metrics.add(metric);
    }
  }

  return Array.from(metrics).sort();
}

export function computeMetricTrajectories(agents: Agent[], metric: string): Series[] {
  if (typeof metric !== 'string' || metric.length === 0) {
    throw new Error('computeMetricTrajectories: metric must be a non-empty string');
  }

  const series = agents
    .filter((agent) => Object.prototype.hasOwnProperty.call(agent.history, metric))
    .map((agent) => ({
      agentId: agent.id,
      agentName: agent.name,
      values: agent.history[metric],
    }))
    .sort((left, right) => left.agentName.localeCompare(right.agentName));

  if (series.length === 0) {
    throw new Error(`computeMetricTrajectories: metric "${metric}" not found in any agent history`);
  }

  return series;
}

export function computeMetricAggregate(series: Series[]): MetricAggregatePoint[] {
  if (!Array.isArray(series) || series.length === 0) {
    throw new Error('computeMetricAggregate: series must be a non-empty array');
  }

  const maxLen = Math.max(...series.map((s) => s.values.length));
  if (maxLen === 0) {
    throw new Error('computeMetricAggregate: series have no values');
  }

  const points: MetricAggregatePoint[] = [];

  for (let i = 0; i < maxLen; i++) {
    const vals: number[] = [];

    for (const s of series) {
      if (i < s.values.length) {
        vals.push(s.values[i]);
      }
    }

    const sum = vals.reduce((acc, v) => acc + v, 0);
    points.push({
      round: i + 1,
      mean: sum / vals.length,
      min: Math.min(...vals),
      max: Math.max(...vals),
    });
  }

  return points;
}

export function computeEventCountByAgent(logs: LogEntry[]): AgentCount[] {
  if (!Array.isArray(logs)) {
    throw new Error('computeEventCountByAgent: logs must be an array');
  }

  const counts = new Map<string, number>();

  for (const log of logs) {
    if (typeof log.agentId === 'string' && log.agentId.length > 0) {
      const currentCount = counts.get(log.agentId);
      if (currentCount === undefined) {
        counts.set(log.agentId, 1);
        continue;
      }

      counts.set(log.agentId, currentCount + 1);
    }
  }

  return Array.from(counts.entries())
    .map(([agentId, count]) => ({ agentId, count }))
    .sort((left, right) => {
      if (left.count !== right.count) {
        return right.count - left.count;
      }

      return left.agentId.localeCompare(right.agentId);
    });
}

export function computeEventCountByRound(logs: LogEntry[]): RoundCount[] {
  if (!Array.isArray(logs)) {
    throw new Error('computeEventCountByRound: logs must be an array');
  }

  const counts = new Map<number, number>();

  for (const log of logs) {
    const currentCount = counts.get(log.round);
    if (currentCount === undefined) {
      counts.set(log.round, 1);
      continue;
    }

    counts.set(log.round, currentCount + 1);
  }

  return Array.from(counts.entries())
    .map(([round, count]) => ({ round, count }))
    .sort((left, right) => left.round - right.round);
}

export function hydrateAgentHistoryFromLogs(logs: LogEntry[], agents: Agent[]): Agent[] {
  if (!Array.isArray(logs)) {
    throw new Error('hydrateAgentHistoryFromLogs: logs must be an array');
  }

  if (!Array.isArray(agents)) {
    throw new Error('hydrateAgentHistoryFromLogs: agents must be an array');
  }

  const actionLogs = logs.filter(
    (log) =>
      log.type === 'AGENT_ACTION'
      && typeof log.agentId === 'string'
      && log.agentId.length > 0
      && log.outcome !== undefined
      && Object.keys(log.outcome).length > 0,
  );

  if (actionLogs.length === 0) {
    return agents;
  }

  const maxRound = Math.max(...actionLogs.map((log) => log.round));
  const store = new Map<string, Map<string, Map<number, number>>>();

  for (const log of actionLogs) {
    const agentId = log.agentId as string;

    if (!store.has(agentId)) {
      store.set(agentId, new Map());
    }

    const agentMetrics = store.get(agentId) as Map<string, Map<number, number>>;

    for (const [metric, value] of Object.entries(log.outcome as Record<string, number>)) {
      if (!agentMetrics.has(metric)) {
        agentMetrics.set(metric, new Map());
      }

      const roundsByMetric = agentMetrics.get(metric) as Map<number, number>;
      roundsByMetric.set(log.round, value);
    }
  }

  return agents.map((agent) => {
    const agentMetrics = store.get(agent.id);

    if (agentMetrics === undefined) {
      return agent;
    }

    const newHistory = { ...agent.history };

    agentMetrics.forEach((roundsByMetric, metric) => {
      if (newHistory[metric] !== undefined && newHistory[metric].length > 0) {
        return;
      }

      newHistory[metric] = Array.from({ length: maxRound }, (_, index) => {
        const value = roundsByMetric.get(index + 1);
        return typeof value === 'number' ? value : 0;
      });
    });

    return { ...agent, history: newHistory };
  });
}

export function buildResultsDataset(input: ResultsDatasetInput): ResultsDataset {
  if (typeof input.title !== 'string' || input.title.length === 0) {
    throw new Error('buildResultsDataset: title must be a non-empty string');
  }

  if (!Array.isArray(input.agents)) {
    throw new Error('buildResultsDataset: agents must be an array');
  }

  const nodes = Array.isArray(input.nodes) ? input.nodes : [];
  const branchLogs = filterLogsToSelectedBranch(input.logs, nodes, input.selectedNodeId);
  const hydratedAgents = hydrateAgentHistoryFromLogs(branchLogs, input.agents);
  const metricNames = listMetrics(hydratedAgents);
  const metrics = metricNames.flatMap((name) => {
    const series = computeMetricTrajectories(hydratedAgents, name)
      .filter((oneSeries) => oneSeries.values.length > 0);
    if (series.length === 0) {
      return [];
    }
    return {
      name,
      series,
      aggregate: computeMetricAggregate(series),
      finalValues: series.map((oneSeries) => ({
        agentId: oneSeries.agentId,
        agentName: oneSeries.agentName,
        value: oneSeries.values[oneSeries.values.length - 1],
      })),
    };
  });

  return {
    title: input.title,
    branchLogs,
    hydratedAgents,
    metrics,
    metricNames: metrics.map((metric) => metric.name),
    activityByAgent: computeEventCountByAgent(branchLogs),
    activityByRound: computeEventCountByRound(branchLogs),
    branch: buildBranchSnapshot(nodes, input.selectedNodeId),
    comparison: input.comparison ?? null,
  };
}

export function buildResultsSummaryInputSnapshot(dataset: ResultsDataset): ResultsSummaryInputSnapshot {
  return {
    title: dataset.title,
    branch: dataset.branch,
    metrics: dataset.metrics.map((metric) => ({
      name: metric.name,
      series: metric.series,
      aggregate: metric.aggregate,
      finalValues: metric.finalValues,
    })),
    activityByAgent: dataset.activityByAgent,
    activityByRound: dataset.activityByRound,
    comparison: dataset.comparison,
  };
}

export function buildResultsComparisonSnapshot(input: {
  nodes: SimNode[];
  baselineNodeId: string | null;
  interventionNodeId: string | null;
  compareData: any | null;
}): ResultsComparisonSnapshot | null {
  if (!input.baselineNodeId || !input.interventionNodeId) {
    return null;
  }

  const onlyInBaseline = Array.isArray(input.compareData?.only_in_a)
    ? input.compareData.only_in_a
    : [];
  const onlyInIntervention = Array.isArray(input.compareData?.only_in_b)
    ? input.compareData.only_in_b
    : [];
  const agentDiffs = input.compareData?.agent_diffs && typeof input.compareData.agent_diffs === 'object'
    ? input.compareData.agent_diffs as Record<string, Record<string, unknown>>
    : {};

  return {
    baselineNodeId: input.baselineNodeId,
    interventionNodeId: input.interventionNodeId,
    baselineLabel: getNodeLabel(input.nodes, input.baselineNodeId),
    interventionLabel: getNodeLabel(input.nodes, input.interventionNodeId),
    baselineOnlyEventCount: onlyInBaseline.length,
    interventionOnlyEventCount: onlyInIntervention.length,
    agentDiffCount: Object.keys(agentDiffs).length,
    agentDiffFieldCount: countAgentDiffFields(agentDiffs),
    eventTypeCount: countComparisonEventTypes([...onlyInBaseline, ...onlyInIntervention]),
    summary: typeof input.compareData?.summary === 'string' ? input.compareData.summary : null,
  };
}

function buildBranchSnapshot(nodes: SimNode[], selectedNodeId: string | null | undefined): ResultsBranchSnapshot {
  if (!selectedNodeId) {
    return {
      selectedNodeId: null,
      selectedBranchLabel: null,
      selectedBranchPath: [],
    };
  }

  const path = getBranchPath(nodes, selectedNodeId);
  return {
    selectedNodeId,
    selectedBranchLabel: getNodeLabel(nodes, selectedNodeId),
    selectedBranchPath: path.map((node) => getNodeLabel(nodes, node.id) ?? node.id),
  };
}

function getBranchPath(nodes: SimNode[], selectedNodeId: string): SimNode[] {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const path: SimNode[] = [];
  const seen = new Set<string>();
  let currentId: string | null | undefined = selectedNodeId;

  while (currentId && !seen.has(currentId)) {
    const node = nodesById.get(currentId);
    if (!node) {
      break;
    }
    seen.add(currentId);
    path.push(node);
    currentId = node.parentId;
  }

  return path.reverse();
}

function getNodeLabel(nodes: SimNode[], nodeId: string | null): string | null {
  if (!nodeId) {
    return null;
  }

  const node = nodes.find((item) => item.id === nodeId);
  if (!node) {
    return nodeId;
  }

  const displayId = node.display_id || node.id;
  return node.name ? `${displayId} - ${node.name}` : displayId;
}

function countAgentDiffFields(agentDiffs: Record<string, Record<string, unknown>>): number {
  return Object.values(agentDiffs).reduce(
    (total, diffs) => total + Object.keys(diffs || {}).length,
    0,
  );
}

function countComparisonEventTypes(events: any[]): number {
  const types = new Set<string>();
  for (const event of events) {
    const eventType = String(event?.type ?? event?.event_type ?? 'event');
    types.add(eventType);
  }
  return types.size;
}
