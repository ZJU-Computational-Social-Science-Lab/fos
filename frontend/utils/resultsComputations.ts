/*
This file turns saved agent history into simple result data.
listMetrics looks through every agent and returns all metric names in sorted order.
computeMetricTrajectories builds one value series per agent for one chosen metric.
computeEventCountByAgent counts how many saved events belong to each agent.
computeEventCountByRound counts how many saved events happened in each round.
*/

import type { Agent, LogEntry } from '@/types';

export type Series = { agentId: string; agentName: string; values: number[] };
export type AgentCount = { agentId: string; count: number };
export type RoundCount = { round: number; count: number };

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
