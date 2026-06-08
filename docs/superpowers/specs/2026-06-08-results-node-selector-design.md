# Results View Node Selector

## Problem

The AnalyseTab's ResultsView shows analysis (charts, AI summary, activity bars) for the currently selected simtree branch node. When a simulation has many branches, users cannot switch which branch they are analyzing from within the analysis view — they must navigate back to the simtree to pick a different node.

## Solution

Add a branch node selector dropdown to the top of ResultsView. Changing the selection calls the existing `store.selectNode(id)` action, which fetches fresh events and state for that node. All charts and summaries update automatically because they already read from the store.

## Design

### Placement

Inside the existing "AI Analysis" card at the top of ResultsView, above the AI summary generate button. A new row with a "Branch" label, a dropdown of all nodes, and a subtle `worldTime` hint next to the selected node.

### Dropdown Content

- Lists all `SimNode` entries from the store, sorted by depth then by `display_id`
- Each option shows: `{display_id} — {name}` (e.g. "0.1.2 — Branch C")
- Root node is included as an option
- The option matching the current `selectedNodeId` is pre-selected

### Behavior

- On mount, defaults to whatever `selectedNodeId` is in the store
- Changing the dropdown calls `selectNode(id)` — the same store action the simtree uses
- This triggers the existing fetch pipeline: `selectNode` fetches sim state and events for the chosen node, updates logs and agents in the store
- The analysis charts, AI summary, and activity bars all re-render with the new data automatically
- Since it uses the same `selectedNodeId` state, changing the node in the analysis view also updates the simtree's selection

### Files Changed

- `frontend/components/results/ResultsView.tsx` — add the node selector dropdown, read `nodes` and `selectNode` from store, wire the `onChange` handler

No new files. No store changes. No backend changes.

### Edge Cases

- If `nodes` is empty, the selector is hidden
- If `selectedNodeId` is not found in `nodes` (e.g. loading state), the dropdown shows a "Select branch" placeholder
- The `selectNode` call is async and may fetch data — the existing loading states in the store handle this
