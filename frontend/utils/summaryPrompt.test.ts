import { describe, it, expect } from 'vitest';
import { buildSummaryPrompt } from './summaryPrompt';
import type { SummaryPromptInput } from './summaryPrompt';

const base: SummaryPromptInput = {
  title: 'Public goods game',
  language: 'en',
  metrics: [
    { name: 'score', series: [
      { agentId: 'a', agentName: 'Alice', values: [10, 12, 15] },
      { agentId: 'b', agentName: 'Bob', values: [8, 9, 9] },
    ] },
  ],
};

describe('buildSummaryPrompt', () => {
  it('includes the title, the English instruction, and each agent\'s real values with final', () => {
    const p = buildSummaryPrompt(base);
    expect(p).toContain('Public goods game');
    expect(p).toContain('English');
    expect(p).toContain('score:');
    expect(p).toContain('- Alice: 10, 12, 15 (final: 15)');
    expect(p).toContain('- Bob: 8, 9, 9 (final: 9)');
  });

  it('switches the instruction language to Chinese when language is zh', () => {
    const p = buildSummaryPrompt({ ...base, language: 'zh' });
    expect(p).toContain('中文');
    expect(p).toContain('- Alice: 10, 12, 15 (final: 15)');
  });

  it('throws when metrics is empty', () => {
    expect(() => buildSummaryPrompt({ ...base, metrics: [] })).toThrow();
  });

  it('throws when a series has no values', () => {
    expect(() => buildSummaryPrompt({
      ...base,
      metrics: [{ name: 'score', series: [{ agentId: 'a', agentName: 'Alice', values: [] }] }],
    })).toThrow();
  });

  it('throws when title is empty', () => {
    expect(() => buildSummaryPrompt({ ...base, title: '' })).toThrow();
  });
});
