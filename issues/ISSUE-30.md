# ISSUE-30: [bug] serialize() in FPV and Element panels reimplemented base fields, losing cost_log

## Root cause

`FPVWorkflowPanel.serialize()` and `ElementWorkflowPanel.serialize()` both returned hand-rolled dicts instead of calling `super().serialize(project_dir)`. Neither included `cost_log`. FPV also omitted `cost_log` in `deserialize()` (no `super().deserialize(d)` call), so cost history was never restored from disk. On reload, `cost_log` silently reverted to `[]` for FPV and element projects.

`FinalizeWorkflowPanel` was already correct (called super in both directions).

## Fix

### FPV

`serialize()`: compute the image copy paths first, then call `super().serialize(project_dir)` and extend the dict with FPV-specific fields.

`deserialize()`: call `super().deserialize(d)` first (which restores `cost_log`, `image_model`, etc.), then restore FPV-specific fields. Legacy `phase1_review_history` fallback preserved:
```python
if not self.review_history:
    self.review_history = d.get("phase1_review_history", [])
```

### Element

`serialize()`: replaced hand-rolled dict with `super().serialize(project_dir)` extended with element-specific fields.

`deserialize()` was already calling super correctly — no change needed.

## Key invariant

Panel `serialize()` overrides must call `super().serialize(project_dir)` and extend the returned dict — never reimplement base fields. Panel `deserialize()` overrides must call `super().deserialize(d)` first. The base saves and restores: `current_prompt`, `generated_images`, `iteration_count`, `work_item`, `review_history`, `review_context`, `cost_log`, `image_model`, `image_resolution`, `aspect_ratio`.
