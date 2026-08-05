# FOS Checkpoint Granularity Investigation

Date: 2026-08-05

## 1. Smallest unit of work

`run_headless_council()` (line 963) loops over `selected_proposals × networks`, creating one `tree.branch()` + `tree.advance(branch_id, turns=4)` per (proposal, network) pair. One condition = one branch = 4 turns (3 deliberation + 1 vote).

**Answer:** One condition — one (proposal, network) pair.

## 2. Single-condition isolation

Yes. The inner loop body (lines 1068–1241) is a self-contained per-condition invocation:
1. Permute node assignment + relabel edges
2. Assign confederates (3 yes, 3 no)
3. Deep-copy agents + inject confederate prompts
4. `tree.branch(root_id, [{"op": "network_replace", "network": run_network}])`
5. `tree.advance(branch_id, turns=4)`
6. Extract logs and metadata

**File:** `scripts/headless_council.py`, lines 1068–1241.

## 3. SimTree serialization

**`SimTree.serialize()`** (`src/fos/core/simtree.py:442`): captures every node as `{id, parent, depth, edge_type, ops, sim: sim.serialize(), logs, meta}`. The `sim` field contains the serialized `ExperimentRunnerAdapter` including scene state.

**`SimTree.deserialize()`** (`src/fos/core/simtree.py:467`): restores the full tree. A deserialized tree can resume at any node — `tree.advance(existing_node_id, turns=N)` on a restored node picks up exactly where it left off.

**Answer:** Serialize captures complete mid-experiment state. After `advance(turns=1)`, the node has logs for 1 turn; calling `advance(turns=1)` again adds turn 2 logs.

## 4. Existing disk writes

`_write_progress()` (`scripts/headless_council.py:1048, 1148, 1234, 1243`) writes `.progress.json` with keys: `status`, `branch`, `total_branches`, `proposal`, `network`, `events`, `started_at`/`finished_at`. It is a reporting artifact — it does not store SimTree state and is not resumable.

**Answer:** No existing checkpoint is resumable. The layer must add its own.

## 5. Per-round observability

`ExperimentRunnerAdapter.run(max_turns=N)` (`src/fos/backend/services/simtree_runtime.py:139`) loops:

```python
for _ in range(max_turns):
    if self.scene.is_complete():
        break
    self._run_scene_round()    # one round
    self.scene._advance_round()
```

`SimTree.advance(parent_id, turns=N)` calls `sim.run(max_turns=N)`. Therefore:
- `tree.advance(branch_id, turns=1)` → runs 1 round, returns the node
- `tree.advance(same_node, turns=1)` again → runs the next round from the same node

Between calls, the tree can be serialized. On resume, deserialize and continue.

**Answer:** YES — per-round advancement is natively supported. No FOS internals need modification.

## 6. Individual agent response persistence

Agent responses are collected in `tree.nodes[node_id]["logs"]` after `advance()` completes. The `_emit_event` callback (`simtree_runtime.py:194`) appends to `self.events` and calls the internal log handler. No externally visible per-agent hook exists.

**Answer:** Agent responses are only available per-round (after advance completes), not per-agent mid-round. Per-agent resume would require modifying FOS internals.

## 7. Timing

From `run_079` (100 agents, real LLM calls): one full condition = 11 minutes 18 seconds. Setup (network rebuild + placement + scene init) is under 15 seconds. Each round ≈ 3–4 minutes.

## Achievable without modifying FOS internals

| Level | Feasible | Mechanism |
|-------|----------|-----------|
| (a) Per-agent resume | **NO** | Would require modifying `_emit_event` or scene internals |
| (b) Per-round resume | **YES** | `tree.advance(turns=1)` per round, serialize between rounds |
| (c) Per-condition resume | **YES** | `tree.advance(turns=4)`, serialize after. Trivial |
| (d) Coarser | Not needed | |

## Recommendation

**Target (b) — per-round resume.** The mechanism:
1. `branch_id = tree.branch(root_id, [network_op])`
2. For round in 1..4: `finished_id = tree.advance(branch_id, turns=1)`, record `run_progress` stage `round_{round}`, serialize tree to `runs/checkpoints/{run_id}.json`
3. On resume: deserialize tree, find the last completed round, continue from the next

4 natural checkpoints per run. An interruption re-executes at most one round (~3 minutes). Requires zero FOS modifications.
