from typing import Optional, Dict, Any
from app.shared_kernel.enums import ScanMode
from app.shared_kernel.ports.file_system_port import FileSystemPort

class HashCalculator:
    """
    Submodule to calculate file hashes: MD5, OSHASH, PHASH, SHA256.
    """
    def __init__(self, fs: FileSystemPort):
        self.fs = fs

    def calculate_hashes(
        self,
        filepath_str: str,
        mode: ScanMode,
        duration: Optional[float] = None
    ) -> Dict[str, Optional[str]]:
        """
        Calculates all relevant hashes for a given filepath based on ScanMode.
        """
        hashes = {
            "hash_md5": None,
            "hash_oshash": None,
            "hash_phash": None,
            "hash_sha256": None,
        }
        
        try:
            hashes["hash_oshash"] = self.fs.calculate_oshash(filepath_str)
        except Exception:
            pass

        if mode == ScanMode.SCENES:
            try:
                hashes["hash_phash"] = self.fs.calculate_phash(filepath_str, duration)
            except Exception:
                pass
        else:
            try:
                hashes["hash_md5"] = self.fs.calculate_fast_hash(filepath_str)
            except Exception:
                pass

        return hashes

    def calculate_fast_hash(self, filepath_str: str) -> Optional[str]:
        try:
            return self.fs.calculate_fast_hash(filepath_str)
        except Exception:
            return None

    def calculate_oshash(self, filepath_str: str) -> Optional[str]:
        try:
            return self.fs.calculate_oshash(filepath_str)
        except Exception:
            return None

    def calculate_phash(self, filepath_str: str, duration: Optional[float] = None) -> Optional[str]:
        try:
            return self.fs.calculate_phash(filepath_str, duration)
        except Exception:
            return None
