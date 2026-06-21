from pathlib import Path
from typing import Callable, List, Dict, Optional
from .models import RenamePreview


class PathResolver:
    def __init__(self, config=None, replacement_decider: Optional[Callable[[RenamePreview], Optional[bool]]] = None):
        self.config = config
        self.replacement_decider = replacement_decider

    def _is_same_file_target(self, preview: RenamePreview) -> bool:
        try:
            return Path(preview.target_path).resolve() == Path(preview.original_path).resolve()
        except Exception:
            target = str(preview.target_path or "").replace("\\", "/").lower()
            original = str(preview.original_path or "").replace("\\", "/").lower()
            return target == original

    def check_path_lengths(self, preview: RenamePreview):
        if preview.is_too_long:
            preview.warnings.append(f"Path exceeds Windows limit ({len(preview.target_path)}/260 chars)")

        for ep in preview.extra_previews:
            self.check_path_lengths(ep)

    def resolve_collisions(self, previews: List[RenamePreview]) -> List[RenamePreview]:
        all_to_check: List[RenamePreview] = []
        for p in previews:
            all_to_check.append(p)
            all_to_check.extend(p.extra_previews)

        path_map: Dict[str, List[RenamePreview]] = {}
        for preview in all_to_check:
            if self._action(preview) in ["delete", "skip"]:
                continue
            if self._is_same_file_target(preview):
                preview.has_collision = False
                preview.collision_group_id = None
                continue
            path_map.setdefault(preview.target_path.lower(), []).append(preview)

        for full_path, items in path_map.items():
            if len(items) > 1:
                self._resolve_group(full_path, items)

        for preview in all_to_check:
            if self._action(preview) in ["delete", "skip"]:
                continue
            if self._is_same_file_target(preview):
                preview.has_collision = False
                preview.collision_group_id = None
                continue
            target = Path(preview.target_path)
            original = Path(preview.original_path)
            if target.exists() and target.resolve() != original.resolve():
                self._apply_external_collision(preview)

        return previews

    def _resolve_group(self, full_path: str, items: List[RenamePreview]):
        strategy = self._strategy()
        group_id = f"coll_{abs(hash(full_path))}"

        if strategy == "keep_both":
            for idx, item in enumerate(items):
                if idx > 0:
                    item.target_name = self._with_suffix(item.target_name, idx + 1)
            return

        if strategy == "skip":
            for item in items[1:]:
                item.action = "skip"
                item.has_collision = True
                item.collision_group_id = group_id
                item.warnings.append("Skipped because another item has the same target path.")
            return

        if strategy == "replace_if_better":
            winner = max(items, key=self._quality_score)
            for item in items:
                if item is winner:
                    item.action = "replace_if_better"
                else:
                    item.action = "skip"
                    item.has_collision = True
                    item.collision_group_id = group_id
                    item.warnings.append("Skipped because a better duplicate targets the same path.")
            return

        if strategy == "replace":
            items[0].action = "replace"
            for item in items[1:]:
                item.action = "skip"
                item.has_collision = True
                item.collision_group_id = group_id
                item.warnings.append("Skipped because another item will replace this target.")
            return

    def _apply_external_collision(self, preview: RenamePreview):
        strategy = self._strategy()
        preview.has_collision = True
        preview.collision_group_id = f"existing_{abs(hash(preview.target_path.lower()))}"

        if strategy == "keep_both":
            preview.target_name = self._next_available_name(preview)
            preview.has_collision = False
            preview.collision_group_id = None
            return

        if strategy == "skip":
            preview.action = "skip"
            preview.warnings.append("Skipped because the target file already exists.")
            return

        if strategy == "replace_if_better":
            replacement_decision = self._can_replace_existing(preview)
            if replacement_decision is True:
                preview.action = "replace_if_better"
                preview.has_collision = False
                preview.collision_group_id = None
                preview.warnings.append("Will replace the existing file because the new file is better.")
                return
            if replacement_decision is False:
                preview.action = "skip"
                preview.has_collision = False
                preview.collision_group_id = None
                preview.warnings.append("Skipped because the existing target file is not worse.")
                return

            preview.action = "replace_if_better"
            preview.warnings.append("Will replace the existing file only if the new file is better.")
            return

        if strategy == "replace":
            preview.action = "replace"
            preview.has_collision = False
            preview.collision_group_id = None
            preview.warnings.append("Will replace the existing target file.")

    def _next_available_name(self, preview: RenamePreview) -> str:
        original = preview.target_name
        idx = 2
        while True:
            candidate = self._with_suffix(original, idx)
            target_path = Path(preview.destination_root) / preview.target_subpath / candidate
            if not target_path.exists():
                return candidate
            idx += 1

    def _with_suffix(self, filename: str, idx: int) -> str:
        stem, dot, ext = filename.rpartition(".")
        if dot:
            return f"{stem} ({idx}).{ext}"
        return f"{filename} ({idx})"

    def _quality_score(self, preview: RenamePreview):
        return (
            self._resolution_height(preview.source_resolution),
            preview.source_video_bitrate or 0,
            preview.source_size or 0,
        )

    def _can_replace_existing(self, preview: RenamePreview):
        if self.replacement_decider is None:
            return None
        return self.replacement_decider(preview)

    def _resolution_height(self, resolution: str) -> int:
        if not resolution:
            return 0
        text = str(resolution).lower()
        if "x" in text:
            try:
                return int(text.split("x")[-1].strip().rstrip("p"))
            except ValueError:
                return 0
        if text.endswith("k"):
            try:
                return int(float(text[:-1]) * 1000)
            except ValueError:
                return 0
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else 0

    def _strategy(self) -> str:
        return getattr(self.config, "collision_strategy", "keep_both") or "keep_both"

    def _action(self, preview: RenamePreview) -> str:
        return str(getattr(preview, "action", "rename") or "rename").strip().lower()
