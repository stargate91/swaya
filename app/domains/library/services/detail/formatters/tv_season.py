from typing import Optional, Any
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.library.services.detail._detail_formatter import DetailFormatter

class TvSeasonFormatter(DetailFormatter):
    def format(
        self,
        tv_tmdb_id: str,
        season_number: int,
        db: Session,
        tmdb_scraper: Any
    ):
        from app.domains.library.schemas import TvSeasonDetailResponse
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        season_detail = tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
        if not season_detail:
            return JSONResponse(status_code=404, content={"error": "Season not found"})
        
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.season_number == season_number,
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        local_episodes_map = {}
        for item in local_items:
            for match in item.matches:
                if match.episode_number is not None:
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            local_episodes_map[num] = item
                    else:
                        local_episodes_map[int(ep_num)] = item
        
        episodes = []
        all_episodes = season_detail.get("episodes", []) or []
        for ep in all_episodes:
            ep_num = ep.get("episode_number")
            local_item = local_episodes_map.get(ep_num)
            
            override = None
            from app.shared_kernel.user_context import get_current_user_id
            current_uid = get_current_user_id()
            
            episode_match = db.query(MetadataMatch).filter(
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.media_type == MediaType.EPISODE,
                MetadataMatch.season_number == season_number,
                MetadataMatch.episode_number == ep_num,
                MetadataMatch.external_id == str(tv_tmdb_id_int)
            ).first()
            
            if episode_match:
                override = db.query(UserOverride).filter(
                    UserOverride.user_id == current_uid,
                    UserOverride.metadata_match_id == episode_match.id
                ).first()
            
            if not override and local_item:
                override = db.query(UserOverride).filter(
                    UserOverride.user_id == current_uid,
                    UserOverride.media_item_id == local_item.id
                ).first()
            
            is_watched = False
            watch_count = 0
            resume_position = 0
            last_watched_at = override.last_watched_at.isoformat() if override and override.last_watched_at else None
            if override:
                is_watched = override.is_watched
                watch_count = override.watch_count or 0
                resume_position = override.resume_position or 0

            is_multi_episode = False
            if local_item:
                siblings = [k for k, v in local_episodes_map.items() if v.id == local_item.id]
                if len(siblings) > 1:
                    is_multi_episode = True
                    match_ids = [m.id for m in local_item.matches]
                    sibling_overrides = db.query(UserOverride).filter(
                        UserOverride.user_id == current_uid,
                        (UserOverride.media_item_id == local_item.id) | (UserOverride.metadata_match_id.in_(match_ids))
                    ).all()
                    for sov in sibling_overrides:
                        if sov.is_watched:
                            is_watched = True
                        if sov.watch_count and sov.watch_count > watch_count:
                            watch_count = sov.watch_count
                        if sov.resume_position and sov.resume_position > resume_position:
                            resume_position = sov.resume_position
                        if sov.last_watched_at:
                            if not last_watched_at or sov.last_watched_at.isoformat() > last_watched_at:
                                last_watched_at = sov.last_watched_at.isoformat()
            
            playback_logs = []
            technical = None
            if local_item:
                playback_logs = [
                    {"id": log.id, "watched_at": log.watched_at.isoformat()}
                    for log in sorted(local_item.playback_logs or [], key=lambda x: x.watched_at, reverse=True)
                ]
                technical = {
                    "resolution": local_item.resolution,
                    "video_codec": local_item.video_codec,
                    "audio_codec": local_item.audio_codec,
                    "audio_channels": local_item.audio_channels,
                    "hdr_type": local_item.hdr_type,
                    "bit_depth": local_item.bit_depth,
                    "framerate": local_item.framerate,
                    "duration": local_item.duration,
                    "size_bytes": local_item.size,
                    "source": local_item.source.value if hasattr(local_item.source, "value") else str(local_item.source),
                    "edition": local_item.edition.value if hasattr(local_item.edition, "value") else str(local_item.edition),
                    "audio_type": local_item.audio_type.value if hasattr(local_item.audio_type, "value") else str(local_item.audio_type),
                }

            episodes.append({
                "id": f"tmdb_{tv_tmdb_id_int}_{season_number}_{ep_num}",
                "episode_number": ep_num,
                "title": ep.get("name") or f"Episode {ep_num}",
                "overview": ep.get("overview"),
                "still_path": self._resolve_img(ep.get("still_path"), "stills"),
                "runtime": ep.get("runtime"),
                "rating_tmdb": ep.get("vote_average"),
                "vote_count_tmdb": ep.get("vote_count"),
                "air_date": ep.get("air_date"),
                "path": local_item.current_path if local_item else None,
                "filename": local_item.filename if local_item else None,
                "watch_count": watch_count,
                "is_watched": is_watched,
                "resume_position": resume_position,
                "last_watched_at": last_watched_at,
                "in_library": local_item is not None,
                "is_missing": local_item is None,
                "is_multi_episode": is_multi_episode,
                "playback_logs": playback_logs,
                "technical": technical,
            })
            
        local_count = sum(1 for ep in all_episodes if ep.get("episode_number") in local_episodes_map)

        result = {
            "season_number": season_number,
            "title": season_detail.get("name") or f"Season {season_number}",
            "overview": season_detail.get("overview"),
            "poster_path": self._resolve_img(season_detail.get("poster_path"), "posters"),
            "air_date": season_detail.get("air_date"),
            "episode_count": len(all_episodes),
            "local_episode_count": local_count,
            "episodes_loaded_count": len(episodes),
            "episodes": episodes,
        }
        return TvSeasonDetailResponse(**result)
