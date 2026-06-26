import os
from typing import Dict, List, Optional
from app.domains.library.models import Library, MediaItem, ExtraFile
from app.shared_kernel.ports.file_system_port import FileSystemPort

class DuplicateFinder:
    """
    Submodule to build and query hash lookups to detect moved, renamed, or duplicate items/extras.
    """
    def __init__(self, library: Library, fs: FileSystemPort):
        self.library = library
        self.fs = fs

    def build_media_hash_lookup(self, items: List[MediaItem]) -> Dict[str, List[MediaItem]]:
        hash_lookup = {}
        for item in items:
            if item.hash_md5:
                hash_lookup.setdefault(item.hash_md5, []).append(item)
        return hash_lookup

    def build_extra_hash_lookup(self, extras: List[ExtraFile]) -> Dict[str, List[ExtraFile]]:
        extra_hash_lookup = {}
        for ex in extras:
            if ex.file_hash:
                extra_hash_lookup.setdefault(ex.file_hash, []).append(ex)
        return extra_hash_lookup

    def find_moved_media_item(
        self,
        file_hash: Optional[str],
        hash_lookup: Dict[str, List[MediaItem]]
    ) -> Optional[MediaItem]:
        if not file_hash:
            return None
        candidates = hash_lookup.get(file_hash) or []
        for cand in candidates:
            cand_full_path = os.path.join(self.library.root_path, cand.relative_path)
            if not os.path.exists(self.fs.to_win_long_path(cand_full_path)):
                return cand
        return None

    def find_moved_extra(
        self,
        file_hash: Optional[str],
        extra_hash_lookup: Dict[str, List[ExtraFile]]
    ) -> Optional[ExtraFile]:
        if not file_hash:
            return None
        candidates = extra_hash_lookup.get(file_hash) or []
        for cand in candidates:
            cand_full_path = os.path.join(self.library.root_path, cand.relative_path)
            if not os.path.exists(self.fs.to_win_long_path(cand_full_path)):
                return cand
        return None
