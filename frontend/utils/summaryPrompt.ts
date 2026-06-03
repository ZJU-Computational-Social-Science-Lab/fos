/*
This file builds the text prompt that describes simulation results for an AI summary.
buildSummaryPrompt checks the input and turns each metric and agent value list into plain text.
*/

import type { Series } from './resultsComputations';

export type SummaryPromptInput = {
  title: string;
  language: 'en' | 'zh';
  metrics: { name: string; series: Series[] }[];
};

const ENGLISH_INSTRUCTION =
  'You are a research analyst. Write a concise, publication-quality analysis in English of the following multi-agent simulation results. Identify the most significant behavioral patterns and any notable or unexpected outcomes. Use an academic tone suitable for a paper.';

const CHINESE_INSTRUCTION =
  '你是一名研究分析员。请用中文对以下多智能体模拟结果撰写一段简洁、可用于论文发表的分析。指出最显著的行为模式以及任何值得注意或意外的结果。使用适合论文的学术语气。';

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
  const dataBlock = input.metrics
    .map((metric) => {
      const seriesLines = metric.series.map((series) => {
        if (series.values.length === 0) {
          throw new Error(
            `buildSummaryPrompt: series for agent "${series.agentName}" in metric "${metric.name}" has no values`,
          );
        }

        const lastValue = series.values[series.values.length - 1];
        return `- ${series.agentName}: ${series.values.join(', ')} (final: ${lastValue})`;
      });

      return [`${metric.name}:`, ...seriesLines].join('\n');
    })
    .join('\n');

  return `${instruction}\n\nSimulation: ${input.title}\n\nData:\n${dataBlock}`;
}
