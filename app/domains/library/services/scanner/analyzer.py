import re
import os
import hashlib
from typing import Dict, Any, Optional
from guessit import guessit

def clean_for_json(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif hasattr(obj, 'alpha2'):
        return obj.alpha2
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    else:
        return str(obj)

class Analyzer:
    """
    Guessit-based analyzer for metadata parsing from filenames and directories.
    """

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Runs Guessit analysis on a given string.
        """
        if not text:
            return {}
        # Normalize S1-01 / S02-09 style range-trap to S1E01 / S02E09
        normalized_text = re.sub(r'(?i)\bs(\d+)-(\d+)\b', r'S\1E\2', text)
        try:
            # guessit returns a dict-like object, convert it to a standard dict
            res = clean_for_json(dict(guessit(normalized_text)))
            if res.get("type") == "series":
                res["type"] = "tv"
            return res
        except Exception:
            return {}

    def extract_language(self, text: str) -> Optional[str]:
        """
        Extracts language codes (e.g., 'hu', 'en') from text using Guessit.
        """
        filename = os.path.basename(text)
        data = self.analyze_text(filename)
        langs = data.get('language') or data.get('subtitle_language')
        
        if isinstance(langs, list) and langs:
            lang = langs[0]
            return getattr(lang, 'alpha2', str(lang))
        elif langs:
            return getattr(langs, 'alpha2', str(langs))
        return None

    def get_triple_data(self, internal_title: Optional[str], filename: str, folder_name: str) -> Dict[str, Any]:
        """
        Executes the 'Triple Analysis' strategy.
        Returns data from the internal file title, the filename, and the immediate parent folder.
        """
        return {
            "it": self.analyze_text(internal_title) if internal_title else {},
            "fn": self.analyze_text(filename),
            "fd": self.analyze_text(folder_name)
        }

    def generate_group_hash(self, title: str, year: Any = "", season: Any = "", episode: Any = "") -> str:
        """
        Generates a unique group hash for collision detection and grouping.
        """
        if not title:
            return ""
            
        clean_title = re.sub(r'[^a-z0-9]', '', title.lower())
        
        if isinstance(episode, list):
            ep_hash = "-".join(map(str, sorted(episode)))
        else:
            ep_hash = str(episode) if episode is not None else ""

        hash_key = f"{clean_title}|{year or ''}|{season or ''}|{ep_hash}"
        return hashlib.md5(hash_key.encode()).hexdigest()
