# Results View Node Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a branch node selector dropdown to ResultsView so users can switch which simtree branch they are analyzing without leaving the analysis view.

**Architecture:** Add a `<select>` dropdown inside ResultsView that reads `nodes` and `selectedNodeId` from the store, and calls the existing `selectNode(id)` store action on change. No store or backend changes needed.

**Tech Stack:** React, TypeScript, Zustand (existing store), Vitest + React Testing Library (existing test setup)

---

### Task 1: Add translation keys for the node selector

**Files:**
- Modify: `frontend/locales/en.json` (add keys inside the `"results"` section at line 3759)
- Modify: `frontend/locales/zh.json` (add keys inside the `"results"` section at line 3793)

- [ ] **Step 1: Add English translation keys**

In `frontend/locales/en.json`, inside the `"results"` object (after `"reportFinalValue"`), add two new keys:

```json
    "branch": "Branch",
    "selectBranch": "Select branch"
```

- [ ] **Step 2: Add Chinese translation keys**

In `frontend/locales/zh.json`, inside the `"results"` object (after `"reportFinalValue"`), add two new keys:

```json
    "branch": "分支",
    "selectBranch": "选择分支"
```

- [ ] **Step 3: Run i18n consistency check**

Run: `cd frontend && npm run test:i18n`
Expected: PASS

---

### Task 2: Write the failing test for node selector in ResultsView

**Files:**
- Modify: `frontend/components/__tests__/AnalyseTab.results.test.tsx`

- [ ] **Step 1: Add nodes and selectNode to the test store setup**

Update the `beforeEach` to include `nodes` and `selectNode` in the store state. The existing test sets agents and logs but does not set nodes. Add after the `toggleReportModal` line:

```typescript
const simNode = (id: string, display_id: string, name: string, parentId: string | null, depth: number) => ({
  id,
  display_id,
  name,
  parentId,
  depth,
  isLeaf: true,
  status: 'completed' as const,
  timestamp: '2026-05-21T10:00:00.000Z',
  worldTime: '2026-01-01T00:00:00.000Z',
});
```

Add to the `setState` call (after `toggleReportModal`):

```typescript
    nodes: [
      simNode('root', '0', 'Root', null, 0),
      simNode('n1', '0.1', 'Branch A', 'root', 1),
      simNode('n2', '0.2', 'Branch B', 'root', 1),
    ],
    selectedNodeId: 'root',
    selectNode: vi.fn(),
```

- [ ] **Step 2: Add test that the branch selector is rendered with all nodes**

Add a new test inside the existing `describe` block:

```typescript
  it('renders a branch selector dropdown with all nodes', () => {
    render(<AnalyseTab />);
    const select = screen.getByLabelText('results.branch');
    expect(select).toBeTruthy();
    const options = select.querySelectorAll('option');
    expect(options.length).toBe(3);
    expect(options[0].textContent).toContain('0');
    expect(options[0].textContent).toContain('Root');
    expect(options[1].textContent).toContain('0.1');
    expect(options[1].textContent).toContain('Branch A');
    expect(options[2].textContent).toContain('0.2');
    expect(options[2].textContent).toContain('Branch B');
  });
```

- [ ] **Step 3: Add test that changing the dropdown calls selectNode**

```typescript
  it('calls selectNode when the user picks a different branch', async () => {
    const { user } = renderWithUser(<AnalyseTab />);
    const select = screen.getByLabelText('results.branch');
    await user.selectOptions(select, 'n2');
    const state = useSimulationStore.getState();
    expect(state.selectNode).toHaveBeenCalledWith('n2');
  });
```

Note: this test uses `user-event` for the select interaction. Check if the test file already imports `userEvent` — if not, add this helper at the top:

```typescript
import userEvent from '@testing-library/user-event';

function renderWithUser(ui: React.ReactElement) {
  const result = render(ui);
  return { ...result, user: userEvent.setup() };
}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run components/__tests__/AnalyseTab.results.test.tsx`
Expected: FAIL — no branch selector rendered yet

---

### Task 3: Implement the node selector in ResultsView

**Files:**
- Modify: `frontend/components/results/ResultsView.tsx`

- [ ] **Step 1: Read nodes and selectNode from the store**

In `ResultsView`, add two more store reads after the existing `selectedNodeId` read (around line 45):

```typescript
  const nodes = useSimulationStore((s: any) => s.nodes);
  const selectNode = useSimulationStore((s: any) => s.selectNode);
```

Note: `nodes` is already read on line 44, so just add `selectNode` after the `selectedNodeId` line.

- [ ] **Step 2: Add sorted node list computation**

Add a `useMemo` after the existing state reads (after line 53, before the early return):

```typescript
  const sortedNodes = React.useMemo(
    () =>
      Array.isArray(nodes)
        ? [...nodes].sort((a: any, b: any) => a.depth - b.depth || a.display_id.localeCompare(b.display_id))
        : [],
    [nodes],
  );
```

- [ ] **Step 3: Add the branch selector UI**

Inside the JSX, add the branch selector inside the "AI Analysis" card, before the `<AiSummarySection>` component (around line 131, before `<AiSummarySection>`). The selector should only render when there are nodes to show:

```tsx
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
                    value={selectedNodeId || ''}
                    onChange={(e) => { selectNode(e.target.value); }}
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
                    {sortedNodes.map((node: any) => (
                      <option key={node.id} value={node.id}>
                        {node.display_id} — {node.name}{node.worldTime ? ` (${node.worldTime})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}
```

- [ ] **Step 4: Add the two new label fields to ResultsLabels type**

In the `ResultsLabels` type at the top of the file (around line 19-25), add:

```typescript
  branch: string; selectBranch: string;
```

- [ ] **Step 5: Pass the new labels from AnalyseTab**

In `AnalyseTab.tsx`, add the two new entries to the `labels` object (after `reportFinalValue`):

```typescript
    branch: t("results.branch"),
    selectBranch: t("results.selectBranch"),
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run components/__tests__/AnalyseTab.results.test.tsx`
Expected: PASS

---

### Task 4: Run the full test suite

- [ ] **Step 1: Run all frontend tests**

Run: `cd frontend && npm run test:run`
Expected: All tests pass

- [ ] **Step 2: Run linting**

Run: `cd frontend && npx eslint components/results/ResultsView.tsx components/AnalyseTab.tsx components/__tests__/AnalyseTab.results.test.tsx`
Expected: No errors
