import re
import unicodedata
from typing import List, Dict, Any, Set, Optional
from sqlalchemy.orm import Session
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.settings.models import SystemSetting, UserSetting
from app.shared_kernel.enums import Provider, MediaType, ItemStatus, ScanMode

def _has_episode_value(episode) -> bool:
    if isinstance(episode, list):
        return len(episode) > 0
    return episode not in (None, "")

def determine_resolved_media_shape(media_kind: Any, season=None, episode=None):
    if media_kind in (MediaType.MOVIE, "movie"):
        return MediaType.MOVIE, ItemStatus.MATCHED
    if media_kind in (MediaType.SCENE, "scene"):
        return MediaType.SCENE, ItemStatus.MATCHED
    if media_kind in (MediaType.JAV, "jav"):
        return MediaType.JAV, ItemStatus.MATCHED

    has_season = season not in (None, "")
    has_episode = _has_episode_value(episode)

    if has_season and has_episode:
        return MediaType.EPISODE, ItemStatus.MATCHED
    
    return MediaType.EPISODE, ItemStatus.UNCERTAIN

def normalize_title(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", normalized.lower())

def normalize_title_words(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", normalized.lower()))


from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

class Resolver:
    """
    Dispatcher facade that delegates resolution to MainstreamResolver or AdultResolver.
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        from app.infrastructure.scrapers.mainstream_resolver import MainstreamResolver
        from app.infrastructure.scrapers.adult_resolver import AdultResolver
        from app.infrastructure.scrapers.porndb_movie_resolver import PornDBMovieResolver
        self.mainstream = MainstreamResolver(db_session)
        self.adult = AdultResolver(db_session)
        self.porndb_movies = PornDBMovieResolver(db_session)

    def resolve_item(
        self,
        item: MediaItem,
        mode: ScanMode = ScanMode.MOVIES_TV,
        language: str = DEFAULT_FALLBACK_LANGUAGE,
        task_id: Optional[int] = None,
        include_adult: Optional[bool] = None,
    ):
        """Resolves MediaItem search candidates and populates matches."""
        if mode.uses_scene_pipeline:
            self._resolve_adult_item(item, mode, task_id)
            return

        if include_adult is None:
            include_adult = self._adult_access_enabled()
        if include_adult and self.porndb_movies.resolve_hash(item, task_id):
            return

        self.mainstream.resolve_item(
            item,
            language,
            task_id,
            include_adult=include_adult,
        )
        if include_adult and item.status != ItemStatus.MATCHED:
            self.porndb_movies.resolve_text(item, task_id)

    def _adult_access_enabled(self, user_id: int = 1) -> bool:
        setting = self.db.query(UserSetting).filter(
            UserSetting.user_id == user_id,
            UserSetting.key == "include_adult",
        ).first()
        if not setting:
            setting = self.db.query(SystemSetting).filter(
                SystemSetting.key == "include_adult"
            ).first()
        return str(setting.value).strip().lower() in ("true", "1") if setting else False

    def _resolve_adult_item(self, item: MediaItem, mode: ScanMode, task_id: Optional[int] = None):
        """Resolves adult items by delegating to AdultResolver."""
        self.adult.resolve_adult_item(item, mode, task_id)

    def propagate_match(self, source_item: MediaItem):
        """
        Copies the active match to other files sharing the same group_hash.
        """
        if not source_item.group_hash:
            return

        active_match = self.db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == source_item.id
        ).first()

        if not active_match:
            return

        # Find other files with the same group hash
        siblings = self.db.query(MediaItem).filter(
            MediaItem.group_hash == source_item.group_hash,
            MediaItem.id != source_item.id
        ).all()

        for sib in siblings:
            # Delete old matches
            self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == sib.id).delete()
            
            # Create new match
            parsed = sib.parsed_info or {}
            fn_data = parsed.get("fn") or {}
            it_data = parsed.get("it") or {}
            fd_data = parsed.get("fd") or {}
            
            s_num = fn_data.get("season") or it_data.get("season") or fd_data.get("season") or active_match.season_number
            ep_num = fn_data.get("episode") or it_data.get("episode") or fd_data.get("episode") or active_match.episode_number

            new_match = MetadataMatch(
                media_item_id=sib.id,
                provider=active_match.provider,
                external_id=active_match.external_id,
                media_type=active_match.media_type,
                season_number=s_num,
                episode_number=ep_num,
                release_date=active_match.release_date,
                last_air_date=active_match.last_air_date,
                confidence_score=active_match.confidence_score,
                rating_tmdb=active_match.rating_tmdb,
                rating_porndb=active_match.rating_porndb,
                is_adult=active_match.is_adult,
                original_title=active_match.original_title,
                runtime=active_match.runtime,
                suggested_tags=active_match.suggested_tags,
                raw_metadata=active_match.raw_metadata,
                vote_count_tmdb=active_match.vote_count_tmdb,
                backdrop_path=active_match.backdrop_path,
                local_backdrop_path=active_match.local_backdrop_path,
                still_path=active_match.still_path,
                local_still_path=active_match.local_still_path,
                stills=active_match.stills,
                local_stills=active_match.local_stills,
            )
            self.db.add(new_match)
            self.db.flush()

            # Copy localizations
            for loc in active_match.localizations:
                new_loc = MetadataLocalization(
                    match_id=new_match.id,
                    locale=loc.locale,
                    title=loc.title,
                    tagline=loc.tagline,
                    overview=loc.overview,
                    poster_path=loc.poster_path,
                    genres=loc.genres
                )
                self.db.add(new_loc)
            
            _, sib_status = determine_resolved_media_shape(
                new_match.media_type,
                new_match.season_number,
                new_match.episode_number
            )
            sib.status = sib_status
        
        self.db.flush()
