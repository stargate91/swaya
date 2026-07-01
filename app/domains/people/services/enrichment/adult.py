import logging
import re
from typing import Dict, Any, List, Callable, Optional
from sqlalchemy.orm import Session
from app.shared_kernel.enums import Provider
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.people.services.enrichment.helpers import EnrichmentHelpers

logger = logging.getLogger(__name__)

def safe_int(val) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        digits = "".join(c for c in val if c.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError as e:
                logger.debug(f"Swallowed exception in domains/people/services/enrichment/adult.py:22: {e}", exc_info=True)
    return None

class AdultEnricher:
    def __init__(self, scrapers: ScraperGatewayPort, get_temp_db_cb: Callable[[], Session], close_temp_db_cb: Optional[Callable[[Session], None]] = None):
        self.scrapers = scrapers
        self.get_temp_db = get_temp_db_cb
        self.close_temp_db = close_temp_db_cb

    def enrich_adult(
        self,
        provider: Provider,
        external_id: str,
        result: Dict[str, Any],
        to_process: List[dict],
        processed_pairs: set
    ) -> bool:
        temp_db = self.get_temp_db()
        perf = None
        try:
            scraper = self.scrapers.adult(provider, temp_db)
            perf = scraper.get_performer_details(external_id)
        except Exception as e:
            logger.error(f"Error calling get_performer_details on {provider.value}: {e}")
        finally:
            if self.close_temp_db:
                self.close_temp_db(temp_db)
            else:
                temp_db.close()

        if perf:
            tats_val = None
            tats = perf.get("tattoos")
            if tats and isinstance(tats, list):
                tats_str = ", ".join(
                    f"{t.get('body_part')}: {t.get('description')}" if t.get('description') else t.get('body_part')
                    for t in tats if t.get('body_part')
                )
                if tats_str:
                    tats_val = tats_str
            elif isinstance(tats, str) and tats:
                tats_val = tats

            piers_val = None
            piers = perf.get("piercings")
            if piers and isinstance(piers, list):
                piers_str = ", ".join(
                    f"{p.get('body_part')}: {p.get('description')}" if p.get('description') else p.get('body_part')
                    for p in piers if p.get('body_part')
                )
                if piers_str:
                    piers_val = piers_str
            elif isinstance(piers, str) and piers:
                piers_val = piers

            g_val = None
            g = perf.get("gender")
            if g:
                g_lower = str(g).lower()
                if "female" in g_lower:
                    g_val = 1
                elif "male" in g_lower:
                    g_val = 2
                else:
                    g_val = 0

            measurements_val = None
            cup_val = None
            band_val = None
            waist_val = None
            hip_val = None
            m = perf.get("measurements")
            if m and isinstance(m, dict):
                band = m.get("band_size")
                cup = m.get("cup_size")
                waist = m.get("waist")
                hip = m.get("hip")
                
                if band is not None:
                    band_val = safe_int(band)
                if waist is not None:
                    waist_val = safe_int(waist)
                if hip is not None:
                    hip_val = safe_int(hip)
                
                parts = []
                if band and cup:
                    parts.append(f"{band}{cup}")
                elif cup:
                    parts.append(str(cup))
                
                if waist and hip:
                    parts.append(f"{waist}-{hip}")
                
                if parts:
                    measurements_val = "-".join(parts)
                if cup:
                    cup_val = str(cup)

            bio = perf.get("details")
            images = perf.get("images") or []
            urls_list = [img.get("url") for img in images if img.get("url")]

            # Compile source_data
            source_data = {
                "birthday": perf.get("birth_date"),
                "rating_porndb": float(perf["rating_porndb"]) if perf.get("rating_porndb") is not None else None,
                "scene_count": safe_int(perf.get("scene_count")),
                "ethnicity": perf.get("ethnicity"),
                "hair_color": perf.get("hair_color"),
                "eye_color": perf.get("eye_color"),
                "height": safe_int(perf.get("height")),
                "weight": safe_int(perf.get("weight")),
                "aliases": perf.get("aliases") or [],
                "tattoos": tats_val,
                "piercings": piers_val,
                "same_sex_only": perf.get("same_sex_only"),
                "place_of_birth": perf.get("country") or perf.get("place_of_birth"),
                "deathday": perf.get("death_date") or perf.get("deathday"),
                "career_start_year": safe_int(perf.get("career_start_year")),
                "career_end_year": safe_int(perf.get("career_end_year")),
                "gender": g_val,
                "measurements": measurements_val,
                "cup_size": cup_val,
                "band_size": band_val,
                "waist": waist_val,
                "hip": hip_val,
                "breast_type": perf.get("breast_type"),
                "biographies": {DEFAULT_FALLBACK_LANGUAGE: bio} if bio else {},
                "images": urls_list,
                "profile_path": urls_list[0] if urls_list else None,
                "socials": {},
                "urls": perf.get("urls") or []
            }

            # Merge into prioritized result
            result["birthday"] = source_data["birthday"] or result["birthday"]
            if source_data["rating_porndb"] is not None:
                result["rating_porndb"] = source_data["rating_porndb"]
            if source_data["scene_count"] is not None:
                result["scene_count"] = max(result["scene_count"] or 0, source_data["scene_count"])
            result["ethnicity"] = source_data["ethnicity"] or result["ethnicity"]
            result["hair_color"] = source_data["hair_color"] or result["hair_color"]
            result["eye_color"] = source_data["eye_color"] or result["eye_color"]
            if source_data["height"] is not None:
                result["height"] = source_data["height"]
            if source_data["weight"] is not None:
                result["weight"] = source_data["weight"]
            if source_data["aliases"]:
                result["aliases"].extend(source_data["aliases"])
            if source_data["tattoos"]:
                result["tattoos"] = source_data["tattoos"]
            if source_data["piercings"]:
                result["piercings"] = source_data["piercings"]
            if source_data["same_sex_only"]:
                result["same_sex_only"] = source_data["same_sex_only"]
            result["place_of_birth"] = source_data["place_of_birth"] or result["place_of_birth"]
            result["deathday"] = source_data["deathday"] or result["deathday"]
            if source_data["career_start_year"] is not None:
                result["career_start_year"] = source_data["career_start_year"]
            if source_data["career_end_year"] is not None:
                result["career_end_year"] = source_data["career_end_year"]
            if source_data["gender"] is not None:
                result["gender"] = source_data["gender"]
            if source_data["measurements"]:
                result["measurements"] = source_data["measurements"]
            if source_data["cup_size"]:
                result["cup_size"] = source_data["cup_size"]
            if bio:
                result["biographies"][DEFAULT_FALLBACK_LANGUAGE] = bio
            if urls_list:
                if result["images"] is None:
                    result["images"] = []
                for u in urls_list:
                    if u not in result["images"]:
                        result["images"].append(u)
                if not result["profile_path"]:
                    result["profile_path"] = urls_list[0]

            if "provider_profiles" not in result:
                result["provider_profiles"] = {}
            result["provider_profiles"][provider.value] = source_data

            perf_urls = perf.get("urls") or []
            if perf_urls:
                result["urls"].extend(perf_urls)
            for url in perf_urls:
                if not url or not isinstance(url, str):
                    continue
                # URL-based external ID auto-discovery is disabled to keep linking strictly user-controlled
                # and prevent split profiles from automatically linking themselves back.
                # for ext_link in EnrichmentHelpers.extract_ids_from_urls([url]):
                #     ext_pair = (ext_link["provider"], ext_link["external_id"])
                #     if ext_pair not in processed_pairs:
                #         to_process.append(ext_link)

                social_patterns = {
                    "instagram": r'instagram\.com/([a-zA-Z0-9\._\-]+)',
                    "twitter": r'(?:twitter|x)\.com/([a-zA-Z0-9_\-]+)',
                    "tiktok": r'tiktok\.com/@?([a-zA-Z0-9\._\-]+)',
                    "facebook": r'facebook\.com/([a-zA-Z0-9\._\-]+)',
                    "threads": r'threads\.net/@?([a-zA-Z0-9\._\-]+)',
                    "twitch": r'twitch\.tv/([a-zA-Z0-9_\-]+)',
                    "kick": r'kick\.com/([a-zA-Z0-9_\-]+)',
                    "youtube": r'youtube\.com/@?([a-zA-Z0-9\._\-]+)',
                    "onlyfans": r'onlyfans\.com/([a-zA-Z0-9_\.\-]+)',
                    "fansly": r'fansly\.com/([a-zA-Z0-9_\.\-]+)',
                    "patreon": r'patreon\.com/([a-zA-Z0-9_\.\-]+)',
                    "loyalfans": r'loyalfans\.com/([a-zA-Z0-9_\.\-]+)',
                    "manyvids": r'manyvids\.com/([a-zA-Z0-9_\.\-]+)',
                    "linktree": r'linktr\.ee/([a-zA-Z0-9_\.\-]+)',
                    "bluesky": r'bsky\.app/profile/([a-zA-Z0-9_\.\-]+)',
                    "pornhub": r'pornhub\.com/((?:model|pornstar|users)/[a-zA-Z0-9_\-\+]+)',
                    "clips4sale": r'clips4sale\.(?:com|org)/((?:studio|room)/[a-zA-Z0-9_\-\/]+)',
                    "allmylinks": r'allmylinks\.com/([a-zA-Z0-9_\-\.]+)',
                    "beacons": r'beacons\.(?:ai|page)/([a-zA-Z0-9_\-\.]+)',
                    "iafd": r'iafd\.com/person\.rme/([a-zA-Z0-9_\-\.\=\/]+)',
                    "babepedia": r'babepedia\.com/babe/([a-zA-Z0-9_\-\.\+]+)',
                    "freeones": r'freeones\.(?:com|xxx)/([a-zA-Z0-9_\-\.]+)',
                    "data18": r'data18\.com/star/([a-zA-Z0-9_\-\.\+]+)'
                }
                for platform, pattern in social_patterns.items():
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        val = next((g for g in reversed(match.groups()) if g is not None), None)
                        if val:
                            result["socials"][platform] = val
            return True
        return False
