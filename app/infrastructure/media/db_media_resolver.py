from typing import Tuple, Optional, Dict, Any
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.ports.media_resolver import MediaResolverPort
from app.shared_kernel.ports.library_port import LibraryPort

# Specialized Adapters
from app.infrastructure.media.adapters.db_media_item_adapter import DbMediaItemAdapter
from app.infrastructure.media.adapters.db_rename_adapter import DbRenameAdapter
from app.infrastructure.media.adapters.db_scan_adapter import DbScanAdapter
from app.infrastructure.media.adapters.db_person_override_adapter import DbPersonOverrideAdapter
from app.infrastructure.media.adapters.db_playback_adapter import DbPlaybackAdapter
from app.infrastructure.media.adapters.db_collection_adapter import DbCollectionAdapter

logger = logging.getLogger(__name__)

class DbMediaResolver(
    MediaResolverPort,
    LibraryPort,
    DbMediaItemAdapter,
    DbRenameAdapter,
    DbScanAdapter,
    DbPersonOverrideAdapter,
    DbPlaybackAdapter,
    DbCollectionAdapter
):
    def __init__(self, db: Session):
        self.db = db

    def resolve_ids(self, item_id: str, media_type: Optional[str] = None) -> Tuple[Optional[int], Optional[int]]:
        media_item_id = None
        metadata_match_id = None

        if isinstance(item_id, str) and item_id.startswith("tmdb_"):
            parts = item_id.split("_")
            if len(parts) >= 4:
                # TV Episode format: tmdb_{tv_id}_{season}_{episode}
                tv_id = parts[1]
                season_num = int(parts[2])
                episode_num = int(parts[3])
                
                # 1. TV show match
                tv_match = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == Provider.TMDB,
                    MetadataMatch.external_id == tv_id,
                    MetadataMatch.media_type == MediaType.TV
                ).first()
                if not tv_match:
                    tv_match = MetadataMatch(provider=Provider.TMDB, external_id=tv_id, media_type=MediaType.TV)
                    self.db.add(tv_match)
                    self.db.flush()
                
                # 2. Season match
                season_match = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == Provider.TMDB,
                    MetadataMatch.parent_id == tv_match.id,
                    MetadataMatch.media_type == MediaType.SEASON,
                    MetadataMatch.season_number == season_num
                ).first()
                if not season_match:
                    season_match = MetadataMatch(
                        provider=Provider.TMDB,
                        external_id=f"{tv_id}-s{season_num}",
                        media_type=MediaType.SEASON,
                        season_number=season_num,
                        parent_id=tv_match.id
                    )
                    self.db.add(season_match)
                    self.db.flush()
                
                # 3. Episode match
                all_season_episodes = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == Provider.TMDB,
                    MetadataMatch.parent_id == season_match.id,
                    MetadataMatch.media_type == MediaType.EPISODE
                ).all()
                
                episode_match = None
                for m in all_season_episodes:
                    if m.episode_number == episode_num:
                        episode_match = m
                        break
                    elif isinstance(m.episode_number, list) and episode_num in m.episode_number:
                        episode_match = m
                        break
                    elif isinstance(m.episode_number, str):
                        import json
                        try:
                            parsed_ep = json.loads(m.episode_number)
                            if isinstance(parsed_ep, list) and episode_num in parsed_ep:
                                episode_match = m
                                break
                            elif parsed_ep == episode_num:
                                episode_match = m
                                break
                        except:
                            if str(episode_num) == m.episode_number:
                                episode_match = m
                                break
                if not episode_match:
                    episode_match = MetadataMatch(
                        provider=Provider.TMDB,
                        external_id=tv_id,
                        media_type=MediaType.EPISODE,
                        season_number=season_num,
                        episode_number=episode_num,
                        parent_id=season_match.id
                    )
                    self.db.add(episode_match)
                    self.db.flush()
                
                metadata_match_id = episode_match.id
                media_item_id = episode_match.media_item_id
            else:
                tmdb_id = parts[1]
                query = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == Provider.TMDB,
                    MetadataMatch.external_id == tmdb_id
                )
                if media_type:
                    try:
                        resolved_type = MediaType(media_type.lower())
                    except ValueError:
                        resolved_type = MediaType.TV if media_type.lower() == 'tv' else MediaType.MOVIE
                    query = query.filter(MetadataMatch.media_type == resolved_type)
                
                match = query.first()
                if not match:
                    resolved_type = MediaType.MOVIE
                    if media_type:
                        try:
                            resolved_type = MediaType(media_type.lower())
                        except ValueError:
                            if media_type.lower() == 'tv':
                                resolved_type = MediaType.TV
                    # Create a placeholder match record to link the override to
                    match = MetadataMatch(provider=Provider.TMDB, external_id=tmdb_id, media_type=resolved_type, is_adult=False)
                    self.db.add(match)
                    self.db.flush()
                metadata_match_id = match.id
                media_item_id = match.media_item_id
        elif isinstance(item_id, str) and "_" in item_id and item_id.split("_", 1)[0].lower() in ("scene", "stash", "stashdb", "fansdb", "porndb", "theporndb"):
            parts = item_id.split("_", 1)
            provider_prefix = parts[0].lower()
            scene_id = parts[1]
            
            provider = Provider.STASHDB
            if provider_prefix == "scene":
                provider = Provider.STASHDB
            elif provider_prefix == "fansdb":
                provider = Provider.FANSDB
            elif provider_prefix in ("porndb", "theporndb"):
                provider = Provider.PORNDB
                
            resolved_media_type = MediaType.SCENE
            if media_type:
                try:
                    resolved_media_type = MediaType(media_type.lower())
                except ValueError:
                    if media_type.lower() == 'movie':
                        resolved_media_type = MediaType.MOVIE
                    elif media_type.lower() == 'tv':
                        resolved_media_type = MediaType.TV

            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == provider,
                MetadataMatch.external_id == scene_id,
                MetadataMatch.media_type == resolved_media_type
            ).first()
            if not match:
                match = MetadataMatch(
                    provider=provider, 
                    external_id=scene_id, 
                    media_type=resolved_media_type,
                    is_adult=True
                )
                self.db.add(match)
                self.db.flush()
            metadata_match_id = match.id
            media_item_id = match.media_item_id
        else:
            try:
                media_item_id = int(item_id)
            except ValueError:
                # Fallback check if it is a pure tmdb string id passed directly
                match = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == Provider.TMDB,
                    MetadataMatch.external_id == str(item_id)
                ).first()
                if match:
                    metadata_match_id = match.id
                else:
                    return None, None

        return media_item_id, metadata_match_id

    def update_item_status(self, item_id: int, status: str) -> Dict[str, Any]:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Item not found")

        try:
            new_status = ItemStatus(status.lower())
        except ValueError:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException(f"Invalid status: {status}")

        if new_status == ItemStatus.IGNORED and item.status != ItemStatus.IGNORED:
            item.ignored_previous_status = item.status
            item.ignored_at = datetime.now(timezone.utc)
        elif new_status != ItemStatus.IGNORED:
            item.ignored_previous_status = None
            item.ignored_at = None

        item.status = new_status
        self.db.commit()
        return {"status": "success", "item_id": item_id, "new_status": item.status.value}






