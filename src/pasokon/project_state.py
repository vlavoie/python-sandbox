"""App-level project state and persistence for FPV POV app."""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image


def _normalize_chat_history(history: list) -> list:
    """Convert old tuple/list pairs to the messages-dict format Gradio 5 expects."""
    normalized = []
    for msg in history:
        if isinstance(msg, dict):
            normalized.append(msg)
        elif isinstance(msg, (list, tuple)) and len(msg) == 2:
            user_msg, assistant_msg = msg
            if user_msg:
                normalized.append({"role": "user", "content": str(user_msg)})
            if assistant_msg:
                normalized.append({"role": "assistant", "content": str(assistant_msg)})
    return normalized


class ProjectState:
    """
    Holds app-level state: project identity, model preferences, skills, and
    project persistence (save/load/list).

    Per-panel state (prompts, images, review history, etc.) lives in each
    WorkflowPanel subclass.  Panels register themselves via register_panel()
    so save/load can reach them.
    """

    def __init__(self):
        self.project_name = "untitled-project"

        self.output_dir = Path(__file__).parent.parent.parent / "fpv-pov-outputs"
        self.output_dir.mkdir(exist_ok=True)

        # Skill files
        self.skill_dir = Path(__file__).parent.parent.parent
        try:
            with open(self.skill_dir / "fpv-pov-image.md", "r", encoding="utf-8", errors="replace") as f:
                self.prompt_skill = f.read()
            with open(self.skill_dir / "fpv-pov-review.md", "r", encoding="utf-8", errors="replace") as f:
                self.review_skill = f.read()
            with open(self.skill_dir / "fpv-pov-element.md", "r", encoding="utf-8", errors="replace") as f:
                self.element_skill = f.read()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Skill files not found. Ensure fpv-pov-image.md, fpv-pov-review.md, and "
                f"fpv-pov-element.md are in: {self.skill_dir}"
            ) from e

        # App-level model preferences (persisted per project)
        self.chat_model = "grok-4.20"
        self.image_model = "grok-imagine-image-pro"
        self.image_resolution: str = "auto"

        # Registered workflow panels: name → panel instance
        self._panels: Dict = {}

    def register_panel(self, name: str, panel) -> None:
        self._panels[name] = panel

    # ── display ───────────────────────────────────────────────────────────

    def _get_project_display_string(self) -> str:
        return f"**📁 Current Project:** `{self.project_name}` | 💾 Auto-saves after each action"

    # ── file utilities ────────────────────────────────────────────────────

    def save_uploaded_file(self, file) -> Optional[str]:
        """Copy an uploaded file to a temporary location and return the path."""
        if file is None:
            return None
        try:
            source_path = file if isinstance(file, str) else file.name
            suffix = Path(source_path).suffix.lower() or ".jpg"
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temp_path = tf.name
            tf.close()

            if suffix == ".png":
                shutil.copy(source_path, temp_path)
            elif suffix in (".jpg", ".jpeg"):
                img = Image.open(source_path)
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(temp_path, "JPEG", quality=95, optimize=True)
            else:
                shutil.copy(source_path, temp_path)
            return temp_path

        except Exception as e:
            print(f"Warning: Could not save uploaded file: {e}")
            source = file if isinstance(file, str) else file.name
            suffix = Path(source).suffix or ".jpg"
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            shutil.copy(source, tf.name)
            tf.close()
            return tf.name

    def _copy_image_to_project(
        self, image_path: str, image_type: str, project_dir: Path = None
    ) -> Optional[str]:
        """Copy an image into <project_dir>/references/. Returns the new path."""
        if not image_path or not Path(image_path).exists():
            return image_path
        try:
            refs_dir = (project_dir or (self.output_dir / self.project_name)) / "references"
            refs_dir.mkdir(parents=True, exist_ok=True)
            suffix = Path(image_path).suffix.lower() or ".jpg"
            dest = refs_dir / f"{image_type}{suffix}"

            if suffix == ".png":
                shutil.copy(image_path, dest)
            elif suffix in (".jpg", ".jpeg"):
                img = Image.open(image_path)
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(dest, "JPEG", quality=95, optimize=True)
            else:
                shutil.copy(image_path, dest)
            return str(dest)
        except Exception as e:
            print(f"Warning: Could not copy {image_type} to project: {e}")
            return image_path

    def _get_project_metadata_path(self, project_name: str = None) -> Path:
        return self.output_dir / (project_name or self.project_name) / ".project_metadata.json"

    # ── save / load ───────────────────────────────────────────────────────

    def save_project_state(self) -> str:
        """Save app-level state and all registered panel states to disk."""
        try:
            project_dir = self.output_dir / self.project_name
            project_dir.mkdir(parents=True, exist_ok=True)

            panels_state = {}
            for name, panel in self._panels.items():
                panels_state[name] = panel.serialize(project_dir)

            state: dict = {
                "project_name": self.project_name,
                "chat_model": self.chat_model,
                "image_model": self.image_model,
                "image_resolution": self.image_resolution,
                "last_saved": datetime.now().isoformat(),
                "panels": panels_state,
            }

            with open(self._get_project_metadata_path(), "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

            (self.output_dir / ".last_project.txt").write_text(self.project_name)

            fpv_state = panels_state.get("fpv", {})
            total_refs = sum([
                1 if fpv_state.get("reference_image_path") else 0,
                len(fpv_state.get("additional_images_paths", [])),
                1 if fpv_state.get("greenzone_image_path") else 0,
            ])
            return f"✅ Project '{self.project_name}' saved ({total_refs} reference image(s) backed up)"

        except Exception as e:
            return f"⚠️ Could not save project: {str(e)}"

    def load_project_state(self, project_name: str = None) -> Tuple[str, str]:
        """
        Load project state from disk. Restores app-level fields and all registered panels.
        Returns (status_msg, project_display_str).
        """
        try:
            if not project_name:
                last = self.output_dir / ".last_project.txt"
                if last.exists():
                    project_name = last.read_text().strip()
                else:
                    return "ℹ️ No saved project found", self._get_project_display_string()

            metadata_path = self._get_project_metadata_path(project_name)
            if not metadata_path.exists():
                # No state file — switch to this project name with a blank slate
                self.project_name = project_name
                self._clear_all_panels()
                (self.output_dir / project_name).mkdir(parents=True, exist_ok=True)
                return (
                    f"ℹ️ No saved state for '{project_name}' — starting fresh",
                    self._get_project_display_string(),
                )

            # State file confirmed to exist — safe to clear and reload
            self._clear_all_panels()

            with open(metadata_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            self.project_name = state.get("project_name", "untitled-project")
            self.chat_model = state.get("chat_model", "grok-4.20")
            self.image_model = state.get("image_model", "grok-imagine-image-pro")
            self.image_resolution = state.get("image_resolution", "auto")

            # New format: state["panels"]["fpv"] / state["panels"]["element"]
            # Legacy format: FPV state is flat at the top level (no "panels" key)
            panels_state = state.get("panels")
            for name, panel in self._panels.items():
                if panels_state is not None:
                    panel_dict = panels_state.get(name, {})
                elif name == "fpv":
                    # Legacy flat format — FPV state lives at the top level
                    panel_dict = dict(state)
                    panel_dict["review_history"] = _normalize_chat_history(
                        state.get("phase1_review_history", [])
                    )
                    panel_dict["review_context"] = state.get("phase1_review_context", {})
                else:
                    panel_dict = {}
                panel.deserialize(panel_dict)

            last_saved = state.get("last_saved", "unknown")
            fpv_panel = self._panels.get("fpv")
            ref_ok = fpv_panel and fpv_panel.reference_image_path and Path(fpv_panel.reference_image_path).exists()
            add_count = len([p for p in (fpv_panel.additional_images_paths if fpv_panel else []) if Path(p).exists()])
            gz_ok = fpv_panel and fpv_panel.greenzone_image_path and Path(fpv_panel.greenzone_image_path).exists()

            status = (
                f"✅ Loaded project '{self.project_name}'\n\n"
                f"📅 Last saved: {last_saved}\n"
                f"🎯 Mode: {fpv_panel.review_mode if fpv_panel else 'N/A'}\n"
                f"📝 Prompt: {'Set' if fpv_panel and fpv_panel.current_prompt else 'Not set'}\n"
                f"🖼️ Character reference: {'✅ Available' if ref_ok else '❌ Missing'}\n"
                f"➕ Additional images: {add_count}\n"
                f"📸 Generated images: {len(fpv_panel.generated_images) if fpv_panel else 0}\n"
                f"🔄 Iterations: {fpv_panel.iteration_count if fpv_panel else 0}\n"
                f"💬 Review history: {len(fpv_panel.review_history) if fpv_panel else 0} message(s)\n"
                f"🌿 Phase 2 greenzone: {'✅ Configured' if gz_ok else 'Not set'}"
            )
            return status, self._get_project_display_string()

        except Exception as e:
            return f"❌ Error loading project: {str(e)}", self._get_project_display_string()

    def set_project_name(self, project_name: str) -> Tuple[str, str]:
        """
        Set the active project name. Clears panels if this is a new project.
        Returns (status_msg, project_display_str).
        """
        if not project_name or not project_name.strip():
            return "❌ Project name cannot be empty", self._get_project_display_string()

        sanitized = (
            "".join(c if c.isalnum() or c in ("-", "_", " ") else "_" for c in project_name)
            .strip()
            .replace(" ", "-")
            .lower()
        )

        if sanitized != self.project_name:
            is_new = not self._get_project_metadata_path(sanitized).exists()
            if is_new:
                self._clear_all_panels()
            self.project_name = sanitized
            suffix = " (New project — state cleared)" if is_new else ""
            return f"✅ Project set to: {sanitized}{suffix}", self._get_project_display_string()

        return f"📁 Project: {sanitized}", self._get_project_display_string()

    # ── helpers ───────────────────────────────────────────────────────────

    def _clear_all_panels(self) -> None:
        for panel in self._panels.values():
            panel.deserialize({})

    def list_projects(self) -> List[str]:
        try:
            if not self.output_dir.exists():
                return []
            projects = []
            for item in self.output_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    meta = item / ".project_metadata.json"
                    if meta.exists():
                        try:
                            s = json.loads(meta.read_text())
                            projects.append((item.name, s.get("last_saved", "")))
                        except Exception:
                            projects.append((item.name, ""))
                    else:
                        projects.append((item.name, ""))
            projects.sort(key=lambda x: x[1], reverse=True)
            return [name for name, _ in projects]
        except Exception as e:
            print(f"Error listing projects: {e}")
            return []
