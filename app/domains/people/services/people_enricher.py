import logging
from typing import List, Optional, Callable
import requests
from sqlalchemy.orm import Session
from app.domains.people.models import Person, PersonLocalization, MediaPersonLink, ExternalSourceLink
from app.shared_kernel.enums import Provider, RoleType
from app.shared_kernel.ports.scrapers import ScraperGatewayPort

from app.shared_kernel.constants import DEFAULT_MAX_WORKERS, DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class PeopleEnricher:
    def __init__(
        self,
        db: Optional[Session],
        scrapers: Optional[ScraperGatewayPort] = None,
        session_factory: Optional[Callable[[], Session]] = None,
        is_cancelled: Optional[Callable[[int], bool]] = None,
        has_active_heavy_tasks: Optional[Callable[[], bool]] = None,
        executor: Optional[Any] = None,
        update_progress: Optional[Callable[[int, float], None]] = None,
    ):
        self.db = db
        self.scrapers = scrapers
        self.session_factory = session_factory
        self._is_cancelled_cb = is_cancelled
        self._has_active_heavy_tasks_cb = has_active_heavy_tasks
        self._executor = executor
        self._update_progress_cb = update_progress
        self.session = requests.Session()

    def _is_cancelled(self, task_id: int) -> bool:
        if self._is_cancelled_cb:
            return self._is_cancelled_cb(task_id)
        try:
            from app.domains.tasks import task_manager
            return task_manager.is_cancelled(task_id)
        except Exception:
            return False

    def _has_active_heavy_tasks(self) -> bool:
        if self._has_active_heavy_tasks_cb:
            return self._has_active_heavy_tasks_cb()
        try:
            from app.domains.tasks import task_manager
            return task_manager.has_active_heavy_tasks()
        except Exception:
            return False

    def _get_executor(self):
        if self._executor:
            return self._executor
        try:
            from app.domains.tasks import task_manager
            return task_manager.executor
        except Exception:
            import concurrent.futures
            return concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def _update_progress(self, task_id: int, progress: float) -> None:
        if self._update_progress_cb:
            self._update_progress_cb(task_id, progress)
        else:
            try:
                from app.domains.tasks import task_manager
                task_manager.update_progress(task_id, progress)
            except Exception:
                pass


    def _require_scrapers(self) -> ScraperGatewayPort:
        if self.scrapers is None:
            raise RuntimeError("Scraper gateway is required for people enrichment")
        return self.scrapers

    def _get_temp_db(self) -> Session:
        if self.session_factory:
            return self.session_factory()
        try:
            from app.domains.tasks import task_manager
            if task_manager and hasattr(task_manager, "session_factory") and task_manager.session_factory:
                return task_manager.session_factory()
        except Exception:
            pass
        from app.shared_kernel.database import SessionLocal
        return SessionLocal()


    def enrich_people_for_matches(self, task_id: int, match_ids: List[int], progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """
        Enriches all people associated with the metadata matches.
        Fetches bio, details, and schedules profile downloads in parallel.
        Returns the number of enriched people.
        """
        links = self.db.query(MediaPersonLink).filter(MediaPersonLink.match_id.in_(match_ids)).all()
        person_ids = list(set(link.person_id for link in links))
        if not person_ids:
            return 0

        logger.info(f"Enriching {len(person_ids)} people linked to matches: {match_ids}")
        enriched_count = 0
        total = len(person_ids)

        import concurrent.futures
        import time

        executor = self._get_executor()
        max_workers = DEFAULT_MAX_WORKERS

        def enrich_worker(person_id: int) -> bool:
            if self._is_cancelled(task_id):
                return False

            while self._has_active_heavy_tasks():
                if self._is_cancelled(task_id):
                    return False
                time.sleep(2)

            # 1. Quick read of external IDs and name (Release SQLite transaction immediately)
            local_db = self._get_temp_db()
            try:
                person = local_db.query(Person).filter(Person.id == person_id).first()
                if not person:
                    return False
                person_name = person.name
                links = local_db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
                link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
                external_ids = person.external_ids or {}
                is_adult = person.is_adult
            finally:
                local_db.close()

            # 3. Perform network API request outside of database transaction
            enricher = PeopleEnricher(
                None,
                self.scrapers,
                self.session_factory,
                self._is_cancelled_cb,
                self._has_active_heavy_tasks_cb,
                self._executor,
                self._update_progress_cb
            )
            fetched_data = enricher.fetch_external_details(person_name, external_ids, link_data, is_adult=is_adult)
            if not fetched_data:
                return False

            # 4. Short transaction: save the retrieved data to database
            local_db = self._get_temp_db()
            try:
                person = local_db.query(Person).filter(Person.id == person_id).first()
                if person:
                    enricher.db = local_db
                    enricher.apply_enriched_data(person, fetched_data)
                    local_db.commit()
                    return True
            except Exception as ex:
                local_db.rollback()
                logger.error(f"Failed to save enriched data for person ID {person_id}: {ex}", exc_info=True)
            finally:
                local_db.close()
            return False

        future_to_id = {}
        id_iter = iter(person_ids)
        completed = 0

        while not self._is_cancelled(task_id):
            while len(future_to_id) < max_workers:
                try:
                    pid = next(id_iter)
                except StopIteration:
                    break
                future = executor.submit(enrich_worker, pid)
                future_to_id[future] = pid

            if not future_to_id:
                break

            done, _pending = concurrent.futures.wait(set(future_to_id.keys()), return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                res = future.result()
                if res:
                    enriched_count += 1
                completed += 1
                future_to_id.pop(future, None)

                progress = (completed / total) * 100.0
                self._update_progress(task_id, progress)
                if progress_callback:
                    progress_callback(completed, total)

        for future in list(future_to_id.keys()):
            res = future.result()
            if res:
                enriched_count += 1
            completed += 1
            progress = (completed / total) * 100.0
            self._update_progress(task_id, progress)
            if progress_callback:
                progress_callback(completed, total)

        return enriched_count

    def fetch_external_details(self, name: str, external_ids: dict, links: List[dict], settings: Optional[dict] = None, is_adult: bool = False) -> Optional[dict]:
        all_links = list(links)
        if not all_links:
            for prov_name, ext_id in external_ids.items():
                try:
                    prov = Provider(prov_name)
                    all_links.append({"provider": prov, "external_id": str(ext_id)})
                except ValueError:
                    pass

        result = {
            "birthday": None,
            "deathday": None,
            "place_of_birth": None,
            "gender": None,
            "popularity": None,
            "rating_porndb": None,
            "scene_count": None,
            "profile_path": None,
            "images": None,
            "ethnicity": None,
            "hair_color": None,
            "eye_color": None,
            "height": None,
            "measurements": None,
            "cup_size": None,
            "biographies": {},
            "links_to_create": [],
            "aliases": [],
            "weight": None,
            "tattoos": None,
            "piercings": None,
            "orientation": None,
            "socials": {},
            "urls": [],
            "known_for_department": None,
            "career_start_year": None,
            "career_end_year": None
        }

        has_data = False
        processed_pairs = set()
        to_process = list(all_links)

        while to_process:
            l = to_process.pop(0)
            provider = l["provider"]
            external_id = l["external_id"]

            pair = (provider, external_id)
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            if provider == Provider.TMDB:
                temp_db = self._get_temp_db()
                try:
                    tmdb = self._require_scrapers().tmdb(temp_db)
                    details = tmdb.get_person_details(int(external_id))
                finally:
                    temp_db.close()

                if details:
                    has_data = True
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

                    # Extract TMDB also_known_as
                    if details.get("also_known_as"):
                        result["aliases"].extend(details["also_known_as"])

                    # Extract TMDB socials
                    ext_ids = details.get("external_ids") or {}
                    for soc_key in ["instagram", "twitter", "tiktok", "facebook", "youtube"]:
                        soc_val = ext_ids.get(f"{soc_key}_id")
                        if soc_val:
                            result["socials"][soc_key] = str(soc_val)

            elif provider in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
                temp_db = self._get_temp_db()
                perf = None
                try:
                    if provider in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
                        scraper = self._require_scrapers().adult(provider, temp_db)
                    else:
                        continue
                    
                    perf = scraper.get_performer_details(external_id)
                except Exception as e:
                    logger.error(f"Error calling get_performer_details on {provider.value}: {e}")
                finally:
                    temp_db.close()

                if perf:
                    has_data = True
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
                    
                    # Extract adult performer weight
                    if perf.get("weight") is not None:
                        result["weight"] = int(perf["weight"])

                    # Extract aliases
                    if perf.get("aliases"):
                        result["aliases"].extend(perf["aliases"])

                    # Extract tattoos
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

                    # Extract piercings
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

                    # Extract orientation
                    if perf.get("orientation"):
                        result["orientation"] = perf["orientation"]

                    # Extract career & origin
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
                            result["images"] = urls_list
                            result["profile_path"] = urls_list[0]

                    # Parse URLs dynamically to extract exact provider links and socials
                    perf_urls = perf.get("urls") or []
                    if perf_urls:
                        result["urls"].extend(perf_urls)
                    for url in perf_urls:
                        if not url or not isinstance(url, str):
                            continue
                        import re
                        # Extract exact provider links
                        for ext_link in self._extract_ids_from_urls([url]):
                            ext_pair = (ext_link["provider"], ext_link["external_id"])
                            if ext_pair not in processed_pairs:
                                to_process.append(ext_link)
                                result["links_to_create"].append(ext_link)

                        # Extract socials dynamically using regex patterns
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

        existing_providers = {l["provider"] for l in links}
        for prov_name, ext_id in external_ids.items():
            try:
                prov = Provider(prov_name)
                if prov not in existing_providers:
                    result["links_to_create"].append({"provider": prov, "external_id": str(ext_id)})
            except ValueError:
                pass

        return result if has_data else None

    def _extract_ids_from_urls(self, urls: List[str]) -> List[dict]:
        import re
        links = []
        for url in urls:
            if not url or not isinstance(url, str):
                continue
            # PornDB: https://theporndb.net/performers/<uuid>
            match_porndb = re.search(r'theporndb\.net/performers/([a-fA-F0-9\-]+)', url)
            if match_porndb:
                links.append({"provider": Provider.PORNDB, "external_id": match_porndb.group(1)})
                continue
                
            # FansDB: https://fansdb.cc/performers/<uuid>
            match_fansdb = re.search(r'fansdb\.cc/performers/([a-fA-F0-9\-]+)', url)
            if match_fansdb:
                links.append({"provider": Provider.FANSDB, "external_id": match_fansdb.group(1)})
                continue
                
            # StashDB: https://stashdb.org/performers/<uuid>
            match_stashdb = re.search(r'stashdb\.org/performers/([a-fA-F0-9\-]+)', url)
            if match_stashdb:
                links.append({"provider": Provider.STASHDB, "external_id": match_stashdb.group(1)})
                continue
                
            # TMDB: https://www.themoviedb.org/person/(\d+)
            match_tmdb = re.search(r'themoviedb\.org/person/(\d+)', url)
            if match_tmdb:
                links.append({"provider": Provider.TMDB, "external_id": match_tmdb.group(1)})
                continue
                
        return links

    def apply_enriched_data(self, person: Person, data: dict):
        from app.domains.tasks import task_manager
        if data.get("birthday"):
            person.birthday = data["birthday"]
        if data.get("deathday"):
            person.deathday = data["deathday"]
        if data.get("place_of_birth"):
            person.place_of_birth = data["place_of_birth"]
        if data.get("known_for_department"):
            person.known_for_department = data["known_for_department"]
        if data.get("homepage"):
            person.homepage = data["homepage"]
        if data.get("gender") is not None:
            person.gender = data["gender"]
        if data.get("popularity") is not None:
            person.popularity = data["popularity"]
        if data.get("rating_porndb") is not None:
            person.rating_porndb = float(data["rating_porndb"])
        if data.get("scene_count") is not None:
            person.scene_count = max(person.scene_count or 0, int(data["scene_count"]))
        if data.get("ethnicity"):
            person.ethnicity = data["ethnicity"]
        if data.get("hair_color"):
            person.hair_color = data["hair_color"]
        if data.get("eye_color"):
            person.eye_color = data["eye_color"]
        if data.get("height") is not None:
            person.height = data["height"]
        if data.get("measurements"):
            person.measurements = data["measurements"]
        if data.get("cup_size"):
            person.cup_size = data["cup_size"]
            
        # Save extended performer attributes
        if data.get("weight") is not None:
            person.weight = data["weight"]
        if data.get("aliases"):
            existing_aliases = person.aliases or []
            person.aliases = list(set(existing_aliases + data["aliases"]))
        if data.get("tattoos"):
            person.tattoos = data["tattoos"]
        if data.get("piercings"):
            person.piercings = data["piercings"]
        if data.get("orientation"):
            person.orientation = data["orientation"]
        if data.get("career_start_year") is not None:
            person.career_start_year = data["career_start_year"]
        if data.get("career_end_year") is not None:
            person.career_end_year = data["career_end_year"]
        if data.get("socials"):
            existing_socials = person.socials or {}
            existing_socials.update(data["socials"])
            person.socials = existing_socials

        if data.get("urls"):
            ids = person.external_ids or {}
            existing_urls = ids.get("urls") or []
            existing_urls_set = {u.get("url") if isinstance(u, dict) else u for u in existing_urls}
            for new_url in data["urls"]:
                url_str = new_url.get("url") if isinstance(new_url, dict) else new_url
                if url_str and url_str not in existing_urls_set:
                    existing_urls.append({"url": url_str})
                    existing_urls_set.add(url_str)
            ids["urls"] = existing_urls
            person.external_ids = ids

        for l in data["links_to_create"]:
            link = self.db.query(ExternalSourceLink).filter(
                ExternalSourceLink.person_id == person.id,
                ExternalSourceLink.provider == l["provider"],
                ExternalSourceLink.external_id == l["external_id"]
            ).first()
            if not link:
                new_link = ExternalSourceLink(
                    person_id=person.id,
                    provider=l["provider"],
                    external_id=l["external_id"]
                )
                self.db.add(new_link)

        for locale, bio in data["biographies"].items():
            self._save_bio(person.id, locale, bio)

        profile_path = data.get("profile_path")
        if profile_path:
            person.profile_path = profile_path
            tmdb_id = person.external_ids.get("tmdb") if person.external_ids else None
            
            from app.domains.media_assets.services.images import image_processing_service
            url = image_processing_service.get_download_url(profile_path, "people") or profile_path
            
            if tmdb_id:
                import os
                clean_path = os.path.basename(profile_path)
                filename = f"tmdb_{tmdb_id}_{clean_path}"
            else:
                import os
                ext = os.path.splitext(profile_path)[1] or ".jpg"
                ext_id = "unknown"
                prov_val = "perf"
                if person.external_ids:
                    for k, v in person.external_ids.items():
                        prov_val = k
                        ext_id = v
                        break
                filename = f"{prov_val}_{ext_id}{ext}"

            existing_imgs = person.images or []
            new_imgs = data.get("images") or []
            seen = set()
            res_list = []
            for img in existing_imgs:
                if not img:
                    continue
                norm = img.split("/")[-1].split("?")[0].lower()
                if norm not in seen:
                    seen.add(norm)
                    res_list.append(img)
            for img in new_imgs:
                if not img:
                    continue
                norm = img.split("/")[-1].split("?")[0].lower()
                if norm not in seen:
                    seen.add(norm)
                    res_list.append(img)
            person.images = res_list

            task_manager.download_worker.enqueue_download(url, "people", filename)

    def _save_bio(self, person_id: int, locale: str, biography: str):
        loc = self.db.query(PersonLocalization).filter(
            PersonLocalization.person_id == person_id,
            PersonLocalization.locale == locale
        ).first()
        if not loc:
            loc = PersonLocalization(person_id=person_id, locale=locale, biography=biography)
            self.db.add(loc)
        else:
            loc.biography = biography
