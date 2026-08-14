"""Standalone HTML thumbnail gallery with lightbox — no Gradio Gallery dependency."""
import base64
from pathlib import Path


def render_gallery_html(image_paths) -> str:
    """Return an HTML thumbnail strip for the given image paths.

    Accepts plain strings, (path, caption) tuples, or Gradio FileData dicts.
    Returns an empty string when there are no valid images.
    """
    if not image_paths:
        return ""

    thumbs = []
    for item in image_paths:
        if isinstance(item, str):
            path = item
        elif isinstance(item, (list, tuple)) and item:
            path = str(item[0])
        elif isinstance(item, dict):
            inner = item.get("image", item)
            path = inner.get("path", "") if isinstance(inner, dict) else str(inner)
        else:
            continue

        if not path:
            continue
        p = Path(path)
        if not p.exists():
            continue
        ext = p.suffix.lower().lstrip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
        try:
            b64 = base64.b64encode(p.read_bytes()).decode()
            thumbs.append(
                f'<img class="psk-thumb" src="data:image/{mime};base64,{b64}" />'
            )
        except Exception:
            continue

    if not thumbs:
        return ""

    return '<div class="psk-gallery">' + "".join(thumbs) + "</div>"
