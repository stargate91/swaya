import logging
import os
import re
from urllib.parse import urlparse
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization, Studio, MediaCollection
from app.shared_kernel.enums import Provider, MediaType, RoleType
from app.domains.people.models import MediaPersonLink
from app.domains.people.services import PersonService
from app.infrastructure.scrapers.tmdb import TMDBScraper
from app.infrastructure.scrapers.omdb import OMDBScraper
from app.shared_kernel.language import LanguageService

logger = logging.getLogger(__name__)

tv_enrich_lock = threading.Lock()

def _pick_backdrop_path(raw_data) -> Optional[str]:
    images = raw_data.get("images") or {}
    backdrops = images.get("backdrops") or []
    if not backdrops:
        return raw_data.get("backdrop_path")

    neutral_backdrops = [bd for bd in backdrops if bd.get("iso_639_1") in (None, "")]
    candidates = neutral_backdrops or backdrops

    def score(bd):
        return (
            int(bd.get("width") or 0),
            int(bd.get("height") or 0),
            float(bd.get("vote_average") or 0),
            int(bd.get("vote_count") or 0),
        )

    sorted_bd = sorted(candidates, key=score, reverse=True)
    return sorted_bd[0].get("file_path") or raw_data.get("backdrop_path")

def _pick_logo_path(raw_data, language: str = None) -> Optional[str]:
    images = raw_data.get("images") or {}
    logos = images.get("logos") or []
    if not logos:
        return None
    lang_pref = [language, DEFAULT_FALLBACK_LANGUAGE, None, ""]
    def score(lg):
        lg_lang = lg.get("iso_639_1")
        try:
            lang_idx = lang_pref.index(lg_lang)
        except ValueError:
            lang_idx = 999
        return (
            -lang_idx,
            int(lg.get("vote_count") or 0),
            float(lg.get("vote_average") or 0)
        )
    sorted_lg = sorted(logos, key=score, reverse=True)
    return sorted_lg[0].get("file_path")

from app.shared_kernel.constants import YOUTUBE_WATCH_BASE, DEFAULT_FALLBACK_LANGUAGE

def _pick_trailer_key(raw_data, language: str = None, original_language: str = None) -> Optional[str]:
    videos = (raw_data.get("videos") or {}).get("results") or []
    if not videos:
        return None
    youtube_videos = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
    if not youtube_videos:
        youtube_videos = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
    if not youtube_videos:
        return None
    lang_pref = [language, DEFAULT_FALLBACK_LANGUAGE, original_language]
    def score(v):
        v_lang = v.get("iso_639_1")
        try:
            lang_idx = lang_pref.index(v_lang)
        except ValueError:
            lang_idx = 999
        return -lang_idx
    sorted_v = sorted(youtube_videos, key=score, reverse=True)
    key = sorted_v[0].get("key")
    return f"{YOUTUBE_WATCH_BASE}{key}" if key else None

class MainstreamEnricher:
    """
    Mainstream enricher that queries TMDB/OMDB and populates full localization,
    studios, collection details, and links cast/crew.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.api = TMDBScraper(db_session)
        self.omdb = OMDBScraper(db_session)
        self._details_cache: Dict[tuple[str, int, str], Dict[str, Any]] = {}
        self._episode_cache: Dict[tuple[int, int, int, str], Dict[str, Any]] = {}
        self._omdb_cache: Dict[str, Dict[str, Any]] = {}

    def enrich_matched_item(
        self,
        item: MediaItem,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        fallback_language: str = None,
        include_ratings: bool = True,
        commit: bool = False,
    ):
        """Fetches and stores complete metadata for the active match."""
        active_match = self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id
        ).first()

        if not active_match:
            return

        # Build unique list of languages to enrich
        langs_to_enrich = []
        if language:
            langs_to_enrich.append(language)
        if fallback_language:
            langs_to_enrich.append(fallback_language)

        # Retrieve target language and overrides so they are also cached in the DB
        try:
            from app.domains.settings.models import UserSetting, SystemSetting
            if item.overrides and item.overrides.custom_language:
                langs_to_enrich.append(item.overrides.custom_language)
            
            follow_s = self.db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "follow_app_language_for_naming").first()
            if not follow_s:
                follow_s = self.db.query(SystemSetting).filter(SystemSetting.key == "follow_app_language_for_naming").first()
            follow_naming = follow_s.value if follow_s else True
            
            t_lang = None
            if follow_naming:
                ui_s = self.db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "ui_language").first()
                if not ui_s:
                    ui_s = self.db.query(SystemSetting).filter(SystemSetting.key == "ui_language").first()
                if ui_s and ui_s.value:
                    t_lang = ui_s.value
            else:
                target_s = self.db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "default_target_language").first()
                if not target_s:
                    target_s = self.db.query(SystemSetting).filter(SystemSetting.key == "default_target_language").first()
                if target_s and target_s.value:
                    t_lang = target_s.value
            
            if t_lang:
                langs_to_enrich.append(t_lang)
        except Exception as lang_ex:
            logger.warning(f"Failed to load target language for enrichment: {lang_ex}")

        unique_langs = []
        for raw_language in langs_to_enrich:
            language = LanguageService.resolve_request_locale(Provider.TMDB, raw_language)
            if language and language not in unique_langs:
                unique_langs.append(language)

        for idx, lang in enumerate(unique_langs):
            inc_rat = include_ratings if idx == 0 else False
            if active_match.media_type == MediaType.MOVIE:
                self._enrich_movie(active_match, lang, include_ratings=inc_rat)
            elif active_match.media_type == MediaType.TV or active_match.media_type == MediaType.EPISODE:
                self._enrich_tv(active_match, lang, include_ratings=inc_rat)

        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def _enrich_movie(self, match: MetadataMatch, language: str, include_ratings: bool = True):
        details = self._get_details_cached(int(match.external_id), "movie", language)
        if not details:
            return

        self._update_match_common(match, details, include_ratings=include_ratings)
        match.is_adult = details.get("adult", False)
        match.release_status = details.get("status")
        match.budget = details.get("budget")
        match.revenue = details.get("revenue")

        # Collection details
        coll = details.get("belongs_to_collection")
        if coll:
            coll_id = str(coll["id"])
            collection = self.db.query(MediaCollection).filter(
                MediaCollection.provider == Provider.TMDB,
                MediaCollection.external_id == coll_id
            ).first()
            if not collection:
                collection = MediaCollection(
                    provider=Provider.TMDB,
                    external_id=coll_id,
                    backdrop_path=coll.get("backdrop_path")
                )
                self.db.add(collection)
            match.collection = collection
            
        selected_backdrop_path = _pick_backdrop_path(details)
        if selected_backdrop_path:
            match.backdrop_path = selected_backdrop_path

        # Localization
        loc = self._get_or_create_loc(match, language)
        loc.title = details.get("title") or details.get("original_title") or "Unknown"
        loc.overview = details.get("overview")
        loc.tagline = details.get("tagline")
        loc.poster_path = details.get("poster_path")
        loc.logo_path = _pick_logo_path(details, language)
        localized_asset_prefix = f"tmdb_movie_{match.external_id}_{language}"
        match.local_backdrop_path = self._queue_image(
            match.backdrop_path,
            "backdrops",
            f"tmdb_movie_{match.external_id}",
        )
        loc.local_poster_path = self._queue_image(loc.poster_path, "posters", localized_asset_prefix)
        loc.local_logo_path = self._queue_image(loc.logo_path, "logos", localized_asset_prefix)
        loc.genres = [g["name"] for g in details.get("genres") or []]
        loc.original_language = details.get("original_language")

        # Trailer
        loc.trailer_url = _pick_trailer_key(details, language, details.get("original_language"))

    def _enrich_tv(self, match: MetadataMatch, language: str, include_ratings: bool = True):
        # A. TV SHOW LEVEL
        tv_details = self._get_details_cached(int(match.external_id), "tv", language)
        if not tv_details:
            return

        with tv_enrich_lock:
            # Query or create the TV Show match (shared, so media_item_id is None)
            tv_match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == match.provider,
                MetadataMatch.external_id == match.external_id,
                MetadataMatch.media_type == MediaType.TV,
                MetadataMatch.media_item_id.is_(None)
            ).first()
            if not tv_match:
                tv_match = MetadataMatch(
                    provider=match.provider,
                    external_id=match.external_id,
                    media_type=MediaType.TV,
                    confidence_score=1.0,
                    media_item_id=None
                )
                try:
                    with self.db.begin_nested():
                        self.db.add(tv_match)
                except Exception:
                    tv_match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == match.provider,
                        MetadataMatch.external_id == match.external_id,
                        MetadataMatch.media_type == MediaType.TV,
                        MetadataMatch.media_item_id.is_(None)
                    ).first()

            self._update_match_common(tv_match, tv_details, include_ratings=include_ratings)
            tv_match.is_adult = tv_details.get("adult", False)
            tv_match.release_status = tv_details.get("status")
            tv_match.tv_type = tv_details.get("type")
            tv_match.number_of_seasons = tv_details.get("number_of_seasons")
            tv_match.number_of_episodes = tv_details.get("number_of_episodes")

            tv_first_air_date = tv_details.get("first_air_date")
            if tv_first_air_date:
                try:
                    tv_match.first_air_date = datetime.strptime(tv_first_air_date, "%Y-%m-%d")
                except:
                    pass
            tv_last_air_date = tv_details.get("last_air_date")
            if tv_last_air_date:
                try:
                    tv_match.last_air_date = datetime.strptime(tv_last_air_date, "%Y-%m-%d")
                except:
                    pass

            selected_backdrop_path = _pick_backdrop_path(tv_details)
            if selected_backdrop_path:
                tv_match.backdrop_path = selected_backdrop_path
            
            tv_loc = self._get_or_create_loc(tv_match, language)
            tv_loc.title = tv_details.get("name") or tv_details.get("original_name") or "Unknown"
            tv_loc.overview = tv_details.get("overview")
            tv_loc.poster_path = tv_details.get("poster_path")
            tv_loc.logo_path = _pick_logo_path(tv_details, language)
            tv_loc.genres = [g["name"] for g in tv_details.get("genres") or []]
            tv_loc.original_language = tv_details.get("original_language")
            tv_loc.trailer_url = _pick_trailer_key(tv_details, language, tv_details.get("original_language"))

            localized_asset_prefix = f"tmdb_tv_{tv_match.external_id}_{language}"
            tv_match.local_backdrop_path = self._queue_image(
                tv_match.backdrop_path,
                "backdrops",
                f"tmdb_tv_{tv_match.external_id}",
            )
            tv_loc.local_poster_path = self._queue_image(tv_loc.poster_path, "posters", localized_asset_prefix)
            tv_loc.local_logo_path = self._queue_image(tv_loc.logo_path, "logos", localized_asset_prefix)

        # B. SEASON LEVEL
        season_match = None
        if match.season_number is not None:
            with tv_enrich_lock:
                season_match = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == match.provider,
                    MetadataMatch.parent_id == tv_match.id,
                    MetadataMatch.media_type == MediaType.SEASON,
                    MetadataMatch.season_number == match.season_number,
                    MetadataMatch.media_item_id.is_(None)
                ).first()
                if not season_match:
                    season_match = MetadataMatch(
                        provider=match.provider,
                        external_id=f"{match.external_id}-s{match.season_number}",
                        media_type=MediaType.SEASON,
                        season_number=match.season_number,
                        parent_id=tv_match.id,
                        confidence_score=1.0,
                        media_item_id=None
                    )
                    try:
                        with self.db.begin_nested():
                            self.db.add(season_match)
                    except Exception:
                        season_match = self.db.query(MetadataMatch).filter(
                            MetadataMatch.provider == match.provider,
                            MetadataMatch.parent_id == tv_match.id,
                            MetadataMatch.media_type == MediaType.SEASON,
                            MetadataMatch.season_number == match.season_number,
                            MetadataMatch.media_item_id.is_(None)
                        ).first()

                seasons = tv_details.get("seasons", [])
                season_data = next((s for s in seasons if s.get("season_number") is not None and int(s.get("season_number")) == int(match.season_number)), None)
                
                if season_data:
                    season_match.number_of_episodes = season_data.get("episode_count")
                    season_loc = self._get_or_create_loc(season_match, language)
                    season_loc.title = season_data.get("name") or f"Season {match.season_number}"
                    season_loc.overview = season_data.get("overview")
                    if season_data.get("poster_path"):
                        season_loc.poster_path = season_data.get("poster_path")
                    season_loc.local_poster_path = self._queue_image(
                        season_loc.poster_path,
                        "posters",
                        f"tmdb_tv_{match.external_id}_s{match.season_number}_{language}",
                    )
                    if tv_match.release_date:
                        season_match.release_date = tv_match.release_date

        # C. EPISODE LEVEL
        if match.season_number is not None and match.episode_number is not None:
            if season_match:
                match.parent_id = season_match.id
            else:
                match.parent_id = tv_match.id

            ep_nums = []
            raw_ep = match.episode_number
            if isinstance(raw_ep, list):
                ep_nums = raw_ep
            else:
                ep_nums = [raw_ep]

            titles = []
            overviews = []
            all_stills = []
            first_still = None
            first_air_date = None
            
            for ename in ep_nums:
                try:
                    ep_details = self._get_episode_details_cached(
                        int(match.external_id), match.season_number, int(ename), language=language
                    )
                    if ep_details:
                        titles.append(ep_details.get("name") or f"Episode {ename}")
                        if ep_details.get("overview"):
                            overviews.append(ep_details.get("overview"))
                        
                        s_path = ep_details.get("still_path")
                        if s_path:
                            all_stills.append(s_path)
                            if not first_still:
                                first_still = s_path
                                
                        if not first_air_date:
                            first_air_date = ep_details.get("air_date")
                            
                        if ename == ep_nums[0]:
                            match.rating_tmdb = ep_details.get("vote_average")
                            match.vote_count_tmdb = ep_details.get("vote_count")
                            match.runtime = ep_details.get("runtime") or match.runtime
                except Exception as e:
                    logger.warning(f"Failed to fetch metadata for episode {ename}: {e}")

            loc = self._get_or_create_loc(match, language)
            if titles:
                loc.title = " / ".join(titles)
                match.still_path = first_still
                match.stills = all_stills
                still_prefix = f"tmdb_tv_{match.external_id}_s{match.season_number}_e{ep_nums[0]}"
                match.local_stills = [
                    local_path
                    for index, still_path in enumerate(all_stills)
                    if (local_path := self._queue_image(still_path, "stills", f"{still_prefix}_{index}"))
                ]
                match.local_still_path = match.local_stills[0] if match.local_stills else None
                if overviews:
                    loc.overview = "\n\n".join(overviews)
                
                if first_air_date:
                    try:
                        match.release_date = datetime.strptime(first_air_date, "%Y-%m-%d")
                    except:
                        pass
                
                match.media_type = MediaType.EPISODE

    def _queue_image(self, path: Optional[str], subfolder: str, prefix: str) -> Optional[str]:
        if not path:
            return None

        from app.domains.tasks import task_manager

        image_service = task_manager.download_worker.image_service
        url = image_service.get_download_url(path, subfolder)
        if not url:
            return None

        basename = os.path.basename(urlparse(path).path)
        if not basename:
            return None
        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
        filename = f"{safe_prefix}_{basename}"
        task_manager.download_worker.enqueue_download(url, subfolder, filename)
        return f"{subfolder}/{filename}"

    def _update_match_common(self, match: MetadataMatch, details: Dict[str, Any], include_ratings: bool = True):
        runtimes = details.get("episode_run_time", [])
        match.runtime = details.get("runtime") or (runtimes[0] if runtimes else None)
        match.popularity = details.get("popularity")
        match.rating_tmdb = details.get("vote_average")
        match.vote_count_tmdb = details.get("vote_count")
        
        release_date = details.get("release_date") or details.get("first_air_date")
        if release_date:
            try:
                match.release_date = datetime.strptime(release_date, "%Y-%m-%d")
            except Exception:
                pass
        
        ext_ids = details.get("external_ids", {})
        imdb_id = ext_ids.get("imdb_id") or match.imdb_id
        match.imdb_id = imdb_id

        match.original_language = details.get("original_language")
        match.origin_country = details.get("origin_country")
        spoken = details.get("spoken_languages", [])
        if spoken:
            match.spoken_languages = [s["iso_639_1"] for s in spoken]

        # Studios mapping
        for comp in details.get("production_companies") or []:
            s_name = comp.get("name")
            if s_name:
                studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                if not studio:
                    studio = Studio(name=s_name, logo_path=comp.get("logo_path"))
                    self.db.add(studio)
                if studio not in match.studios:
                    match.studios.append(studio)

        # OMDb Ratings
        if include_ratings and imdb_id:
            omdb_data = self._get_omdb_ratings_cached(imdb_id)
            if omdb_data:
                self.omdb.update_omdb_ratings(match, omdb_data)

        # Cast/Crew processing
        self._process_people(match, details)

    def _process_people(self, match: MetadataMatch, details: Dict[str, Any]):
        credits = details.get("aggregate_credits", {}) if match.media_type != MediaType.MOVIE else details.get("credits", {})
        if not credits or not credits.get("cast"):
            credits = details.get("credits", {})
            
        cast = credits.get("cast", [])[:15]
        crew = credits.get("crew", [])
        
        person_service = PersonService(self.db)
        
        # Link Actors
        for idx, cast_member in enumerate(cast):
            person = person_service.update_or_create_person(
                name=cast_member["name"],
                profile_path=cast_member.get("profile_path"),
                gender=cast_member.get("gender"),
                is_adult=cast_member.get("adult", False),
                tmdb_id=str(cast_member["id"])
            )
            
            link = self.db.query(MediaPersonLink).filter(
                MediaPersonLink.match_id == match.id if match.id else False,
                MediaPersonLink.person_id == person.id if person.id else False,
                MediaPersonLink.role == RoleType.ACTOR
            ).first()
            
            if not link:
                link = MediaPersonLink(
                    role=RoleType.ACTOR,
                    character_name=cast_member.get("character") or (cast_member.get("roles", [{}])[0].get("character") if "roles" in cast_member else None),
                    order=idx
                )
                link.person = person
                match.people.append(link)

        # Link Directors
        directors = [p for p in crew if p.get("job") == "Director"][:2]
        for idx, dir_member in enumerate(directors):
            person = person_service.update_or_create_person(
                name=dir_member["name"],
                profile_path=dir_member.get("profile_path"),
                gender=dir_member.get("gender"),
                is_adult=dir_member.get("adult", False),
                tmdb_id=str(dir_member["id"])
            )
            
            link = self.db.query(MediaPersonLink).filter(
                MediaPersonLink.match_id == match.id if match.id else False,
                MediaPersonLink.person_id == person.id if person.id else False,
                MediaPersonLink.role == RoleType.DIRECTOR
            ).first()
            
            if not link:
                link = MediaPersonLink(
                    role=RoleType.DIRECTOR,
                    order=idx
                )
                link.person = person
                match.people.append(link)

    def _get_or_create_loc(self, match: MetadataMatch, language: str) -> MetadataLocalization:
        language = LanguageService.resolve_request_locale(Provider.TMDB, language) or DEFAULT_FALLBACK_LANGUAGE
        equivalent_localizations = [
            loc for loc in match.localizations
            if LanguageService.resolve_request_locale(Provider.TMDB, loc.locale) == language
        ]
        if equivalent_localizations:
            loc = next((item for item in equivalent_localizations if item.locale == language), equivalent_localizations[0])
            loc.locale = language
            for duplicate in equivalent_localizations:
                if duplicate is not loc:
                    match.localizations.remove(duplicate)
            return loc
        loc = self.db.query(MetadataLocalization).filter(
            MetadataLocalization.match_id == match.id if match.id else False,
            MetadataLocalization.locale == language
        ).first()
        if not loc:
            loc = MetadataLocalization(locale=language)
            match.localizations.append(loc)
        return loc

    def _get_details_cached(self, tmdb_id: int, item_type: str, language: str) -> Dict[str, Any]:
        cache_key = (item_type, tmdb_id, language)
        if cache_key not in self._details_cache:
            try:
                self._details_cache[cache_key] = self.api.get_details(tmdb_id, item_type=item_type, language=language) or {}
            except Exception as e:
                logger.error(f"Failed to fetch details for {item_type} {tmdb_id}: {e}")
                self._details_cache[cache_key] = {}
        return self._details_cache[cache_key]

    def _get_episode_details_cached(self, tv_id: int, season_number: int, episode_number: int, language: str) -> Dict[str, Any]:
        cache_key = (tv_id, season_number, episode_number, language)
        if cache_key not in self._episode_cache:
            try:
                self._episode_cache[cache_key] = self.api.get_episode_details(
                    tv_id,
                    season_number,
                    episode_number,
                    language=language,
                ) or {}
            except Exception as e:
                logger.error(f"Failed to fetch episode details for TV {tv_id} S{season_number}E{episode_number}: {e}")
                self._episode_cache[cache_key] = {}
        return self._episode_cache[cache_key]

    def _get_omdb_ratings_cached(self, imdb_id: str) -> Dict[str, Any]:
        if imdb_id not in self._omdb_cache:
            self._omdb_cache[imdb_id] = self.omdb.fetch_omdb(imdb_id) or {}
        return self._omdb_cache[imdb_id]
