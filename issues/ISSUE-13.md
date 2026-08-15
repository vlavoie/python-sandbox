# ISSUE-13: Prompt box was in Generate Prompt tab instead of Generate Images tab

**Type:** Bug (regression)  
**Status:** Fixed  
**Files:** `src/pasokon/workflow_panel.py` → `render()`

## Root Cause
`prompt_box` was rendered inside the "Generate Prompt" tab, so after clicking Generate Prompt
the user had to manually navigate to the Generate Images tab to see the result and kick off
generation. The intended flow is: click Generate Prompt → API responds → land on Generate
Images tab with the prompt already visible at the top, ready to generate.

## Fix
Moved `prompt_box` to the top of the "Generate Images" tab. The Generate Prompt tab now
contains only the subclass inputs (`render_prompt_tab_content`) and the button.

No wiring changes were needed — `do_generate_prompt` already yields
`gr.update(selected=f"{panel_id}_gen_images")` for `panel_tabs` and the prompt text for
`prompt_box`, so the tab switch and prompt fill both happen automatically after the API call.

## Key Invariant
`prompt_box` must be rendered BEFORE it is wired as an output. `render_prompt_tab_content()`
runs before `prompt_box` is created; subclasses must not reference `self.prompt_box` inside
that hook (use `get_ui_outputs()` / `get_ui_restore_values()` instead, which run after `render()`).
