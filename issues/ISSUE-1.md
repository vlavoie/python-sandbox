# ISSUE-1: Review thumbnails vanish after program restart

**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `generate_images_batch`

## Root Cause
`self.generated_images` stored paths from `tempfile.NamedTemporaryFile`. Those temp files
are deleted by the OS on restart, so `render_gallery_html` finds nothing and returns empty HTML.

## Fix
`generate_images_batch` now records the permanent save paths from `_save_images_permanently`
instead of creating duplicate temp files:
```python
images = [str(saved_dir / f"image_{i}.png") for i in range(1, len(image_data_list) + 1)]
```
Files saved as `image_1.png … image_N.png` under the project directory survive restarts.

## Key Invariant
`self.generated_images` must always contain paths that survive a program restart.
Never store temp paths in any persistent state field.
