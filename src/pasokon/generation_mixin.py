"""GenerationMixin: image generation and persistence for WorkflowPanel."""

import io
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import gradio as gr
from PIL import Image

from .gallery_widget import render_gallery_html


class GenerationMixin:
    """Image generation and output persistence methods shared by all workflow panels."""

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
