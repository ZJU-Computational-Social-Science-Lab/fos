# Results Section Design

**Date**: 2026-06-02
**Status**: Approved
**Approach**: A — Frontend-computed metrics pipeline

## Goal

Replace the AnalyseTab's "overview" sub-view with a full Results view containing interactive charts, an AI-generated prose summary, and paper-ready exports. The AnalyseTab will have two sub-views: "Results" (new) and "Compare" (existing ComparisonView).

The results section must produce outputs (tables and narrative prose) that researchers can directly paste into academic papers, in both Chinese and English.

## Core Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data pipeline location | Frontend (Zustand store) | Logs, agents with history, and nodes are already in the store. No backend API changes needed. |
| Action Breakdown chart | Recharts BarChart | Already installed (confirmed in vite.config.ts). Horizontal stacked bars per agent. |
| Metric Trajectory chart | D3 (existing pattern) | Reuse AnalyticsPanel.tsx's D3 line chart pattern. One line per agent, metric selector dropdown. |
| Branch Comparison | D3 (same pattern) | Overlaid trajectories, solid vs dashed lines for baseline vs treatment. Only shown when branches exist. |
| AI Summary | Existing LLM endpoint | Sends computed metrics to backend, LLM generates publishable-quality prose in user's language. Reuses generateReport store flow pattern. |
| Export formats | CSV + Markdown | CSV for raw data. Markdown with tables + LLM prose for direct paper inclusion. Both i18n-aware. |
| Works for all scenes | Yes | Scored scenes use agent.history. Non-scored scenes use state variables or action counts. |

## File Structure

```
frontend/
├── components/
│   ├── AnalyseTab.tsx                    # Modified: replace "overview" with Results view
│   ├── results/
│   │   ├── ActionBreakdownChart.tsx      # Recharts horizontal stacked bar chart (~120 lines)
│   │   ├── MetricTrajectoryChart.tsx     # D3 line chart, metric selector (~180 lines)
│   │   ├── BranchComparisonChart.tsx     # D3 overlaid trajectories (~150 lines)
│   │   ├── AiSummarySection.tsx          # AI summary button + collapsible result (~100 lines)
│   │   └── ExportSection.tsx             # CSV + Markdown export buttons (~130 lines)
├── utils/
│   ├── resultsComputations.ts            # Metrics pipeline: action breakdown, trajectories, branches (~200 lines)
│   └── markdownReport.ts                 # Markdown report generator from computed metrics (~200 lines)
```

**No backend changes required.** The AI summary reuses the existing `generateReport` / LLM refinement flow already in the store.

## Section 2: Data Pipeline (`resultsComputations.ts`)

One module with three pure functions. All take data already in the Zustand store.

### `computeActionBreakdown(logs: LogEntry[]): ActionBreakdown`

Returns `Record<string, Record<string, number>>` — agent name to action name to count.

- Iterates all log entries, groups by `agentName` (or `agentId` mapped to name), counts each `action` value
- Works for all scene types since every event has an `agent` and `action` field
- Sorts agents alphabetically, actions by frequency (descending)

### `computeMetricTrajectories(agents: Agent[]): MetricTrajectories`

Returns `{ metrics: string[], data: Record<string, Array<{round: number, value: number}>> }` where the outer key is agent name.

- For scored scenes: reads `agent.history` (already populated — same data AnalyticsPanel uses). Keys are metric names (e.g. "score", "cooperation_rate").
- For non-scored scenes (GAWorld etc.): extracts state variables from agent properties that change over rounds (emotion, stress, econ_security, city_identity, etc.)
- Falls back to per-round action count if neither scores nor state vars exist
- Returns the list of available metric names plus the per-agent per-round data

### `computeBranchComparison(nodes: SimNode[], logs: LogEntry[]): BranchComparison | null`

Returns `{ baseline: MetricTrajectories, treatment: MetricTrajectories, branchLabel: string }` or `null`.

- Detects branches by checking if `nodes` contains a fork: two nodes at the same depth with different parent IDs
- If multiple forks exist, uses the first one
- Splits logs into two groups based on which branch node they belong to
- Computes metric trajectories for each group independently
- `branchLabel` comes from the branch node's metadata (e.g. intervention description)
- Returns `null` if no branches exist — BranchComparisonChart is not rendered

## Section 3: Charts

### ActionBreakdownChart (Recharts)

- `ResponsiveContainer` wrapping a horizontal `BarChart`
- One bar per agent on the Y-axis
- Each bar is stacked with segments for each action type
- Colors from Recharts `COLORS` palette
- Legend at bottom
- Tooltip shows agent name, action name, and count on hover
- If only one action type exists (e.g. all "cooperate"), renders a simple non-stacked bar

### MetricTrajectoryChart (D3)

- Reuses the exact D3 pattern from `AnalyticsPanel.tsx`: SVG with scales, axes, line generator, points, tooltip
- Dropdown at top to select which metric to display
- One line per agent, color-coded via `d3.schemeCategory10`
- X-axis: round numbers (R1, R2, R3...)
- Y-axis: metric values, auto-scaled with 10% padding
- Points at each data value, hover tooltip showing all agents' values at that round
- Grid lines at 10% opacity

### BranchComparisonChart (D3)

- Same D3 structure as MetricTrajectoryChart
- Metric selector dropdown (shared metric list from trajectories)
- Two groups of lines: baseline agents (solid) and treatment agents (dashed)
- Different color palettes for each group to avoid confusion (e.g. blues for baseline, oranges for treatment)
- Summary card below the chart:
  - "Baseline avg final score: X" vs "Treatment avg final score: Y"
  - "Delta: +Z (treatment higher/lower)"
- Only rendered when `computeBranchComparison()` returns non-null

## Section 4: AI Summary

### AiSummarySection component

- A "Generate AI Analysis" button at the top of the Results view
- On click: calls a store action that sends the computed metrics (action breakdown, final scores, trajectory trends, branch deltas) to the existing LLM backend endpoint
- The LLM prompt instructs it to:
  - Identify the most significant behavioral patterns
  - Note any unexpected outcomes or emergent phenomena
  - Compare agent strategies and outcomes
  - For branch comparisons: describe the intervention effect
  - Write in the user's current UI language (Chinese or English)
  - Use academic/professional tone suitable for paper inclusion
- Results render in a collapsible card below the button
- Loading state with spinner while the LLM generates
- Reuses the `generateReport` flow pattern from `store/experiments.ts`

### Store changes

- Add `resultsSummary: string | null` to the experiments store
- Add `isGeneratingResultsSummary: boolean` to the experiments store
- Add `generateResultsSummary(metrics: ComputedMetrics): Promise<void>` action
- The action calls the same LLM endpoint used by `generateReport`, with a different prompt template

## Section 5: Export Section

### ExportSection component

Two buttons below the charts area:

**CSV Export:**
- Downloads raw event log data in CSV format
- Reuses the existing CSV generation logic from `ExportModal.tsx` (Papa.unparse pattern)
- Columns: timestamp, round, agent, action, parameters, summary, nodeId, success
- Filename: `{simulation_name}_results_{date}.csv`

**Markdown Report Export:**
- Generates a structured Markdown document using `markdownReport.ts`
- Contents:
  1. Title: "Simulation Results: {simulation_name}"
  2. Per-round summary table: round number, each agent's action, score/metric value
  3. Final scores table: agent name, final score/metric, rank
  4. Action rate table: agent name, each action type, percentage
  5. Branch comparison table (if applicable): metric, baseline value, treatment value, delta
  6. AI-generated prose analysis (if generated; placeholder text if not)
- All headers and labels are i18n-aware (Chinese or English based on current UI language)
- Filename: `{simulation_name}_report_{date}.md`

### markdownReport.ts

- Pure function: `generateMarkdownReport(metrics: ComputedMetrics, summary: string | null, locale: string): string`
- Builds Markdown string with aligned tables, bold headers, and the LLM prose section
- No external dependencies — just string templates

## Section 6: AnalyseTab Changes

The AnalyseTab is modified:

- `type AnalyseView = "results" | "compare"` (replaces `"overview" | "compare"`)
- The sub-tab button changes from "Overview" to "Results" with a `BarChart3` icon
- The "results" view renders the new content (charts, AI summary, exports)
- The "compare" view remains unchanged (ComparisonView)
- Remove the old overview content (stats cards, metric pills, open-analytics/report buttons) — their functionality is now in the Results view directly

### Layout of the Results sub-view

```
┌─────────────────────────────────────────────────────┐
│ [Results tab] [Compare tab]                          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  [Generate AI Analysis] button           top-right   │
│                                                      │
│  ┌─ AI Summary Card (collapsible) ────────────────┐ │
│  │  LLM-generated prose analysis                   │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Action Breakdown ─────────────────────────────┐ │
│  │  Recharts horizontal stacked bar chart          │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Metric Trajectory ────────────────────────────┐ │
│  │  [Metric selector dropdown]                     │ │
│  │  D3 line chart                                  │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Branch Comparison (conditional) ──────────────┐ │
│  │  D3 overlaid chart + summary card               │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  [Export CSV]  [Export Markdown Report]              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

All charts are wrapped in white card containers with headers matching the existing AnalyseTab style (bordered rounded-lg sections with icon + title headers).

## Scope

This design covers only the Results sub-view within AnalyseTab. It does not:

- Change the ReportModal (it remains accessible from ContextToolbar and other entry points)
- Change the ExportModal (it remains for full data export; the Results export is focused on paper-ready outputs)
- Add new backend endpoints
- Modify the SimTree or branching system
- Add new i18n keys for new labels (these will be added as part of implementation)
