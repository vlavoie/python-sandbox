# ISSUE-12: Generation cost display

**Type:** Feature  
**Status:** Implemented  
**Files:** `src/pasokon/grok_client.py`, `src/pasokon/workflow_panel.py`

## What was added
After each image generation batch, the total cost is surfaced in the UI progress label.

`generate_single_image` returns a 3-tuple `(index, image_data, cost_ticks)` where `cost_ticks`
comes from `response["usage"]["cost_in_usd_ticks"]`. The parallel generation loop accumulates
`total_cost_ticks` across all images. `generate_images` returns `(successful_images, total_cost_ticks)`.

`generate_images_batch` divides by 10,000,000,000 to get USD and formats it for display.

## Key invariants
- `cost_in_usd_ticks` is in the `usage` field of the image API response, not `choices`.
- Divide by `10_000_000_000` (10 billion) to get USD.
- `generate_single_image` must return 3 values; the parallel unpack loop must unpack 3.
  Mismatch causes a `ValueError` at runtime.
