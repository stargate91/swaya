from typing import Dict, Any, Callable
from sqlalchemy.orm import Session
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

class TMDBEnricher:
    def __init__(self, scrapers: ScraperGatewayPort, get_temp_db_cb: Callable[[], Session]):
        self.scrapers = scrapers
        self.get_temp_db = get_temp_db_cb

    def enrich_tmdb(self, external_id: str, result: Dict[str, Any]) -> bool:
        temp_db = self.get_temp_db()
        details = None
        try:
            tmdb = self.scrapers.tmdb(temp_db)
            details = tmdb.get_person_details(int(external_id))
        finally:
            temp_db.close()

        if details:
            result["birthday"] = details.get("birthday")
            result["deathday"] = details.get("deathday")
            result["place_of_birth"] = details.get("place_of_birth")
            if details.get("gender") is not None:
                result["gender"] = details.get("gender")
            if details.get("popularity") is not None:
                result["popularity"] = details.get("popularity")
            result["profile_path"] = details.get("profile_path")
            if details.get("known_for_department"):
                result["known_for_department"] = details.get("known_for_department")
            result["homepage"] = details.get("homepage")
            
            images_data = details.get("images", {}).get("profiles", [])
            result["images"] = [img.get("file_path") for img in images_data if img.get("file_path")]

            original_bio = details.get("biography")
            if original_bio:
                result["biographies"][DEFAULT_FALLBACK_LANGUAGE] = original_bio

            translations = details.get("translations", {}).get("translations", [])
            for trans in translations:
                locale = trans.get("iso_639_1")
                bio = trans.get("data", {}).get("biography")
                if bio and locale:
                    result["biographies"][locale] = bio

            if details.get("also_known_as"):
                result["aliases"].extend(details["also_known_as"])

            ext_ids = details.get("external_ids") or {}
            for soc_key in ["instagram", "twitter", "tiktok", "facebook", "youtube"]:
                soc_val = ext_ids.get(f"{soc_key}_id")
                if soc_val:
                    result["socials"][soc_key] = str(soc_val)
            return True
        return False
