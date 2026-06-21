from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class RenamePreview:
    item_id: int
    original_path: str
    target_name: str
    target_subpath: str
    item_type: str
    destination_root: str = ""
    action: str = "rename"
    extra_id: Optional[int] = None
    source_size: Optional[int] = None
    source_duration: Optional[float] = None
    source_resolution: Optional[str] = None
    source_video_bitrate: Optional[int] = None
    has_collision: bool = False
    collision_group_id: Optional[str] = None
    extra_previews: List["RenamePreview"] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def target_path(self) -> str:
        # standard path formatting with forward slashes
        subpath_part = self.target_subpath.strip("/")
        if subpath_part:
            return f"{self.destination_root.rstrip('/')}/{subpath_part}/{self.target_name}"
        return f"{self.destination_root.rstrip('/')}/{self.target_name}"

    @property
    def is_too_long(self) -> bool:
        return len(self.target_path) >= 260
