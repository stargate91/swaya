import os
import shutil
import platform
import logging
import sys
import subprocess
from pathlib import Path
from typing import Iterable, Set, Optional

logger = logging.getLogger(__name__)

def to_win_long_path(path_str: str) -> str:
    r"""
    Converts a path to a Windows extended-length path (\\?\) if on Windows.
    This bypasses the 260 character MAX_PATH limit.
    """
    if platform.system() != "Windows":
        return path_str
    
    if path_str.startswith("\\\\?\\") or not os.path.isabs(path_str):
        return path_str
        
    abs_path = os.path.abspath(path_str)
    
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abs_path[2:]
    
    return "\\\\?\\" + abs_path

def move_with_progress(src: str, dst: str, progress_callback=None):
    """
    Moves a file with progress reporting.
    Tries os.rename first (instant for same drive).
    Falls back to chunked copy + delete (for cross-drive) to allow progress updates.
    """
    src_long = to_win_long_path(src)
    dst_long = to_win_long_path(dst)

    try:
        os.rename(src_long, dst_long)
        if progress_callback:
            progress_callback(1.0)
        return
    except OSError:
        pass # Probably cross-drive EXDEV

    # Fallback to chunked copy
    file_size = os.path.getsize(src_long)
    copied = 0
    chunk_size = 1024 * 1024 * 16 # 16 MB chunks

    with open(src_long, 'rb') as fsrc, open(dst_long, 'wb') as fdst:
        while True:
            buf = fsrc.read(chunk_size)
            if not buf:
                break
            fdst.write(buf)
            copied += len(buf)
            if progress_callback and file_size > 0:
                progress_callback(copied / file_size)

    # Copy metadata
    shutil.copystat(src_long, dst_long)
    # Remove original
    os.remove(src_long)
    
    if progress_callback:
        progress_callback(1.0)

def _send_to_trash_windows(path: Path) -> None:
    escaped_path = str(path).replace("'", "''")
    script = (
        f"$target = '{escaped_path}'; "
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        "if (Test-Path -LiteralPath $target -PathType Container) { "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
        "$target, "
        "[Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, "
        "[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin"
        ")"
        "} else { "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
        "$target, "
        "[Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs, "
        "[Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin"
        ")"
        "}"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
    )

def send_to_trash(paths: Iterable[Path]) -> int:
    """Moves existing files to the OS recycle bin/trash."""
    try:
        from send2trash import send2trash
    except ImportError:
        send2trash = None

    moved = 0
    candidates = []
    seen: Set[str] = set()
    for path in paths:
        if not path:
            continue
        candidate = Path(path)
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            candidates.append(candidate)

    filtered_candidates = []
    for candidate in sorted(candidates, key=lambda p: len(p.parts)):
        if any(parent in candidate.parents for parent in filtered_candidates if parent.is_dir()):
            continue
        filtered_candidates.append(candidate)

    for candidate in filtered_candidates:
        if send2trash is not None:
            send2trash(str(candidate))
        elif sys.platform.startswith("win"):
            _send_to_trash_windows(candidate)
        else:
            raise RuntimeError("send2trash is not installed and OS is not Windows")
        moved += 1
        logger.info(f"FS: Sent to trash: {candidate}")

    return moved

def calculate_fast_hash(filepath: str) -> Optional[str]:
    """Fast hash calculation: file size + content of the first and last 1MB"""
    import os
    import hashlib
    try:
        long_path = to_win_long_path(filepath)
        if not os.path.exists(long_path):
            return None
            
        file_size = os.path.getsize(long_path)
        if file_size < 2 * 1024 * 1024:
            with open(long_path, 'rb') as f:
                content = f.read()
        else:
            with open(long_path, 'rb') as f:
                first_part = f.read(1024 * 1024)
                try:
                    f.seek(-1024 * 1024, os.SEEK_END)
                    last_part = f.read(1024 * 1024)
                except OSError:
                    last_part = b""
                content = first_part + last_part
        
        hasher = hashlib.md5(content)
        hasher.update(str(file_size).encode())
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash {filepath}: {e}")
        return None

def calculate_oshash(filepath: str) -> Optional[str]:
    """
    Calculates OpenSubtitles hash for a file.
    Size + 64bit check sum of the first and last 64k of the file.
    """
    import os
    import struct
    try:
        long_path = to_win_long_path(filepath)
        if not os.path.exists(long_path):
            return None
        file_size = os.path.getsize(long_path)
        if file_size < 65536 * 2:
            return None

        with open(long_path, "rb") as f:
            # Read first 64k
            buffer = f.read(65536)
            hash_val = file_size
            
            # Sum 64-bit words
            words = struct.unpack("<8192Q", buffer)
            hash_val = (hash_val + sum(words)) & 0xFFFFFFFFFFFFFFFF
            
            # Read last 64k
            f.seek(-65536, os.SEEK_END)
            buffer = f.read(65536)
            words = struct.unpack("<8192Q", buffer)
            hash_val = (hash_val + sum(words)) & 0xFFFFFFFFFFFFFFFF
            
        return f"{hash_val:016x}"
    except Exception as e:
        logger.error(f"Failed to calculate oshash for {filepath}: {e}")
        return None

def calculate_full_md5(filepath: str) -> Optional[str]:
    """Calculates the full MD5 hash of a file."""
    import os
    import hashlib
    try:
        long_path = to_win_long_path(filepath)
        if not os.path.exists(long_path):
            return None
        hasher = hashlib.md5()
        with open(long_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate full MD5 for {filepath}: {e}")
        return None

def calculate_full_sha256(filepath: str) -> Optional[str]:
    """Calculates the full SHA256 hash of a file."""
    import os
    import hashlib
    try:
        long_path = to_win_long_path(filepath)
        if not os.path.exists(long_path):
            return None
        hasher = hashlib.sha256()
        with open(long_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate full SHA256 for {filepath}: {e}")
        return None
