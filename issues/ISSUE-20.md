# ISSUE-20: Per-work-item reference snapshots

**Type:** Feature  
**Status:** Added  
**Files:**
- `src/pasokon/workflow_panel.py` — `get_work_item_references()` hook + copy logic in `_save_images_permanently`
- `src/pasokon/fpv_workflow.py` — override returning character reference, additional images, greenzone base
- `src/pasokon/finalize_workflow.py` — override returning character reference + source image

## What was added

On the first iteration of each work item (`iteration == 0`), `_save_images_permanently` now creates a `references/` folder inside `work-item-N/` and copies all reference images there.

**Output structure after the change:**
```
work-item-N/
  references/
    character_reference.png
    additional_0.png          (if Phase 1 multi-char)
    greenzone_base.png        (if Phase 2)
    source_image.png          (Finalize only)
  2026-08-16_11-43-16_iteration-0/
    image_1.png
    prompt.txt
  2026-08-16_11-45-00_iteration-1/
    ...
```

**FPV panel saves:**
- `character_reference` — always
- `additional_0`, `additional_1`… — if additional character images were uploaded
- `greenzone_base` — if Phase 2

**Finalize panel saves:**
- `character_reference` — from `fpv_panel.reference_image_path` (IMAGE_0)
- `source_image` — the finished image being refined (IMAGE_1)

## Key invariants

- `get_work_item_references()` is a no-op hook in the base class (returns `{}`); subclasses opt in
- Copy only runs on `iteration == 0` — once per work item, not per generation batch
- Missing or non-existent paths are silently skipped (`if path and Path(path).exists()`)
- Existing project-level `references/` copy in `serialize()` is unchanged — this is additive
