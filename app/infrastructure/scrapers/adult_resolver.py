import logging
import difflib
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.enums import Provider, MediaType, ItemStatus, ScanMode

logger = logging.getLogger(__name__)

from app.shared_kernel.constants import PORNDB_API_BASE, SCRAPER_REQUEST_TIMEOUT

class AdultResolver:
    """
    Handles resolving adult scene items against StashDB, PornDB, and FansDB APIs.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def resolve_adult_item(self, item: MediaItem, mode: ScanMode = ScanMode.SCENES, task_id: Optional[int] = None):
        """Resolves adult scene/JAV items using MD5 fingerprinting, OSHash, or text search fallbacks."""
        from app.infrastructure.scrapers.stashdb import StashDBScraper
        from app.infrastructure.scrapers.porndb import PornDBScraper
        from app.infrastructure.scrapers.fansdb import FansDBScraper
        from app.infrastructure.scrapers.resolver import normalize_title

        stash_scraper = StashDBScraper(self.db)
        porndb_scraper = PornDBScraper(self.db)
        fans_scraper = FansDBScraper(self.db)

        target_media_type = MediaType.JAV if mode.is_jav else MediaType.SCENE
        scrapers_to_try = []
        logger.info(f"resolve_adult_item called for mode: {mode.value}, porndb key from setting: '{porndb_scraper.get_setting('porndb_api_key')}'")
        if mode.is_jav:
            if porndb_scraper.get_setting("porndb_api_key") or porndb_scraper.get_setting("porndb_api_token"):
                scrapers_to_try.append((porndb_scraper, Provider.PORNDB))
        else:
            order_setting = stash_scraper.get_setting("scenes_scraper_order") or "stashdb,porndb,fansdb"
            order = [o.strip().lower() for o in str(order_setting).split(",")]
            
            available = {}
            if stash_scraper.get_setting("stashdb_api_key"):
                available["stashdb"] = (stash_scraper, Provider.STASHDB)
            if porndb_scraper.get_setting("porndb_api_key") or porndb_scraper.get_setting("porndb_api_token"):
                available["porndb"] = (porndb_scraper, Provider.PORNDB)
            if fans_scraper.get_setting("fansdb_api_key"):
                available["fansdb"] = (fans_scraper, Provider.FANSDB)
                
            for prov_name in order:
                if prov_name in available:
                    scrapers_to_try.append(available[prov_name])

        if not scrapers_to_try:
            logger.warning("No adult metadata provider API key configured.")
            item.status = ItemStatus.NO_MATCH
            self.db.flush()
            return

        for scraper, provider in scrapers_to_try:
            scene_data = None

            # 1. Try Hash Lookup
            if provider in (Provider.STASHDB, Provider.FANSDB):
                hash_query = """
                query FindSceneByHash($hash: String!) {
                  queryScenes(input: { fingerprints: { value: [$hash], modifier: EQUALS }, page: 1, per_page: 1 }) {
                    scenes {
                      id
                      title
                      details
                      date
                      tags {
                        name
                      }
                      studio {
                        id
                        name
                        images {
                          url
                        }
                      }
                      performers {
                        performer {
                          id
                          name
                          gender
                          scene_count
                          birth_date
                          images {
                            url
                          }
                          ethnicity
                          hair_color
                          eye_color
                          height
                          measurements {
                            band_size
                            cup_size
                            waist
                            hip
                          }
                        }
                      }
                      images {
                        url
                      }
                    }
                  }
                }
                """
                # Try MD5 first
                if item.hash_md5:
                    cache_key_md5 = f"{provider.value}/hash/v3/md5/{item.hash_md5}"
                    cached = scraper.cache.get(provider, cache_key_md5)
                    if cached is not None:
                        if cached:  # Not empty negative cache
                            scene_data = cached
                    else:
                        try:
                            res = scraper.execute_query(hash_query, {"hash": item.hash_md5})
                            if res and res.get("queryScenes", {}).get("scenes"):
                                scene_data = res["queryScenes"]["scenes"][0]
                                scraper.cache.set(provider, cache_key_md5, scene_data)
                            else:
                                scraper.cache.set(provider, cache_key_md5, {})
                        except Exception as e:
                            logger.error(f"{provider.value} MD5 hash query failed: {e}")

                # Try OSHash fallback
                if not scene_data and item.hash_oshash:
                    cache_key_osh = f"{provider.value}/hash/v3/oshash/{item.hash_oshash}"
                    cached = scraper.cache.get(provider, cache_key_osh)
                    if cached is not None:
                        if cached:
                            scene_data = cached
                    else:
                        try:
                            res = scraper.execute_query(hash_query, {"hash": item.hash_oshash})
                            if res and res.get("queryScenes", {}).get("scenes"):
                                scene_data = res["queryScenes"]["scenes"][0]
                                scraper.cache.set(provider, cache_key_osh, scene_data)
                            else:
                                scraper.cache.set(provider, cache_key_osh, {})
                        except Exception as e:
                            logger.error(f"{provider.value} OSHash query failed: {e}")

            elif provider == Provider.PORNDB and item.hash_oshash:
                # Use REST API hash lookup with caching for the selected adult mode
                cache_key_pornhash = f"porndb/{mode.value}/hash/oshash/{item.hash_oshash}"
                cached = scraper.cache.get(provider, cache_key_pornhash)
                if cached is not None:
                    if cached:
                        scene_data = cached
                else:
                    api_token = scraper.get_setting("porndb_api_key") or scraper.get_setting("porndb_api_token")
                    headers = {
                        "Authorization": f"Bearer {api_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    
                    endpoint = "jav" if mode.is_jav else "scenes"
                    for ep in [endpoint]:
                        url = f"{PORNDB_API_BASE}/{ep}/hash/{item.hash_oshash}?type=OSHASH"
                        try:
                            resp = scraper.session.get(url, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
                            if resp.status_code == 200:
                                res_json = resp.json()
                                if res_json and res_json.get("data"):
                                    scene_data = res_json["data"]
                                    scraper.cache.set(provider, cache_key_pornhash, scene_data)
                                    break
                        except Exception as e:
                            logger.error(f"PornDB OSHash query failed for {ep}: {e}")
                    
                    if not scene_data:
                        scraper.cache.set(provider, cache_key_pornhash, {})

            if scene_data:
                # Save hash match
                self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
                self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == provider,
                    MetadataMatch.external_id == str(scene_data["id"]),
                    MetadataMatch.media_type == target_media_type
                ).delete()

                from app.infrastructure.scrapers.persistence import ScraperPersister
                from app.infrastructure.scrapers.normalizer import ScraperNormalizer
                if provider == Provider.PORNDB:
                    scene_data = scraper.enrich_scene_ratings(scene_data)
                normalized = ScraperNormalizer.normalize_adult_scene(provider.value, scene_data)
                persister = ScraperPersister(self.db)
                match = persister.persist_normalized_scene(provider, str(scene_data["id"]), normalized, media_type=target_media_type)
                match.media_item_id = item.id
                item.status = ItemStatus.MATCHED
                
                # Log successful hash match
                scraper.log_search(
                    task_id=task_id,
                    media_item_id=item.id,
                    search_query=f"hash: md5={item.hash_md5}, oshash={item.hash_oshash}",
                    result_count=1,
                    details={
                        "hash_match": True,
                        "matched_scene_id": str(scene_data["id"]),
                        "matched_title": scene_data.get("title"),
                        "final_status": "matched"
                    }
                )
                self.db.flush()
                return

            # 2. Try Text Search Fallback
            parsed = item.parsed_info or {}
            fn_data = parsed.get("fn") or {}
            it_data = parsed.get("it") or {}
            fd_data = parsed.get("fd") or {}

            import re
            search_title = None
            if mode == ScanMode.JAV:
                # Matches patterns like SSNI-942, 3DJS-051, MGP.121
                match = re.search(r'\b([a-zA-Z0-9]{2,10})[-.]([0-9]{3,5})\b', item.filename)
                if match:
                    search_title = f"{match.group(1)}-{match.group(2)}"
                else:
                    # Fallback for codes without hyphen/dot, e.g. SSNI942
                    match_no_sep = re.search(r'\b([a-zA-Z]{2,6})([0-9]{3,5})\b', item.filename)
                    if match_no_sep:
                        search_title = f"{match_no_sep.group(1)}-{match_no_sep.group(2)}"

            if not search_title:
                search_title = fn_data.get("title") or fd_data.get("title") or it_data.get("title")

            if not search_title:
                continue

            cache_key_search = f"{provider.value}/{mode.value}/search/v3/{search_title.strip().lower()}"
            cached_search = scraper.cache.get(provider, cache_key_search)
            if cached_search is not None:
                scenes = cached_search
            else:
                if provider == Provider.PORNDB and mode.is_jav:
                    scenes = scraper.search_jav(search_title, per_page=10)
                    scraper.cache.set(provider, cache_key_search, scenes)
                else:
                    search_query = """
                query SearchScenes($q: String!) {
                  searchScene(term: $q) {
                    id
                    title
                    details
                    date
                    tags {
                      name
                    }
                    studio {
                      id
                      name
                      images {
                        url
                      }
                    }
                    performers {
                      performer {
                        id
                        name
                        gender
                        scene_count
                        birth_date
                        images {
                          url
                        }
                        ethnicity
                        hair_color
                        eye_color
                        height
                        measurements {
                          band_size
                          cup_size
                          waist
                          hip
                        }
                      }
                    }
                    images {
                      url
                    }
                  }
                }
                """
                    try:
                        res = scraper.execute_query(search_query, {"q": search_title})
                        scenes = res.get("searchScene", []) if res else []
                        if scenes is None:
                            scenes = []
                        scraper.cache.set(provider, cache_key_search, scenes)
                    except Exception as e:
                        logger.error(f"Text query failed for provider {provider.value}: {e}")
                        scenes = []

            if not scenes:
                continue

            # Score candidates
            candidates = []
            for scene in scenes:
                title = scene.get("title") or ""
                if mode.is_jav:
                    ext_id = scene.get("external_id") or ""
                    if normalize_title(search_title) == normalize_title(ext_id):
                        score = 1.0
                    elif normalize_title(search_title) in normalize_title(title):
                        score = 0.95
                    else:
                        score = difflib.SequenceMatcher(
                            None, normalize_title(search_title), normalize_title(title)
                        ).ratio()
                else:
                    score = difflib.SequenceMatcher(
                        None, normalize_title(search_title), normalize_title(title)
                    ).ratio()
                candidates.append((score, scene))

            candidates.sort(key=lambda x: x[0], reverse=True)
            if candidates:
                best_score, best_scene = candidates[0]

                if best_score >= 0.8:
                    self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
                    self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == provider,
                        MetadataMatch.external_id == str(best_scene["id"]),
                        MetadataMatch.media_type == target_media_type
                    ).delete()

                    from app.infrastructure.scrapers.persistence import ScraperPersister
                    from app.infrastructure.scrapers.normalizer import ScraperNormalizer
                    if provider == Provider.PORNDB:
                        best_scene = scraper.enrich_scene_ratings(best_scene)
                    normalized = ScraperNormalizer.normalize_adult_scene(provider.value, best_scene)
                    persister = ScraperPersister(self.db)
                    match = persister.persist_normalized_scene(provider, str(best_scene["id"]), normalized, media_type=target_media_type)
                    match.media_item_id = item.id
                    item.status = ItemStatus.MATCHED
                    
                    # Log successful text match
                    scraper.log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        search_query=search_title,
                        result_count=len(scenes),
                        details={
                            "hash_match": False,
                            "candidates": [
                                {
                                    "id": s.get("id"),
                                    "title": s.get("title"),
                                    "score": difflib.SequenceMatcher(None, normalize_title(search_title), normalize_title(s.get("title") or "")).ratio()
                                }
                                for s in scenes[:10]
                            ],
                            "best_score": best_score,
                            "matched_scene_id": str(best_scene["id"]),
                            "final_status": "matched"
                        }
                    )
                    self.db.flush()
                    return
                else:
                    # Log failed text match due to low score
                    scraper.log_search(
                        task_id=task_id,
                        media_item_id=item.id,
                        search_query=search_title,
                        result_count=len(scenes),
                        details={
                            "hash_match": False,
                            "candidates": [
                                {
                                    "id": s.get("id"),
                                    "title": s.get("title"),
                                    "score": difflib.SequenceMatcher(None, normalize_title(search_title), normalize_title(s.get("title") or "")).ratio()
                                }
                                for s in scenes[:10]
                            ],
                            "best_score": best_score,
                            "final_status": "no_match_low_score"
                        }
                    )

        item.status = ItemStatus.NO_MATCH
        self.db.flush()
        
        # Log final fallback no match outcome
        last_scraper = scrapers_to_try[-1][0] if scrapers_to_try else stash_scraper
        last_scraper.log_search(
            task_id=task_id,
            media_item_id=item.id,
            search_query=item.filename,
            result_count=0,
            details={"hash_match": False, "candidates": [], "final_status": "no_match"}
        )
