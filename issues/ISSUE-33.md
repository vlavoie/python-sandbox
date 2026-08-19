# ISSUE-33 — [bug] Prompt code blocks in review chat render as single horizontal line

## Root cause

Gradio's `MarkdownCode` component CSS (`MarkdownCode-Ca9FjBJK.css`) sets
`white-space: pre` on `.md pre` elements. This file is loaded **lazily** (only when
a chatbot message with code content is first rendered), so it always executes *after*
the custom CSS injected by `gr.Blocks(css=...)`. This means any static stylesheet
rule targeting `.md pre` — including ones with `!important` — is overridden by the
component CSS that loads last.

The result: FPV prompts (dense single-paragraph text) displayed inside markdown code
blocks rendered as one long horizontal line with a scrollbar, making them unreadable
without clicking "Extract".

## Attempted approaches that failed

1. **`white-space: pre-wrap` in `gallery.css` targeting `.gradio-container pre`**
   — Lost the specificity battle (0-1-1 vs Gradio's 0-2-1).

2. **Same rule with `.gradio-container .md pre`** — Equal specificity (0-2-1), but
   Gradio's lazily-loaded component CSS still loads *after* our `<style>` tag, so it
   wins on source order.

3. **`!important` on `.gradio-container .md pre` rules** — `!important` on
   `overflow` took effect (content stopped escaping the box) but `white-space:
   pre-wrap !important` was still beaten, indicating the MarkdownCode CSS reloads
   on every component render, after our injection.

4. **MutationObserver in `gallery.js`** — Should theoretically work (JS inline
   `style.setProperty(..., 'important')` beats all stylesheets), but Gradio
   re-renders the chatbot markup on every streaming token and the race between
   component CSS re-application and the observer callback was not reliable.

## Fix

**`_inject_extract_buttons` in `workflow_panel.py`** — This function already
post-processes messages for the display copy (it injects the "↗ Use this prompt"
button). Changed it to also replace the markdown code block (```` ``` … ``` ````)
with a raw `<pre style="...">` element carrying inline `white-space: pre-wrap`
styles. Inline `style` attributes are authoritative — no stylesheet can override
them regardless of specificity or load order.

```python
_PRE_STYLE = (
    "white-space:pre-wrap;word-break:break-word;overflow-wrap:break-word;"
    "overflow:auto;background:var(--code-background-fill);"
    "padding:var(--spacing-xxl);border-radius:var(--radius-sm);"
    "font-family:var(--font-mono);font-size:var(--text-sm);display:block;margin:.5em 0;"
)
```

The prompt body is HTML-escaped (for the `<pre>` content) and also attribute-escaped
(for the `data-prompt` on the extract button). The stored `review_history` is
unchanged — only the display copy produced by `_inject_extract_buttons` uses HTML.

## Key invariant

**Never fight Gradio's lazy-loaded component CSS with static CSS rules.**
`MarkdownCode` and other Gradio components inject their CSS on first render, after
`gr.Blocks(css=...)` is already in the page. The only reliable override points are:

- **Inline `style` attributes** set in Python before the message reaches the chatbot.
- **JavaScript** that re-applies inline styles *after* each DOM mutation (fragile due
  to streaming re-renders).

For any chatbot display transformation, prefer the Python post-processing path in
`_inject_extract_buttons` (or a similar display-copy hook) over CSS overrides.
