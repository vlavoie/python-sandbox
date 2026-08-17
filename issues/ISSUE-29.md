# ISSUE-29: [feature] Per-prompt and aggregate project cost tracking

## What was added

Each panel now tracks a `cost_log` list — a list of `{work_item, iteration, ticks}` dicts, one entry per image generation batch. This is persisted in `serialize`/`deserialize` alongside the rest of panel state.

`_work_item_status()` (shown in the work item label below the generation controls) now includes cost:
- Current prompt cost appears when at least one generation has been done for the current work item.
- Project total appears alongside it when there are costs from prior work items.
- Format: `**Work Item 2** · Iteration 3 · 💰 $0.0023 · total: $0.0041`

## API cost availability

Only **image generation** (`/images/edits`) returns `cost_in_usd_ticks` in `usage`. Chat completions (`/chat/completions`) return token counts only — no USD ticks. So cost tracking only covers image generation, which is the dominant cost.

## Key invariants

- `cost_log` entries are never removed or reset — they accumulate across all work items for the lifetime of the project. `_start_new_prompt()` does NOT clear `cost_log`.
- The cost entry is appended **before** `self.iteration_count` is incremented, so `entry["iteration"]` matches the index used for the saved directory name.
- Old projects without `cost_log` load cleanly — `deserialize` defaults to `[]`.
