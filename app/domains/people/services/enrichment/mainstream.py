from typing import Dict, Any, Callable
from sqlalchemy.orm import Session
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

class TMDBEnricher:
    def __init__(self, scrapers: ScraperGatewayPort, get_temp_db_cb: Callable[[], Session], close_temp_db_cb: Optional[Callable[[Session], None]] = None):
        self.scrapers = scrapers
        self.get_temp_db = get_temp_db_cb
        self.close_temp_db = close_temp_db_cb

    def enrich_tmdb(self, external_id: str, result: Dict[str, Any]) -> bool:
        temp_db = self.get_temp_db()
        details = None
        try:
            tmdb = self.scrapers.tmdb(temp_db)
            details = tmdb.get_person_details(int(external_id))
        finally:
            if self.close_temp_db:
                self.close_temp_db(temp_db)
            else:
                temp_db.close()

        if details:
            images_data = details.get("images", {}).get("profiles", [])
            tmdb_imgs = [img.get("file_path") for img in images_data if img.get("file_path")]
            
            original_bio = details.get("biography")
            biographies = {}
            if original_bio:
                biographies[DEFAULT_FALLBACK_LANGUAGE] = original_bio
            translations = details.get("translations", {}).get("translations", [])
            for trans in translations:
                locale = trans.get("iso_639_1")
                bio = trans.get("data", {}).get("biography")
                if bio and locale:
                    biographies[locale] = bio

            socials_dict = {}
            ext_ids = details.get("external_ids") or {}
            for soc_key in ["instagram", "twitter", "tiktok", "facebook", "youtube"]:
                soc_val = ext_ids.get(f"{soc_key}_id")
                if soc_val:
                    socials_dict[soc_key] = str(soc_val)

            # Compile source_data
            source_data = {
                "birthday": details.get("birthday"),
                "deathday": details.get("deathday"),
                "place_of_birth": details.get("place_of_birth"),
                "gender": details.get("gender"),
                "popularity": details.get("popularity"),
                "profile_path": details.get("profile_path"),
                "known_for_department": details.get("known_for_department"),
                "homepage": details.get("homepage"),
                "images": tmdb_imgs,
                "biographies": biographies,
                "aliases": details.get("also_known_as") or [],
                "socials": socials_dict
            }

            # Merge into prioritized result
            result["birthday"] = source_data["birthday"] or result["birthday"]
            result["deathday"] = source_data["deathday"] or result["deathday"]
            result["place_of_birth"] = source_data["place_of_birth"] or result["place_of_birth"]
            if source_data["gender"] is not None:
                result["gender"] = source_data["gender"]
            if source_data["popularity"] is not None:
                result["popularity"] = source_data["popularity"]
            result["profile_path"] = source_data["profile_path"] or result["profile_path"]
            if source_data["known_for_department"]:
                result["known_for_department"] = source_data["known_for_department"]
            result["homepage"] = source_data["homepage"] or result["homepage"]
            
            if tmdb_imgs:
                if result["images"] is None:
                    result["images"] = []
                for img in tmdb_imgs:
                    if img not in result["images"]:
                        result["images"].append(img)

            if biographies:
                result["biographies"].update(biographies)
            if source_data["aliases"]:
                result["aliases"].extend(source_data["aliases"])
            if socials_dict:
                result["socials"].update(socials_dict)

            if "provider_profiles" not in result:
                result["provider_profiles"] = {}
            result["provider_profiles"]["tmdb"] = source_data
            return True
        return False
