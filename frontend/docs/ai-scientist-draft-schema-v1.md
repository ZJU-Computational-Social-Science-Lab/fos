# AI Scientist Draft Schema v1

This schema is the frontend compatibility shape for AI Scientist analysis results.
It does not replace the existing `/llm/ai_scientist/analyze` API response yet.
Use `normalizeAiScientistDraft()` to map the current response into this structure.

## Compatibility rule

- Keep all existing response fields stable.
- Add new consumers against `AiScientistDraftV1`.
- Move page logic gradually; do not remove legacy fields until all consumers are migrated.

## Shape

```ts
type AiScientistDraftV1 = {
  version: 1;
  locale: string;
  source: {
    textExcerpt: string;
    fileName?: string | null;
    sections: AiScientistSourceSection[];
  };
  scenario: {
    description: string;
    recommendedScenarioId: string;
    recommendedReason: string;
    confidence: number;
    reviewRequired: boolean;
  };
  settings: AiScientistSetting[];
  actions: AiScientistAction[];
  agents: AiScientistAgent[];
  keyVariables: string[];
  recommendedParams: Record<string, unknown>;
  templateSuggestions: AiScientistTemplateSuggestion[];
  evidence: AiScientistEvidence[];
  evidenceByField: Record<string, string[]>;
  semanticSchema: AiScientistSemanticSchema;
  assumptions: string[];
  missingInformation: string[];
  warnings: string[];
  usedLlm: boolean;
  modelUsed?: string | null;
};
```
