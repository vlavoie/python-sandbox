"""WorkflowPanel: reusable Generate Prompt → Generate Images → Review component."""

import html as _html
import httpx
import io
import re
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
from gradio.components.chatbot import ComponentMessage
from PIL import Image

from .gallery_widget import render_gallery_html
from .grok_client import GrokClient


class WorkflowPanel(ABC):
    """
    Reusable Gradio component that provides the three-step workflow:
    Generate Prompt → Generate Images → Review & Correct.

    Subclasses override:
      - panel_id         (property) — unique prefix for Gradio element IDs
      - do_generate_prompt(*inputs) — generator; yields (prompt, tabs_upd, chatbot_upd, btn_upd)
      - get_review_skill()          — review skill content (may prepend mode prefix)
      - build_review_context(images) — builds the review context dict

    Optional overrides:
      - render_prompt_tab_content()      — add inputs above the prompt box
      - render_images_tab_extra_controls() — add controls above the sliders
      - get_prompt_tab_inputs()          — list of components fed into do_generate_prompt
      - get_reference_image_path()       — path to IMAGE_0
      - get_additional_images_for_generation() — extra images for image gen
      - get_output_subdir()              — subdir under project/iteration folder
      - get_ui_outputs()                 — components for project load/restore
      - get_ui_restore_values()          — gr.update() values matching get_ui_outputs()
    """

    def __init__(self, app):
        self.app = app

        # Per-panel persistent state
        self.current_prompt: str = ""
        self.generated_images: List[str] = []
        self.iteration_count: int = 0
        self.work_item: int = 1
        self.review_history: List = []
        # Parallel to review_history — image paths shown with each message.
        # User messages: List[str] of paths; assistant messages: [].
        self.review_galleries: List = []
        self.review_context: dict = {}
        self.cost_log: List[Dict] = []
        # Per-panel model/quality settings — initialized from panel defaults
        self.image_model: str = self.default_image_model
        self.image_resolution: str = self.default_image_resolution
        self.aspect_ratio: str = self.default_aspect_ratio

        # Gradio component refs — populated by render()
        self.panel_tabs = None
        self.prompt_box = None
        self.output_gallery = None
        self.failed_gallery = None
        self.review_chatbot = None
        self.review_input = None
        self._gen_prompt_btn = None
        self._gen_images_btn = None
        self._send_btn = None

        self._failed_upload = None
        self._num_images_slider = None
        self._aspect_ratio_dropdown = None
        self._draft_mode_radio = None
        self.image_model_dropdown = None
        self.draft_model_dropdown = None
        self.image_resolution_dropdown = None
        self._work_item_label = None
        self._dup_confirm_row = None
        self._gen_anyway_btn = None
        self._dup_cancel_btn = None

        # Session-only (not persisted) — tracks last prompt sent to the API
        self._last_submitted_prompt: str = ""
        # Display history for the chatbot UI — parallel to review_history but may
        # include base64-embedded image thumbnails in user messages.  Never sent
        # to the API; reset to text-only review_history on project load.
        self._ui_history: List = []

    # ── abstract interface ────────────────────────────────────────────────

    @property
    @abstractmethod
    def panel_id(self) -> str:
        """Unique string prefix for all Gradio element IDs in this panel."""

    @property
    def default_image_model(self) -> str:
        return "grok-imagine-image-2.0"

    @property
    def default_image_resolution(self) -> str:
        return "1k"

    @property
    def default_aspect_ratio(self) -> str:
        return "16:9"

    @abstractmethod
    def do_generate_prompt(self, *inputs):
        """
        Generator function for prompt generation.
        Yields tuples of (prompt_text, tabs_update, chatbot_update, btn_update).
        """

    @abstractmethod
    def get_review_skill(self) -> str:
        """Return the review skill content (with any mode-specific prefix prepended)."""

    @abstractmethod
    def build_review_context(self, images_to_review: List[str]) -> dict:
        """
        Return a review context dict with at least:
          failed_images, original_prompt, scene_description,
          reference_image, additional_images, review_mode
        The caller appends user_initial_comment.
        """

    # ── optional hooks ────────────────────────────────────────────────────

    def _work_item_status(self) -> str:
        wi_ticks = sum(e["ticks"] for e in self.cost_log if e.get("work_item") == self.work_item)
        total_ticks = sum(e["ticks"] for e in self.cost_log)
        parts = [f"**Work Item {self.work_item}** · Iteration {self.iteration_count}"]
        if wi_ticks:
            parts.append(f"💰 ${wi_ticks / 10_000_000_000:.4f}")
        if total_ticks and total_ticks != wi_ticks:
            parts.append(f"total: ${total_ticks / 10_000_000_000:.4f}")
        return " · ".join(parts)

    def _start_new_prompt(self) -> None:
        """Advance work item if prior work exists, then clear per-item state.
        Call at the top of do_generate_prompt in every subclass."""
        if self.iteration_count > 0 or self.generated_images:
            self.work_item += 1
            self.iteration_count = 0
            self.generated_images = []
        self.review_history = []
        self.review_galleries = []
        self.review_context = {}

    def render_prompt_tab_content(self) -> None:
        """Add subclass-specific inputs above the shared prompt box."""

    def render_images_tab_extra_controls(self) -> None:
        """Create the model and quality dropdowns shared by all panels."""
        with gr.Row():
            self.image_model_dropdown = gr.Dropdown(
                choices=[
                    "grok-imagine-image-pro",
                    "grok-imagine-image-quality",
                    "grok-imagine-image-2.0",
                    "grok-imagine-image",
                ],
                value=self.image_model,
                label="🎨 Model",
                interactive=True,
                allow_custom_value=True,
            )
            is_aurora = self.image_model == "grok-imagine-image-2.0"
            self.image_resolution_dropdown = gr.Dropdown(
                choices=["auto", "1k", "2k"],
                value=self.image_resolution if is_aurora else "auto",
                label="Resolution (2.0 only)",
                interactive=is_aurora,
            )

    def get_prompt_tab_inputs(self) -> List:
        """Gradio components passed as inputs to do_generate_prompt."""
        return []

    def get_reference_image_path(self) -> Optional[str]:
        return None

    def get_additional_images_for_generation(self) -> Optional[List[str]]:
        return None

    def get_output_subdir(self) -> str:
        return ""

    def get_work_item_references(self) -> Dict[str, str]:
        """Return {filename_stem: path} of reference images to copy into work-item-N/references/.
        Called once on iteration 0 of each work item. Override in subclasses."""
        return {}

    def get_ui_outputs(self) -> List:
        """Components list for project load/restore outputs — override in subclass."""
        return [
            self.prompt_box,
            self.failed_gallery,
            self.output_gallery,
            self.review_chatbot,
            self.image_model_dropdown,
            self.image_resolution_dropdown,
            self._aspect_ratio_dropdown,
            self._work_item_label,
            self.panel_tabs,
        ]

    def get_ui_restore_values(self) -> List:
        """gr.update() values matching get_ui_outputs() — override in subclass."""
        is_aurora = self.image_model == "grok-imagine-image-2.0"
        review_buffer = "" if self.review_history else render_gallery_html(self.generated_images or [])
        return [
            gr.update(value=self.current_prompt),
            gr.update(value=review_buffer),
            gr.update(value=render_gallery_html(self.generated_images or [])),
            gr.update(value=self._ui_history),
            gr.update(value=self.image_model),
            gr.update(value=self.image_resolution if is_aurora else "auto", interactive=is_aurora),
            gr.update(value=self.aspect_ratio),
            gr.update(value=self._work_item_status()),
            gr.update(selected=f"{self.panel_id}_gen_prompt"),
        ]

    # ── image generation ─────────────────────────────────────────────────

    def _save_images_permanently(
        self, image_data_list: List[bytes], prompt: str, iteration: int, aspect_ratio: str
    ) -> Path:
        ps = self.app.project_state
        base_dir = ps.output_dir / ps.project_name
        if self.get_output_subdir():
            base_dir = base_dir / self.get_output_subdir()
        base_dir = base_dir / f"work-item-{self.work_item}"
        base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        batch_dir = base_dir / f"{timestamp}_iteration-{iteration}"
        batch_dir.mkdir(exist_ok=True)
        if iteration == 0:
            refs = self.get_work_item_references()
            if refs:
                refs_dir = base_dir / "references"
                refs_dir.mkdir(exist_ok=True)
                for name, path in refs.items():
                    if path and Path(path).exists():
                        suffix = Path(path).suffix or ".png"
                        shutil.copy2(path, refs_dir / f"{name}{suffix}")

        for i, img_data in enumerate(image_data_list, 1):
            img = Image.open(io.BytesIO(img_data))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.save(batch_dir / f"image_{i}.png", "PNG", optimize=True)
        with open(batch_dir / "prompt.txt", "w", encoding="utf-8") as fh:
            fh.write(
                f"Project: {ps.project_name}\nIteration: {iteration}\n"
                f"Aspect Ratio: {aspect_ratio}\n\n{'='*60}\nPROMPT:\n{'='*60}\n\n{prompt}"
            )
        return batch_dir

    def generate_images_batch(
        self,
        prompt: str,
        num_images: int = 3,
        aspect_ratio: str = "16:9",
        model_override: str = None,
        resolution_override: str = None,
        progress_callback=None,
    ) -> Tuple[str, List, List]:
        client = self.app.client
        if not client:
            return "❌ Configure API key first.", [], []
        if not prompt.strip():
            return "❌ Provide a prompt.", [], []
        ref = self.get_reference_image_path()
        if not ref:
            return "❌ No reference image.", [], []
        try:
            image_data_list, total_cost_ticks, moderation_messages = client.generate_images(
                prompt=prompt,
                reference_image=ref,
                num_images=num_images,
                additional_images=self.get_additional_images_for_generation(),
                aspect_ratio=aspect_ratio,
                model=model_override,
                resolution=resolution_override,
                progress_callback=progress_callback,
            )
            for msg in moderation_messages:
                gr.Warning(f"🚫 Content moderated: {msg}")
            if not image_data_list:
                return "❌ No images generated.", [], []

            saved_dir = self._save_images_permanently(
                image_data_list, prompt, self.iteration_count, aspect_ratio
            )
            images = [str(saved_dir / f"image_{i}.png") for i in range(1, len(image_data_list) + 1)]

            if total_cost_ticks:
                self.cost_log.append({
                    "work_item": self.work_item,
                    "iteration": self.iteration_count,
                    "ticks": total_cost_ticks,
                })
            self.iteration_count += 1
            self.generated_images = images
            self.current_prompt = prompt
            if self.review_context:
                self.review_context["failed_images"] = images
                self.review_context["original_prompt"] = prompt

            ps = self.app.project_state
            is_partial = len(images) < num_images
            wi_label = f"Work Item {self.work_item} · Iteration {self.iteration_count}"
            cost_str = f"💰 Cost: ${total_cost_ticks / 10_000_000_000:.4f}" if total_cost_ticks else ""
            status = (
                f"⚠️ Partial: {len(images)}/{num_images} images ({wi_label})\n"
                f"💾 Saved to: {ps.project_name}/{saved_dir.name}/\n{cost_str}"
                if is_partial else
                f"✅ Generated {len(images)} images ({wi_label})\n"
                f"💾 Saved to: {ps.project_name}/{saved_dir.name}/\n{cost_str}"
            )
            ps.save_project_state()
            return status, images, images

        except Exception as e:
            err_str = str(e)
            if err_str.startswith("imagine:content-moderated:"):
                msg = err_str.split(":", 2)[-1].strip()
                gr.Warning(f"🚫 Content moderated: {msg}")
                return "🚫 Content moderated.", [], []
            return f"❌ Error: {err_str}", [], []

    def _generate_images_for_ui(
        self, prompt, num_images, aspect_ratio, progress=gr.Progress()
    ):
        if (
            prompt
            and prompt.strip()
            and prompt.strip() == self._last_submitted_prompt.strip()
        ):
            yield render_gallery_html(self.generated_images), gr.update(), gr.update(visible=True), gr.update(), gr.update()
            return
        yield gr.update(), gr.update(), gr.update(visible=False), gr.update(interactive=False), gr.update(interactive=False)
        self._last_submitted_prompt = (prompt or "").strip()
        gallery, failed = self._do_generate(prompt, num_images, aspect_ratio, progress)
        yield gallery, failed, gr.update(visible=False), gr.update(interactive=True), gr.update(interactive=True)

    def _force_generate_images_for_ui(
        self, prompt, num_images, aspect_ratio, progress=gr.Progress()
    ):
        yield gr.update(), gr.update(), gr.update(), gr.update(interactive=False), gr.update(interactive=False)
        self._last_submitted_prompt = (prompt or "").strip()
        gallery, failed = self._do_generate(prompt, num_images, aspect_ratio, progress)
        yield gallery, failed, gr.update(visible=False), gr.update(interactive=True), gr.update(interactive=True)

    def _do_generate(self, prompt, num_images, aspect_ratio, progress):
        try:
            def on_done(c, t):
                progress(c / t, desc=f"Image {c}/{t} done...")

            r = self.image_resolution if self.image_resolution != "auto" else None
            progress(0, desc=f"Generating {num_images} image(s)...")
            _, images, _ = self.generate_images_batch(
                prompt, num_images, aspect_ratio,
                model_override=self.image_model,
                resolution_override=r,
                progress_callback=on_done,
            )

            if not images:
                progress(1.0, desc="No images returned")
                return render_gallery_html(self.generated_images), gr.update()

            progress(1.0, desc="Done")
            return render_gallery_html(images), render_gallery_html(images)

        except Exception:
            progress(1.0, desc="Failed")
            return render_gallery_html(self.generated_images), gr.update()

    # ── review ────────────────────────────────────────────────────────────

    def start_review(
        self, user_comment: str, uploaded_files=None
    ) -> Tuple[List, str, List]:
        client = self.app.client
        if not client:
            return [], "❌ Configure API key first.", []

        ps = self.app.project_state
        images_to_review = []
        if uploaded_files:
            for f in uploaded_files:
                if f is not None:
                    p = ps.save_uploaded_file(f)
                    if p:
                        images_to_review.append(p)
        elif self.generated_images:
            images_to_review = list(self.generated_images)

        if not images_to_review:
            return [], "❌ No images to review.", []

        try:
            user_display = user_comment.strip() or "Review these"
            ctx = self.build_review_context(images_to_review)
            ctx["user_initial_comment"] = user_display
            self.review_context = ctx

            initial_review = client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=ctx.get("scene_description", ""),
                reference_image=ctx.get("reference_image", ""),
                skill_content=self.get_review_skill(),
                additional_images=ctx.get("additional_images"),
                user_comment=user_display,
                review_mode=ctx.get("review_mode", "phase1"),
            )

            self.review_history = [
                {"role": "user", "content": user_display},
                {"role": "assistant", "content": initial_review},
            ]
            ps.save_project_state()

            mode = ctx.get("review_mode", "phase1")
            mode_label = "Phase 2 Enhancement" if mode == "phase2" else "Phase 1"
            add_info = ctx.get("mode_info", "")
            instructions = (
                f"✅ {mode_label} Review started!\n\n"
                f"📸 {len(images_to_review)} image(s) being analyzed\n"
                f"🗂 <IMAGE_0> = Character reference (always){add_info}\n"
                f"💬 Refer to images as 'image 1', 'image 2', etc."
            )
            return self.review_history, instructions, images_to_review

        except Exception as e:
            return [], f"❌ Error during review: {str(e)}", []

    def _build_continue_review_messages(self, user_message: str) -> List:
        """Build the messages list for a continue_review API call."""
        client = self.app.client
        messages = [{"role": "system", "content": self.get_review_skill()}]

        if self.review_context:
            content = []
            ref = self.review_context.get("reference_image")
            if ref:
                content.append({"type": "text", "text": "Character reference (IMAGE_0):"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{client._encode_image(ref)}"},
                })

            review_mode = self.review_context.get("review_mode", "phase1")
            for idx, img_path in enumerate(self.review_context.get("additional_images") or [], 1):
                label = (
                    "Green-zoned base image (IMAGE_1) — surgical base; preserve everything outside the marked zones exactly:"
                    if review_mode == "phase2" and idx == 1
                    else f"Additional reference (IMAGE_{idx}):"
                )
                content.append({"type": "text", "text": label})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{client._encode_image(img_path)}"},
                })

            for i, ip in enumerate(self.review_context.get("failed_images", []), 1):
                content.append({"type": "text", "text": f"Image {i}:"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{client._encode_image(ip)}"},
                })

            content.append({
                "type": "text",
                "text": f"Original prompt:\n```\n{self.review_context.get('original_prompt', '')}\n```",
            })
            content.append({
                "type": "text",
                "text": f"Scene description:\n{self.review_context.get('scene_description', '')}",
            })
            if ic := self.review_context.get("user_initial_comment", ""):
                content.append({"type": "text", "text": f"User's initial feedback:\n{ic}"})

            messages.append({"role": "user", "content": content})

        skip_first_user = True
        for msg in self.review_history:
            if skip_first_user and msg["role"] == "user":
                skip_first_user = False
                continue
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})
        return messages

    def continue_review(self, user_message: str) -> Tuple[List, str]:
        client = self.app.client
        if not client:
            return self.review_history, "❌ Client not initialized"
        if not user_message.strip():
            return self.review_history, ""

        try:
            messages = self._build_continue_review_messages(user_message)

            with httpx.Client(timeout=120.0) as hc:
                resp = hc.post(
                    f"{client.base_url}/chat/completions",
                    headers=client.headers,
                    json={"model": client.chat_model, "messages": messages},
                )
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    try:
                        api_msg = e.response.json().get("error", {}).get("message", "")
                        if any(k in api_msg.lower() for k in ("content", "policy", "moderation", "safety")):
                            raise Exception("Warning: No response returned")
                    except Exception as inner:
                        if "Warning:" in str(inner):
                            raise
                    raise
                res = resp.json()
                ar = res["choices"][0]["message"]["content"]
                if not ar:
                    raise Exception("Warning: No response returned")

            new_history = self.review_history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": ar},
            ]
            self.review_history = new_history
            self.app.project_state.save_project_state()
            return new_history, ""

        except Exception as e:
            return self.review_history, f"❌ Error: {str(e)}"

    def stream_start_review(self, user_comment: str, uploaded_files=None):
        """Generator: yields (partial_history, images_reviewed) tuples as the first review streams."""
        client = self.app.client
        if not client:
            user_display = user_comment.strip() or "Review these"
            yield [
                {"role": "user", "content": user_display},
                {"role": "assistant", "content": "❌ Client not initialized."},
            ], []
            return

        ps = self.app.project_state
        images_to_review = list(self.generated_images or [])
        if uploaded_files:
            for f in uploaded_files:
                if f is not None:
                    p = ps.save_uploaded_file(f)
                    if p:
                        images_to_review.append(p)

        user_display = user_comment.strip() or "Review these"

        if not images_to_review and not self.current_prompt:
            yield [
                {"role": "user", "content": user_display},
                {"role": "assistant", "content": "❌ No prompt or images to review yet."},
            ], []
            return

        ctx = self.build_review_context(images_to_review)
        ctx["user_initial_comment"] = user_display
        self.review_context = ctx

        user_msg = {"role": "user", "content": user_display}
        partial = ""
        error = None

        if not images_to_review:
            # Prompt-only review — analyze before generating
            messages = [{"role": "system", "content": self.get_review_skill()}]
            content = []
            ref = ctx.get("reference_image")
            if ref:
                content.append({"type": "text", "text": "Character reference (IMAGE_0):"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{client._encode_image(ref)}"},
                })
            for idx, img_path in enumerate(ctx.get("additional_images") or [], 1):
                content.append({"type": "text", "text": f"Additional reference (IMAGE_{idx}):"})
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{client._encode_image(img_path)}"},
                })
            content.append({
                "type": "text",
                "text": f"Prompt to review (no images generated yet):\n```\n{self.current_prompt}\n```",
            })
            if ctx.get("scene_description"):
                content.append({"type": "text", "text": f"Scene description:\n{ctx['scene_description']}"})
            content.append({
                "type": "text",
                "text": (
                    "No images have been generated yet. Analyze this prompt and predict what Aurora failures "
                    "it is most likely to trigger. Apply the same spatial analysis as if you had seen a failed output: "
                    "identify absent or imprecise spatial descriptions, predict the most probable failure mode, "
                    "and provide a corrected prompt using the standard output format."
                ),
            })
            if user_display and user_display != "Review these":
                content.append({"type": "text", "text": f"User feedback:\n{user_display}"})
            messages.append({"role": "user", "content": content})

            try:
                for token in client.stream_chat_completions(messages):
                    partial += token
                    yield [user_msg, {"role": "assistant", "content": partial}], []
            except Exception as e:
                error = str(e)
        else:
            try:
                for token in client.stream_review_images(
                    failed_images=images_to_review,
                    original_prompt=self.current_prompt,
                    scene_description=ctx.get("scene_description", ""),
                    reference_image=ctx.get("reference_image", ""),
                    skill_content=self.get_review_skill(),
                    additional_images=ctx.get("additional_images"),
                    user_comment=user_display,
                    review_mode=ctx.get("review_mode", "phase1"),
                ):
                    partial += token
                    yield [user_msg, {"role": "assistant", "content": partial}], images_to_review
            except Exception as e:
                error = str(e)

        if error:
            err_content = (partial + f"\n\n❌ Error: {error}") if partial else f"❌ Error: {error}"
            yield [user_msg, {"role": "assistant", "content": err_content}], []
        elif partial:
            self.review_history = [user_msg, {"role": "assistant", "content": partial}]
            ps.save_project_state()

    _PRE_STYLE = (
        "white-space:pre-wrap;word-break:break-word;overflow-wrap:break-word;"
        "overflow:auto;background:var(--code-background-fill);"
        "padding:var(--spacing-xxl);border-radius:var(--radius-sm);"
        "font-family:var(--font-mono);font-size:var(--text-sm);display:block;margin:.5em 0;"
    )

    def _inject_extract_buttons(self, content: str) -> str:
        """Replace each prompt code block with a styled <pre> and an extract button."""
        if "```" not in content:
            return content

        def _replace(m: re.Match) -> str:
            raw = m.group(0)
            cleaned = GrokClient._clean_prompt_text(raw)
            if not cleaned:
                return raw
            body = _html.escape(cleaned)
            attr = _html.escape(cleaned, quote=True)
            panel = self.panel_id
            return (
                f'<pre style="{self._PRE_STYLE}">{body}</pre>'
                + f'\n<button class="psk-extract-btn" data-panel="{panel}"'
                + f' data-prompt="{attr}">↗ Use this prompt</button>'
            )

        return re.sub(r"```.*?```", _replace, content, flags=re.DOTALL)

    def _on_message_select(self, evt: gr.SelectData) -> Tuple[Any, Any]:
        content = evt.value if isinstance(evt.value, str) else ""
        if "psk-extract-btn" not in content:
            return gr.update(), gr.update()
        m = re.search(r'data-prompt="([^"]*)"', content)
        if not m:
            return gr.update(), gr.update()
        prompt = _html.unescape(m.group(1))
        if prompt:
            return prompt, gr.update(selected=f"{self.panel_id}_gen_images")
        return gr.update(), gr.update()

    # ── persistence ───────────────────────────────────────────────────────

    def serialize(self, project_dir: "Path") -> dict:
        """
        Return a JSON-serializable state dict for this panel.
        Override in subclasses that own files — copy those files into
        project_dir and store the stable paths in the returned dict.
        The base implementation just captures in-memory state.
        """
        return {
            "current_prompt": self.current_prompt,
            "generated_images": self.generated_images,
            "iteration_count": self.iteration_count,
            "work_item": self.work_item,
            "review_history": self.review_history,
            "review_galleries": self.review_galleries,
            "review_context": self.review_context,
            "cost_log": self.cost_log,
            "image_model": self.image_model,
            "image_resolution": self.image_resolution,
            "aspect_ratio": self.aspect_ratio,
        }

    def deserialize(self, d: dict) -> None:
        """Restore panel state from a previously serialized dict."""
        self.current_prompt = d.get("current_prompt", "")
        self.generated_images = d.get("generated_images", [])
        self.iteration_count = d.get("iteration_count", 0)
        self.work_item = d.get("work_item", 1)
        self.cost_log = d.get("cost_log", [])
        self.image_model = d.get("image_model", self.default_image_model)
        self.image_resolution = d.get("image_resolution", self.default_image_resolution)
        self.aspect_ratio = d.get("aspect_ratio", self.default_aspect_ratio)
        self.review_history = d.get("review_history", [])
        self.review_galleries = d.get("review_galleries", [])
        # Always reset review_context on load — its failed_images may be stale.
        # The first send_message call will invoke start_review, which rebuilds
        # context from self.generated_images (permanent paths, always current).
        self.review_context = {}
        # Rebuild _ui_history with gallery bubbles for messages that had them.
        # review_galleries[i] holds the image paths shown with review_history[i].
        self._ui_history = []
        for i, m in enumerate(self.review_history):
            if m.get("role") == "assistant" and m.get("content"):
                self._ui_history.append({**m, "content": self._inject_extract_buttons(m["content"])})
            else:
                self._ui_history.append(m)
            if m.get("role") == "user":
                gallery_paths = self.review_galleries[i] if i < len(self.review_galleries) else []
                if gallery_paths:
                    gallery_html = render_gallery_html(gallery_paths)
                    if gallery_html:
                        self._ui_history.append({
                            "role": "user",
                            "content": ComponentMessage(
                                component="html",
                                value=gallery_html,
                                constructor_args={},
                                props={},
                            ),
                        })

    def _build_display_user_msgs(self, text: str, images: List[str]) -> List[dict]:
        """User turn messages: one text bubble, then one HTML gallery bubble if images."""
        msgs: List[dict] = [{"role": "user", "content": text}]
        gallery_html = render_gallery_html(images)
        if gallery_html:
            # ComponentMessage is returned as-is by _postprocess_content (first isinstance
            # branch) — it is never mutated between yields, unlike gr.HTML whose
            # constructor_args dict is modified in-place (value popped on first yield).
            msgs.append({
                "role": "user",
                "content": ComponentMessage(
                    component="html",
                    value=gallery_html,
                    constructor_args={},
                    props={},
                ),
            })
        return msgs

    # ── UI render ─────────────────────────────────────────────────────────

    def _render_review_tab_content(self) -> None:
        """Render the review tab UI components. Shared by all panels."""
        with gr.Row():
            self._failed_upload = gr.File(
                label="Upload specific images to review (leave empty to use generated images)",
                file_count="multiple",
                type="filepath",
            )
        self.review_chatbot = gr.Chatbot(
            label="Review Conversation",
            height=500,
            show_label=False,
            bubble_full_width=False,
            type="messages",
            sanitize_html=False,
            elem_classes=["psk-review-chatbot"],
        )
        with gr.Row(equal_height=True):
            self.review_input = gr.Textbox(
                placeholder="Describe issues or say 'review these images'. Shift+Enter for new line.",
                lines=1,
                max_lines=4,
                scale=10,
                show_label=False,
                container=False,
            )
            self._send_btn = gr.Button("Send", variant="primary", scale=0, min_width=60)
        self.failed_gallery = gr.HTML()
        self._gallery_state = gr.State(value="")
        self._chatbot_state = gr.State(value=[])

    def _get_extract_outputs(self) -> List:
        """Components updated by the Extract button. Override to redirect to a different target."""
        return [self.prompt_box, self.panel_tabs]

    def render(self) -> None:
        """Build the inner three-tab UI within the current Gradio Blocks context."""
        with gr.Tabs(elem_id=f"{self.panel_id}_tabs") as self.panel_tabs:
            with gr.Tab("📝 Generate Prompt", id=f"{self.panel_id}_gen_prompt"):
                self.render_prompt_tab_content()
                self._gen_prompt_btn = gr.Button("🎯 Generate Prompt", variant="primary")

            with gr.Tab("🖼️ Generate Images", id=f"{self.panel_id}_gen_images"):
                self.prompt_box = gr.Textbox(
                    label="Prompt (edit if needed)",
                    lines=10,
                    max_lines=10,
                    placeholder="Generated prompt will appear here...",
                )
                self.render_images_tab_extra_controls()
                with gr.Row():
                    self._num_images_slider = gr.Slider(
                        minimum=1, maximum=10, value=2, step=1, label="Number of Images"
                    )
                    self._aspect_ratio_dropdown = gr.Dropdown(
                        choices=["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
                        value=self.aspect_ratio,
                        label="Aspect Ratio",
                    )
                self._gen_images_btn = gr.Button("🖼️ Generate Images", variant="primary")
                with gr.Row(visible=False) as self._dup_confirm_row:
                    gr.Markdown("⚠️ Same prompt as last generation.")
                    self._gen_anyway_btn = gr.Button("Generate anyway", variant="secondary", size="sm")
                    self._dup_cancel_btn = gr.Button("Cancel", size="sm")
                self._work_item_label = gr.Markdown(value=self._work_item_status())
                self.output_gallery = gr.HTML(min_height=150)

            with gr.Tab("🔍 Review & Correct", id=f"{self.panel_id}_review"):
                self._render_review_tab_content()

        self._wire_events()

    def _wire_events(self) -> None:
        """Wire all Gradio events. Subclasses call super()._wire_events() then add their own."""

        def _on_model_change(model):
            self.image_model = model
            self.app.project_state.save_project_state()
            is_aurora = model == "grok-imagine-image-2.0"
            return gr.update(interactive=is_aurora, value=self.image_resolution if is_aurora else "auto")

        def _on_resolution_change(resolution):
            self.image_resolution = resolution
            self.app.project_state.save_project_state()

        def _on_aspect_change(aspect):
            self.aspect_ratio = aspect
            self.app.project_state.save_project_state()

        self.image_model_dropdown.change(
            fn=_on_model_change,
            inputs=[self.image_model_dropdown],
            outputs=[self.image_resolution_dropdown],
            show_progress="hidden",
        )
        self.image_resolution_dropdown.change(fn=_on_resolution_change, inputs=[self.image_resolution_dropdown], show_progress="hidden")
        self._aspect_ratio_dropdown.change(fn=_on_aspect_change, inputs=[self._aspect_ratio_dropdown], show_progress="hidden")

        self._gen_prompt_btn.click(
            fn=lambda: gr.update(interactive=False, value="⏳ Generating prompt..."),
            outputs=[self._gen_prompt_btn],
            show_progress="minimal",
        ).then(
            fn=self.do_generate_prompt,
            inputs=self.get_prompt_tab_inputs(),
            outputs=[self.prompt_box, self.panel_tabs, self._gen_prompt_btn],
            show_progress="minimal",
        ).then(
            fn=lambda: gr.update(value=[]),
            outputs=[self.review_chatbot],
            show_progress="hidden",
        )

        _gen_inputs = [self.prompt_box, self._num_images_slider, self._aspect_ratio_dropdown]
        _gen_outputs = [self.output_gallery, self.failed_gallery, self._dup_confirm_row, self._gen_images_btn, self._gen_anyway_btn]

        self._gen_images_btn.click(
            fn=self._generate_images_for_ui,
            inputs=_gen_inputs,
            outputs=_gen_outputs,
            show_progress="minimal",
        ).then(
            fn=lambda: gr.update(value=self._work_item_status()),
            outputs=[self._work_item_label],
            show_progress="hidden",
        )
        self._gen_anyway_btn.click(
            fn=self._force_generate_images_for_ui,
            inputs=_gen_inputs,
            outputs=_gen_outputs,
            show_progress="minimal",
        ).then(
            fn=lambda: gr.update(value=self._work_item_status()),
            outputs=[self._work_item_label],
            show_progress="hidden",
        )
        self._dup_cancel_btn.click(
            fn=lambda: gr.update(visible=False),
            outputs=[self._dup_confirm_row],
            show_progress="hidden",
        )

        self.review_chatbot.select(
            fn=self._on_message_select,
            outputs=self._get_extract_outputs(),
            show_progress="hidden",
        )

        self._wire_review_events()

    def _wire_review_events(self) -> None:
        """Wire the send/submit 3-step chain. Called from _wire_events() and subclass overrides."""

        def _send_start(msg):
            prior_history = list(self._ui_history)
            # Only show the buffer on a fresh start; follow-up messages carry no buffer.
            prior_gallery = render_gallery_html(self.generated_images or []) if not self.review_history else ""
            pending = prior_history + [{"role": "user", "content": msg}]
            return pending, gr.update(interactive=False), prior_gallery, gr.update(interactive=False)

        def _send_execute(msg, uploaded):
            msg = (msg or "").strip() or "Review these"
            prior_ui_history = list(self._ui_history)
            prior_api_history = list(self.review_history)
            prior_galleries = list(self.review_galleries)
            # Old saves lack review_galleries entirely — pad so indices align with
            # prior_api_history before we extend with the new turn.
            while len(prior_galleries) < len(prior_api_history):
                prior_galleries.append([])
            prior_gallery = render_gallery_html(self.generated_images or [])

            # Thumbnails appear below every user message.
            # Fresh start: bundle generated images + any uploads.
            # Follow-up (continue): only explicitly uploaded files — generated images
            # are already in the review context; re-attaching them every turn would
            # mislead the user into thinking new images are being sent.
            uploaded_clean = [f for f in (uploaded or []) if f is not None]
            display_images = (list(self.generated_images or []) + uploaded_clean) if not prior_api_history else uploaded_clean

            # Build display messages: one text bubble + one image bubble per image.
            display_user_msgs = self._build_display_user_msgs(msg, display_images)

            # Gradio clears generator outputs before the first yield.
            # Re-emit immediately with the image-enhanced user messages.
            # NOTE: review_input is NOT in outputs — it stays out so the show_progress_on
            # loading overlay persists for the full duration (first yield would clear it).
            yield prior_ui_history + display_user_msgs, prior_gallery

            # After a session restart, review_context is cleared but review_history
            # is restored from disk. Rebuild context silently so we can continue
            # the existing conversation without wiping history.
            if self.review_history and not self.review_context:
                images = list(self.generated_images or [])
                if not images:
                    err = "❌ No images available — regenerate images to continue review."
                    yield prior_ui_history + display_user_msgs + [
                        {"role": "assistant", "content": err},
                    ], prior_gallery
                    return
                ctx = self.build_review_context(images)
                ctx["user_initial_comment"] = ""
                self.review_context = ctx

            if not self.review_history:
                # Fresh start — show thinking placeholder before API call starts
                yield prior_ui_history + display_user_msgs + [{"role": "assistant", "content": "..."}], prior_gallery
                had_yield = False
                for partial_history, images in self.stream_start_review(msg, uploaded):
                    had_yield = True
                    # Replace the text-only user msg from stream_start_review with the
                    # display version that includes image thumbnails.
                    display_partial = display_user_msgs + partial_history[1:]
                    yield display_partial, render_gallery_html(images) if images else prior_gallery
                if not had_yield:
                    err = "❌ Could not start review. Re-generate images first."
                    yield prior_ui_history + display_user_msgs + [{"role": "assistant", "content": err}], prior_gallery
                elif self.review_history:
                    # Sync _ui_history: display user msgs + assistant reply with buttons.
                    tail = [
                        {**m, "content": self._inject_extract_buttons(m["content"])}
                        if m.get("role") == "assistant" and m.get("content")
                        else m
                        for m in self.review_history[1:]
                    ]
                    self._ui_history = display_user_msgs + tail
                    self.review_galleries = [display_images, []]
                    self.app.project_state.save_project_state()
                    # Final yield: push the button-injected history to the chatbot.
                    # Empty gallery clears the review buffer now that images are in the chat.
                    yield self._ui_history, ""
            else:
                # Continue — stream chat completions token by token
                client = self.app.client
                if not client:
                    err = "❌ Client not initialized."
                    yield prior_ui_history + display_user_msgs + [{"role": "assistant", "content": err}], prior_gallery
                    return

                messages = self._build_continue_review_messages(msg)
                gallery_html = render_gallery_html(self.review_context.get("failed_images", []))
                partial = ""
                error = None

                # Show thinking placeholder before API call starts
                yield prior_ui_history + display_user_msgs + [{"role": "assistant", "content": "..."}], gallery_html

                try:
                    for token in client.stream_chat_completions(messages):
                        partial += token
                        yield prior_ui_history + display_user_msgs + [
                            {"role": "assistant", "content": partial},
                        ], gallery_html
                except Exception as e:
                    error = str(e)

                if error:
                    err_content = (partial + f"\n\n❌ Error: {error}") if partial else f"❌ Error: {error}"
                    yield prior_ui_history + display_user_msgs + [{"role": "assistant", "content": err_content}], gallery_html
                elif not partial:
                    yield prior_ui_history + display_user_msgs + [{"role": "assistant", "content": "❌ No response received."}], gallery_html
                else:
                    display_content = self._inject_extract_buttons(partial)
                    final_ui = prior_ui_history + display_user_msgs + [{"role": "assistant", "content": display_content}]
                    self._ui_history = final_ui
                    self.review_history = prior_api_history + [
                        {"role": "user", "content": msg},
                        {"role": "assistant", "content": partial},
                    ]
                    self.review_galleries = prior_galleries + [display_images, []]
                    self.app.project_state.save_project_state()
                    # Empty gallery clears the review buffer now that images are in the chat.
                    yield final_ui, ""

        def _flush_gallery(gallery):
            return gallery

        def _send_finish():
            return gr.update(value="", interactive=True), gr.update(interactive=True), gr.update(value=None)

        # show_progress="full" + show_progress_on=review_input targets the native Gradio
        # loading overlay to the input box only, leaving the chatbot unaffected.
        # review_input is intentionally NOT in outputs: when a component is in outputs
        # and receives its first yield (even gr.update()), Gradio clears its loading
        # state. Keeping it out means the overlay persists for the full streaming
        # duration and is only removed when the generator completes. See ISSUE-23.
        _send_event_kwargs = dict(
            inputs=[self.review_input, self._failed_upload],
            outputs=[self.review_chatbot, self._gallery_state],
            show_progress="full",
            show_progress_on=self.review_input,
        )
        _flush_event_kwargs = dict(
            fn=_flush_gallery,
            inputs=[self._gallery_state],
            outputs=[self.failed_gallery],
            show_progress="hidden",
        )
        _finish_event_kwargs = dict(
            fn=_send_finish,
            outputs=[self.review_input, self._send_btn, self._failed_upload],
            show_progress="hidden",
        )

        _send_start_kwargs = dict(
            inputs=[self.review_input],
            outputs=[self.review_chatbot, self.review_input, self.failed_gallery, self._send_btn],
            show_progress="hidden",
        )
        self._send_btn.click(fn=_send_start, **_send_start_kwargs).then(fn=_send_execute, **_send_event_kwargs).then(**_flush_event_kwargs).then(**_finish_event_kwargs)
        self.review_input.submit(fn=_send_start, **_send_start_kwargs).then(fn=_send_execute, **_send_event_kwargs).then(**_flush_event_kwargs).then(**_finish_event_kwargs)
