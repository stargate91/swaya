from typing import Dict, Any
from pathlib import Path

class VideoProber:
    def __init__(self, prober: Any, hash_calculator: Any, analyzer: Any, mode: Any):
        self.prober = prober
        self.hash_calculator = hash_calculator
        self.analyzer = analyzer
        self.mode = mode

    def probe_and_analyze_target(self, filepath: Path) -> Dict[str, Any]:
        """
        Runs ffprobe, extracts metadata, computes hashes, and analyzes names via Guessit in a background thread.
        """
        filepath_str = str(filepath)
        result = {
            "probe_info": None,
            "hash_md5": None,
            "hash_oshash": None,
            "hash_phash": None,
            "hash_sha256": None,
            "guessit_info": None,
        }
        
        # 1. Run ffprobe
        try:
            raw_data = self.prober.probe(filepath_str)
            info = self.prober.extract_info(raw_data)
            result["probe_info"] = info
        except Exception:
            pass

        # 2. Compute Hashes
        duration = None
        if result.get("probe_info"):
            duration = result["probe_info"].get("duration")

        hashes = self.hash_calculator.calculate_hashes(filepath_str, self.mode, duration)
        result.update(hashes)

        # 3. Analyze text with Guessit
        internal_title = None
        if result["probe_info"]:
            internal_title = result["probe_info"].get("internal_title")
            
        result["guessit_info"] = self.analyzer.get_triple_data(
            internal_title, 
            filepath.name, 
            filepath.parent.name
        )
        
        return result
