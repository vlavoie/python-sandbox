"""ReviewMixin: review conversation logic and UI for WorkflowPanel."""

import html as _html
import httpx
import re
from typing import Any, List, Tuple

import gradio as gr
from gradio.components.chatbot import ComponentMessage

from .gallery_widget import render_gallery_html
from .grok_client import GrokClient


class ReviewMixin:
    """Review conversation, streaming, UI rendering, and event wiring for WorkflowPanel."""

    _PRE_STYLE = (
        "white-space:pre-wrap;word-break:break-word;overflow-wrap:break-word;"
        "overflow:auto;background:var(--code-background-fill);"
        "padding:var(--spacing-xxl);border-radius:var(--radius-sm);"
        "font-family:var(--font-mono);font-size:var(--text-sm);display:block;margin:.5em 0;"
    )

    def _rebuild_ui_history(self, review_history: List, review_galleries: List) -> List:
        """Reconstruct _ui_history from persisted review_history + review_galleries."""
        ui_history = []
        for i, m in enumerate(review_history):
            if m.get("role") == "assistant" and m.get("content"):
                ui_history.append({**m, "content": self._inject_extract_buttons(m["content"])})
            else:
                ui_history.append(m)
            if m.get("role") == "user":
                gallery_paths = review_galleries[i] if i < len(review_galleries) else []
                if gallery_paths:
                    gallery_html = render_gallery_html(gallery_paths)
                    if gallery_html:
                        ui_history.append({
                            "role": "user",
                            "content": ComponentMessage(
                                component="html",
                                value=gallery_html,
                                constructor_args={},
                                props={},
                            ),
                        })
        return ui_history

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
