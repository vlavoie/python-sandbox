"""Review handler for FPV POV app — manages interactive review conversations."""

import httpx
from pathlib import Path
from typing import List, Optional, Tuple, Any

import gradio as gr

from .project_state import ProjectState


class ReviewHandler(ProjectState):
    """Mixin that handles review conversation logic.

    Inherits ProjectState for all shared state (client, review_mode, etc.).
    FPVPOVApp should inherit from ReviewHandler instead of ProjectState directly.
    """

    def _get_review_skill(self) -> str:
        """Return review skill, prepending a Phase 2 override when in phase2 mode."""
        if self.review_mode != "phase2":
            return self.review_skill
        prefix = """PHASE 2 REVIEW MODE — IMAGE ASSIGNMENT OVERRIDE
The image assignments below are FIXED for this session. Any conflicting convention in the skill (e.g. "IMAGE_0 = green-marked base") must be IGNORED.

- <IMAGE_0> = CHARACTER REFERENCE — lock all style, appearance, hair color and identity to this image
- <IMAGE_1> = GREEN-MARKED BASE IMAGE — the spatial base with green/pink zones showing where elements must be added

When reviewing failed images:
- Check that elements were added only inside the green/pink zones on <IMAGE_1>
- Check that appearance/style is locked to <IMAGE_0>
- Check that all green/pink paint was completely erased
When writing a corrected prompt, always keep <IMAGE_0> = character reference and <IMAGE_1> = green-marked base. Do NOT swap them.

---

"""
        return prefix + self.review_skill

    def start_phase1_review(
        self,
        user_comment: str,
        manual_uploaded_images: Optional[List] = None
    ) -> Tuple[List, str, List]:
        """Start an interactive review conversation.

        Handles BOTH Phase 1 and Phase 2 reviews.
        review_mode determines image ordering:
        - phase1: IMAGE_0=character, IMAGE_1+=additional characters
        - phase2: IMAGE_0=character, IMAGE_1=greenzone base
        """
        if not self.client:
            return [], "❌ Please configure your API key first.", []

        images_to_review = []

        if manual_uploaded_images:
            for img in manual_uploaded_images:
                if img is not None:
                    path = self.save_uploaded_file(img)
                    if path:
                        images_to_review.append(path)
        elif self.generated_images:
            images_to_review = self.generated_images

        if not images_to_review:
            return [], "❌ No images to review. Please generate or upload images first.", []

        try:
            if self.review_mode == "phase2":
                reference_image = self.reference_image_path
                additional_images = [self.greenzone_image_path] if self.greenzone_image_path else []
                scene_description = f"""Phase 2 Enhancement Review:
{self.current_phase2_description}

Context:
- <IMAGE_0> is the character reference for style/appearance (SAME as Phase 1)
- <IMAGE_1> is the green-zoned base image marking where to add elements
- Only add inside green zones on <IMAGE_1>
- Erase all green paint afterward
- Lock style to <IMAGE_0>

Review the failed enhancement attempts."""
                mode_label = "Phase 2 Enhancement"
            else:
                reference_image = self.reference_image_path
                additional_images = self.additional_images_paths if self.additional_images_paths else None
                scene_description = self.current_scene
                mode_label = "Phase 1"

            self.phase1_review_context = {
                "failed_images": images_to_review,
                "original_prompt": self.current_prompt,
                "scene_description": scene_description,
                "reference_image": reference_image,
                "additional_images": additional_images,
                "review_mode": self.review_mode
            }

            image_ref_guide = "- <IMAGE_0> = Character reference (for style/appearance lock)"
            if self.review_mode == 'phase2':
                image_ref_guide += "\n- <IMAGE_1> = Green-zoned base (spatial guide for enhancements)"
            elif additional_images:
                image_ref_guide += f"\n- <IMAGE_1>+ = Additional characters ({len(additional_images)} provided)"
            image_ref_guide += "\n- Failed images = Analyzed by AI (refer to as 'failed image 1', 'failed image 2', etc.)"

            user_initial_msg = f"""[{mode_label} Review]

Here are the failed images to review:

{user_comment if user_comment.strip() else 'Please review these images and suggest corrections.'}

Image Reference Guide:
{image_ref_guide}

IMPORTANT: Always start your response with a brief 1-3 sentence explanation of what changes you're making to the prompt (what you're strengthening, what bans you're adding, etc.), then provide the corrected prompt in a code block."""

            initial_review = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=scene_description,
                reference_image=reference_image,
                skill_content=self._get_review_skill(),
                additional_images=additional_images
            )

            image_list = "\n".join([f"  • {Path(img).name}" for img in images_to_review])
            user_initial_msg_with_files = f"""{user_initial_msg}

Failed image files being reviewed:
{image_list}"""  # noqa: F841 — kept for potential future use

            user_display_msg = user_comment.strip() if user_comment.strip() else "Please review these images and suggest corrections."

            self.phase1_review_history = [
                (user_display_msg, initial_review)
            ]

            mode_specific_info = ""
            if self.review_mode == 'phase2':
                mode_specific_info = "\n🗂 <IMAGE_1> = Green-zoned base"
            elif additional_images:
                mode_specific_info = f"\n🗂 <IMAGE_1>+ = {len(additional_images)} additional character(s)"

            instructions = f"""✅ {mode_label} Review started!

🎯 Mode: {mode_label}
📸 {len(images_to_review)} failed image(s) being analyzed
🗂 <IMAGE_0> = Character reference (always){mode_specific_info}
💬 Refer to failed images as 'failed image 1', 'failed image 2', etc.
❓ Ask questions or request changes"""

            return self.phase1_review_history, instructions, images_to_review

        except Exception as e:
            return [], f"❌ Error during review: {str(e)}", []

    def continue_phase1_review(self, user_message: str, history: List) -> Tuple[List, str]:
        """Continue the Phase 1 review conversation."""
        if not self.client:
            return history, "❌ Client not initialized"

        if not user_message.strip():
            return history, ""

        try:
            review_mode = self.phase1_review_context.get("review_mode", self.review_mode)
            effective_review_skill = self._get_review_skill() if review_mode == "phase2" else self.review_skill
            messages = [{"role": "system", "content": effective_review_skill}]

            if self.phase1_review_context:
                content = []

                if self.phase1_review_context.get("reference_image"):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(self.phase1_review_context['reference_image'])}"
                        }
                    })

                for img_path in self.phase1_review_context.get("failed_images", []):
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{self.client._encode_image(img_path)}"
                        }
                    })

                content.append({
                    "type": "text",
                    "text": f"Original prompt: {self.phase1_review_context.get('original_prompt', '')}\n\nScene: {self.phase1_review_context.get('scene_description', '')}"
                })

                messages.append({"role": "user", "content": content})

            for idx, (user_msg, assistant_msg) in enumerate(history):
                if idx == 0:
                    if assistant_msg:
                        messages.append({"role": "assistant", "content": assistant_msg})
                else:
                    if user_msg:
                        messages.append({"role": "user", "content": user_msg})
                    if assistant_msg:
                        messages.append({"role": "assistant", "content": assistant_msg})

            messages.append({"role": "user", "content": user_message})

            with httpx.Client(timeout=120.0) as http_client:
                response = http_client.post(
                    f"{self.client.base_url}/chat/completions",
                    headers=self.client.headers,
                    json={
                        "model": self.client.chat_model,
                        "messages": messages
                    }
                )
                response.raise_for_status()
                result = response.json()
                assistant_response = result["choices"][0]["message"]["content"]

            new_history = history + [(user_message, assistant_response)]
            self.phase1_review_history = new_history

            return new_history, ""

        except Exception as e:
            return history, f"❌ Error: {str(e)}"

    def extract_prompt_from_phase1_chat(self) -> Tuple[str, Any]:
        """Extract the final prompt from the Phase 1 review chat and send to generation tab."""
        if not self.phase1_review_history:
            return "", gr.update()

        for user_msg, assistant_msg in reversed(self.phase1_review_history):
            if assistant_msg:
                from pasokon.grok_client import GrokClient
                cleaned_prompt = GrokClient._clean_prompt_text(assistant_msg)
                if cleaned_prompt:
                    return cleaned_prompt, gr.update(selected="tab_generate_images")

        return "", gr.update()
