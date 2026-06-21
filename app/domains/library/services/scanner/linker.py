from pathlib import Path
from typing import List, Dict, Optional

class Linker:
    """
    Submodule: Links extra files (subtitles, images, etc.) to their primary media files.
    Supports recursive parent lookup and sibling directory recognition.
    """

    def link(self, media_files: List[Path], extra_files: List[Path]) -> Dict[Path, Path]:
        """
        Establishes relationships between extras and media files.
        """
        links = {}
        
        # Index by folders for fast access
        folder_index = {}
        for m in media_files:
            folder = m.parent
            if folder not in folder_index:
                folder_index[folder] = []
            folder_index[folder].append(m)

        for extra in extra_files:
            # 1. Attempt standard recursive search upwards
            parent = self._find_parent_recursive(extra, folder_index)
            
            # 2. Fallback to "Sibling Directory" logic if no direct parent is found
            if not parent:
                parent = self._find_sibling_parent(extra, folder_index)
                
            if parent:
                links[extra] = parent

        return links

    def _find_parent_recursive(self, extra_path: Path, folder_index: Dict[Path, List[Path]]) -> Optional[Path]:
        """
        Searches up to 4 levels of parent directories to find a matching media file.
        """
        current_folder = extra_path.parent
        for _ in range(4):
            if current_folder in folder_index:
                parents = folder_index[current_folder]
                return self._match_by_name(extra_path, parents)
            if current_folder.parent == current_folder:
                break
            current_folder = current_folder.parent
        return None

    def _find_sibling_parent(self, extra_path: Path, folder_index: Dict[Path, List[Path]]) -> Optional[Path]:
        """
        Checks if the extra's parent directory name suggests a relationship with a sibling directory.
        Example: Matrix-Extras/trailer.mp4 -> Matrix/Matrix.mkv
        """
        extra_dir = extra_path.parent
        grandparent = extra_dir.parent
        
        if grandparent in folder_index or any(p.parent == grandparent for p in folder_index.keys()):
            extra_dir_name = extra_dir.name.lower()
            
            for folder, media_list in folder_index.items():
                if folder.parent == grandparent:
                    for media in media_list:
                        media_name = media.stem.lower()
                        if media_name in extra_dir_name:
                            return media
        return None

    def _match_by_name(self, extra_path: Path, potential_parents: List[Path]) -> Optional[Path]:
        """
        Selects the best parent match based on filename similarity.
        """
        if len(potential_parents) == 1:
            return potential_parents[0]
        extra_name = extra_path.stem.lower()
        for parent in potential_parents:
            parent_name = parent.stem.lower()
            if parent_name in extra_name or extra_name.startswith(parent_name):
                return parent
        return None
