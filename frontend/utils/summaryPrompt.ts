/*
This file builds the text prompt that describes simulation results for an AI summary.
buildSummaryPrompt checks the input and turns each metric into plain text.
buildMetricBlock chooses between agent lines and aggregate lines for one metric.
buildPerAgentLines writes one line per agent with all values and the final value.
buildAggregateLines writes one line per round with mean, min, and max values.
validateSeriesHaveValues makes sure every series has at least one value.
formatAggregatePoint turns one aggregate round into a plain text line.
*/

import { computeMetricAggregate } from './resultsComputations';
import type { MetricAggregatePoint, Series } from './resultsComputations';

export type SummaryPromptInput = {
  title: string;
  language: 'en' | 'zh';
  metrics: { name: string; series: Series[] }[];
};

const ENGLISH_INSTRUCTION =
  'You are a research analyst. Write a concise, publication-quality analysis in English of the following multi-agent simulation results. Identify the most significant behavioral patterns and any notable or unexpected outcomes. Use an academic tone suitable for a paper. Return only the analysis text as plain prose. Do not wrap the response in JSON, a markdown code block, or any other format.';

const CHINESE_INSTRUCTION =
  '你是一名研究分析员。请用中文对以下多智能体模拟结果撰写一段简洁、可用于论文发表的分析。指出最显著的行为模式以及任何值得注意或意外的结果。使用适合论文的学术语气。请仅返回纯文本分析内容，不要将回复包裹在 JSON、Markdown 代码块或任何其他格式中。';

const AGGREGATE_THRESHOLD = 12;

export function buildSummaryPrompt(input: SummaryPromptInput): string {
  if (typeof input.title !== 'string' || input.title.length === 0) {
    throw new Error('buildSummaryPrompt: title must be a non-empty string');
  }

  if (input.language !== 'en' && input.language !== 'zh') {
    throw new Error('buildSummaryPrompt: language must be "en" or "zh"');
  }

  if (!Array.isArray(input.metrics) || input.metrics.length === 0) {
    throw new Error('buildSummaryPrompt: metrics must be a non-empty array');
  }

  const instruction = input.language === 'en' ? ENGLISH_INSTRUCTION : CHINESE_INSTRUCTION;
  const dataBlock = input.metrics.map((metric) => buildMetricBlock(metric.name, metric.series)).join('\n');

  return `${instruction}\n\nSimulation: ${input.title}\n\nData:\n${dataBlock}`;
}

function buildMetricBlock(metricName: string, series: Series[]): string {
  if (series.length > AGGREGATE_THRESHOLD) {
    return [`${metricName}:`, ...buildAggregateLines(metricName, series)].join('\n');
  }

  return [`${metricName}:`, ...buildPerAgentLines(metricName, series)].join('\n');
}

function buildPerAgentLines(metricName: string, series: Series[]): string[] {
  validateSeriesHaveValues(metricName, series);

  return series.map((oneSeries) => {
    const lastValue = oneSeries.values[oneSeries.values.length - 1];
    return `- ${oneSeries.agentName}: ${oneSeries.values.join(', ')} (final: ${lastValue})`;
  });
}

function buildAggregateLines(metricName: string, series: Series[]): string[] {
  validateSeriesHaveValues(metricName, series);

  const aggregate = computeMetricAggregate(series);
  const heading = `- Aggregate statistics across ${series.length} agents:`;

  return [heading, ...aggregate.map(formatAggregatePoint)];
}

function validateSeriesHaveValues(metricName: string, series: Series[]): void {
  for (const oneSeries of series) {
    if (oneSeries.values.length === 0) {
      throw new Error(
        `buildSummaryPrompt: series for agent "${oneSeries.agentName}" in metric "${metricName}" has no values`,
      );
    }
  }
}

function formatAggregatePoint(point: MetricAggregatePoint): string {
  return `- Round ${point.round}: mean ${point.mean}, min ${point.min}, max ${point.max}`;
}
