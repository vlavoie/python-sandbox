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
The image assignments below are FIXED for this session. Any conflicting convention in the skill must be IGNORED.

- <IMAGE_0> = CHARACTER REFERENCE — lock all style, appearance, hair color and identity to this image
- <IMAGE_1> = GREEN-MARKED BASE IMAGE — the spatial base to modify surgically

AURORA MODEL CONSTRAINT — applies to all corrected prompts you write:
Aurora ignores negative language entirely ("not", "no", "never", "forbidden", "do not"). Every correction must be written as a positive spatial description of what should appear and where — not as a ban of what failed. Stronger bans never fix failures. The correct fix is always a more precise spatial description placed earlier in the prompt.

When reviewing failed images, check in this order:
1. Was IMAGE_1 preserved exactly outside the green zones? (Primary failure if not — base was regenerated instead of surgically modified)
2. Were elements added only inside the green zones?
3. Was all paint erased?
4. Does the addition style match IMAGE_0?

When writing a corrected prompt, use the Phase 2 structure from the skill:
- Open with: "Starting from IMAGE_1 as the unchanged spatial and compositional base, [what appears in the green zones]."
- Describe the addition spatially: frame position, color/texture matching IMAGE_0.
- State once: "Everything outside the green-marked zones remains identical to IMAGE_1. Green paint fully removed."
- No ban lists. No repetition. Aim for 60–100 words.

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
- <IMAGE_1> is the green-zoned base image — the canvas to modify surgically
- ONLY add elements inside the green/pink zones on <IMAGE_1>
- Everything OUTSIDE the green zones in <IMAGE_1> must remain completely unchanged (background, body, scene composition)
- Erase all green/pink paint afterward so no trace remains
- Lock style and appearance to <IMAGE_0>

A primary failure mode is when the model regenerates the entire image instead of making a surgical local addition — watch for this in the failed images."""
                mode_label = "Phase 2 Enhancement"
            else:
                reference_image = self.reference_image_path
                additional_images = self.additional_images_paths if self.additional_images_paths else None
                scene_description = self.current_scene
                mode_label = "Phase 1"

            user_display_msg = user_comment.strip() if user_comment.strip() else "Review these"

            self.phase1_review_context = {
                "failed_images": images_to_review,
                "original_prompt": self.current_prompt,
                "scene_description": scene_description,
                "reference_image": reference_image,
                "additional_images": additional_images,
                "review_mode": self.review_mode,
                "user_initial_comment": user_display_msg,
            }

            initial_review = self.client.review_images(
                failed_images=images_to_review,
                original_prompt=self.current_prompt,
                scene_description=scene_description,
                reference_image=reference_image,
                skill_content=self._get_review_skill(),
                additional_images=additional_images,
                user_comment=user_display_msg,
                review_mode=self.review_mode,
            )

            self.phase1_review_history = [
                {"role": "user", "content": user_display_msg},
                {"role": "assistant", "content": initial_review},
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

                ref = self.phase1_review_context.get("reference_image")
                if ref:
                    content.append({"type": "text", "text": "Character reference (IMAGE_0):"})
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{self.client._encode_image(ref)}"}
                    })

                for idx, img_path in enumerate(self.phase1_review_context.get("additional_images") or [], 1):
                    if review_mode == "phase2" and idx == 1:
                        label = "Green-zoned base image (IMAGE_1) — surgical base; preserve everything outside the marked zones exactly:"
                    else:
                        label = f"Additional reference (IMAGE_{idx}):"
                    content.append({"type": "text", "text": label})
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{self.client._encode_image(img_path)}"}
                    })

                for i, img_path in enumerate(self.phase1_review_context.get("failed_images", []), 1):
                    content.append({"type": "text", "text": f"Failed image {i}:"})
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{self.client._encode_image(img_path)}"}
                    })

                content.append({
                    "type": "text",
                    "text": f"Original prompt:\n```\n{self.phase1_review_context.get('original_prompt', '')}\n```"
                })
                content.append({
                    "type": "text",
                    "text": f"Scene description:\n{self.phase1_review_context.get('scene_description', '')}"
                })

                initial_comment = self.phase1_review_context.get("user_initial_comment", "")
                if initial_comment:
                    content.append({"type": "text", "text": f"User's initial feedback:\n{initial_comment}"})

                messages.append({"role": "user", "content": content})

            # Skip the first user message from history — it is already embedded in the
            # rebuilt context above as "User's initial feedback".
            skip_first_user = True
            for msg in history:
                if skip_first_user and msg["role"] == "user":
                    skip_first_user = False
                    continue
                messages.append({"role": msg["role"], "content": msg["content"]})

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
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    try:
                        api_msg = e.response.json().get("error", {}).get("message", "")
                        if any(k in api_msg.lower() for k in ("content", "policy", "moderation", "safety")):
                            raise Exception("Warning: No response returned")
                    except Exception as inner:
                        if "Warning:" in str(inner):
                            raise
                    raise
                result = response.json()
                assistant_response = result["choices"][0]["message"]["content"]
                if not assistant_response:
                    raise Exception("Warning: No response returned")

            new_history = history + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response},
            ]
            self.phase1_review_history = new_history

            return new_history, ""

        except Exception as e:
            return history, f"❌ Error: {str(e)}"

    def extract_prompt_from_phase1_chat(self, history: List) -> Tuple[str, Any]:
        """Extract the final prompt from the Phase 1 review chat and send to generation tab."""
        if not history:
            return "", gr.update()

        for msg in reversed(history):
            if msg["role"] == "assistant" and msg["content"]:
                from pasokon.grok_client import GrokClient
                cleaned_prompt = GrokClient._clean_prompt_text(msg["content"])
                if cleaned_prompt:
                    return cleaned_prompt, gr.update(selected="tab_generate_images")

        return "", gr.update()
