# ISSUE-27: [feature] Content moderation warning bubble

## What was added

When xAI returns `{'code':'imagine:content-moderated', 'error':'...', 'usage':{...}}` as a successful (200 OK) response body, the app now shows a `gr.Warning()` toast rather than silently failing.

### grok_client.py

In `generate_single_image`, after parsing `result = response.json()`, check for the moderation code before processing image data:

```python
if result.get("code") == "imagine:content-moderated":
    raise Exception(f"imagine:content-moderated: {result.get('error', '...')}")
```

In the `ThreadPoolExecutor` loop, moderation exceptions are separated from other failures into a `moderation_messages` list. Return signature changed to a 3-tuple:

```python
return (successful_images, total_cost_ticks, moderation_messages)
```

If ALL images were moderated (no successes, no other errors), the exception is re-raised so the caller's except block handles it.

### workflow_panel.py

Unpacks the 3-tuple and calls `gr.Warning()` for each moderation message. The all-moderated path is caught in the `except` block, detected by the `"imagine:content-moderated:"` prefix, and also calls `gr.Warning()`.

## Cases covered

| Scenario | Behaviour |
|---|---|
| All images moderated | `gr.Warning()` toast, returns `"🚫 Content moderated."` status |
| Some images moderated, some succeeded | `gr.Warning()` per moderated image, successful images displayed normally |
| Single image moderated | Same as all-images case |

## Key invariant

The content moderation response is a **200 OK** with an error code in the body, not an HTTP error. It is not caught by `raise_for_status()` and must be checked explicitly after `response.json()`.
