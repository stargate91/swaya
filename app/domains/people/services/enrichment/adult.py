import logging
import re
from typing import Dict, Any, List, Callable
from sqlalchemy.orm import Session
from app.shared_kernel.enums import Provider
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.people.services.enrichment.helpers import EnrichmentHelpers

logger = logging.getLogger(__name__)

class AdultEnricher:
    def __init__(self, scrapers: ScraperGatewayPort, get_temp_db_cb: Callable[[], Session]):
        self.scrapers = scrapers
        self.get_temp_db = get_temp_db_cb

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
            temp_db.close()

        if perf:
            result["birthday"] = perf.get("birth_date") or result["birthday"]
            if perf.get("rating_porndb") is not None:
                result["rating_porndb"] = float(perf["rating_porndb"])
            if perf.get("scene_count") is not None:
                result["scene_count"] = max(result["scene_count"] or 0, int(perf["scene_count"]))
            result["ethnicity"] = perf.get("ethnicity") or result["ethnicity"]
            result["hair_color"] = perf.get("hair_color") or result["hair_color"]
            result["eye_color"] = perf.get("eye_color") or result["eye_color"]
            if perf.get("height") is not None:
                result["height"] = int(perf["height"])
            if perf.get("weight") is not None:
                result["weight"] = int(perf["weight"])

            if perf.get("aliases"):
                result["aliases"].extend(perf["aliases"])

            tats = perf.get("tattoos")
            if tats and isinstance(tats, list):
                tats_str = ", ".join(
                    f"{t.get('body_part')}: {t.get('description')}" if t.get('description') else t.get('body_part')
                    for t in tats if t.get('body_part')
                )
                if tats_str:
                    result["tattoos"] = tats_str
            elif isinstance(tats, str) and tats:
                result["tattoos"] = tats

            piers = perf.get("piercings")
            if piers and isinstance(piers, list):
                piers_str = ", ".join(
                    f"{p.get('body_part')}: {p.get('description')}" if p.get('description') else p.get('body_part')
                    for p in piers if p.get('body_part')
                )
                if piers_str:
                    result["piercings"] = piers_str
            elif isinstance(piers, str) and piers:
                result["piercings"] = piers

            if perf.get("orientation"):
                result["orientation"] = perf["orientation"]

            result["place_of_birth"] = perf.get("country") or perf.get("place_of_birth") or result["place_of_birth"]
            result["deathday"] = perf.get("death_date") or perf.get("deathday") or result["deathday"]
            if perf.get("career_start_year") is not None:
                result["career_start_year"] = int(perf["career_start_year"])
            if perf.get("career_end_year") is not None:
                result["career_end_year"] = int(perf["career_end_year"])

            g = perf.get("gender")
            if g:
                g_lower = str(g).lower()
                if "female" in g_lower:
                    result["gender"] = 1
                elif "male" in g_lower:
                    result["gender"] = 2
                else:
                    result["gender"] = 0

            m = perf.get("measurements")
            if m and isinstance(m, dict):
                band = m.get("band_size")
                cup = m.get("cup_size")
                waist = m.get("waist")
                hip = m.get("hip")
                if band and cup and waist and hip:
                    result["measurements"] = f"{band}{cup}-{waist}-{hip}"
                if cup:
                    result["cup_size"] = str(cup)

            bio = perf.get("details")
            if bio:
                result["biographies"][DEFAULT_FALLBACK_LANGUAGE] = bio

            images = perf.get("images") or []
            if images:
                urls_list = [img.get("url") for img in images if img.get("url")]
                if urls_list:
                    if result["images"] is None:
                        result["images"] = []
                    for u in urls_list:
                        if u not in result["images"]:
                            result["images"].append(u)
                    if not result["profile_path"]:
                        result["profile_path"] = urls_list[0]

            perf_urls = perf.get("urls") or []
            if perf_urls:
                result["urls"].extend(perf_urls)
            for url in perf_urls:
                if not url or not isinstance(url, str):
                    continue
                for ext_link in EnrichmentHelpers.extract_ids_from_urls([url]):
                    ext_pair = (ext_link["provider"], ext_link["external_id"])
                    if ext_pair not in processed_pairs:
                        to_process.append(ext_link)
                        result["links_to_create"].append(ext_link)

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
