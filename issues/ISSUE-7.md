# ISSUE-7: PNG transparency stripped on element reference upload

**Status:** Fixed  
**Files:** `src/pasokon/element_workflow.py` → `element_reference` gr.Image component

## Root Cause
`gr.Image` without `image_mode=None` converts uploaded images to RGB internally,
stripping the alpha channel from PNGs before passing the file path to the handler.
The FPV reference image already had `image_mode=None` but the element reference did not.

## Fix
Added `image_mode=None` to the `element_reference` gr.Image component:
```python
self.element_reference = gr.Image(
    label="Character Reference (optional — uses FPV reference if empty)",
    type="filepath",
    image_mode=None,
    ...
)
```

## Key Invariant
All `gr.Image` components that accept user uploads must use `image_mode=None` to preserve
the original file format. Without it, Gradio converts to RGB and PNG transparency is lost.
