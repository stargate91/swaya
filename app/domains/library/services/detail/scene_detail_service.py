import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType
from app.domains.users.models import UserOverride
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.domains.metadata.models import Studio, MetadataMatch
from app.domains.library.services.detail._detail_formatter import DetailFormatter

logger = logging.getLogger(__name__)

class SceneDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers

    def get_scene_detail(self, item_id: str) -> SceneDetailResponse:
        from app.application.library.schemas import SceneDetailResponse
        db = self.db
        
        provider_prefix = None
        item = None
        if "_" in item_id:
            parts = item_id.split("_", 1)
            provider_prefix = parts[0].lower()
            scene_uuid = parts[1]
        else:
            if str(item_id).isdigit():
                from app.domains.library.models import MediaItem
                item = db.query(MediaItem).filter(MediaItem.id == int(item_id)).first()
                if item:
                    match_db = db.query(MetadataMatch).filter(
                        MetadataMatch.media_item_id == item.id,
                        MetadataMatch.media_type == MediaType.SCENE
                    ).first()
                    if match_db:
                        p_val = match_db.provider.value if hasattr(match_db.provider, "value") else str(match_db.provider)
                        provider_prefix = p_val.lower()
                        scene_uuid = match_db.external_id
                    else:
                        scene_uuid = item_id
                else:
                    scene_uuid = item_id
            else:
                scene_uuid = item_id

        import re
        is_uuid = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", scene_uuid))
        scene_data = None

        if provider_prefix in ("stashdb", "stash"):
            stash_scraper = self.scrapers.adult(Provider.STASHDB, db)
            scene_data = stash_scraper.fetch_scene(scene_uuid)
        elif provider_prefix == "fansdb":
            fans_scraper = self.scrapers.adult(Provider.FANSDB, db)
            scene_data = fans_scraper.fetch_scene(scene_uuid)
        elif provider_prefix in ("porndb", "theporndb"):
            porndb_scraper = self.scrapers.adult(Provider.PORNDB, db)
            scene_data = porndb_scraper.fetch_scene(scene_uuid)
        else:
            if is_uuid:
                stash_scraper = self.scrapers.adult(Provider.STASHDB, db)
                scene_data = stash_scraper.fetch_scene(scene_uuid)
                if not scene_data:
                    fans_scraper = self.scrapers.adult(Provider.FANSDB, db)
                    scene_data = fans_scraper.fetch_scene(scene_uuid)
            else:
                porndb_scraper = self.scrapers.adult(Provider.PORNDB, db)
                scene_data = porndb_scraper.fetch_scene(scene_uuid)
        
        if not scene_data:
            return JSONResponse(status_code=404, content={"error": "Scene not found on StashDB/FansDB/PornDB"})
        
        title = scene_data.get("title") or "Unknown Scene"
        images = scene_data.get("images") or []
        poster_url = images[0].get("url") if images else None
        
        date_str = scene_data.get("date")
        year = None
        if date_str:
            try:
                year = int(date_str.split("-")[0])
            except:
                pass
        
        duration_raw = scene_data.get("duration")
        duration_sec = None
        duration_str = None
        
        if duration_raw:
            if isinstance(duration_raw, (int, float)):
                duration_sec = int(duration_raw)
            elif isinstance(duration_raw, str):
                val = duration_raw.strip()
                if val.isdigit():
                    duration_sec = int(val)
                elif "." in val and val.replace(".", "", 1).isdigit():
                    duration_sec = int(float(val))
                elif ":" in val:
                    parts = val.split(":")
                    try:
                        if len(parts) == 2:
                            duration_sec = int(parts[0]) * 60 + int(parts[1])
                        elif len(parts) == 3:
                            duration_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    except ValueError:
                        pass

        if duration_sec:
            duration_min = duration_sec // 60
            if duration_min > 0:
                duration_str = f"{duration_min} min"
        
        studio_data = scene_data.get("studio") or scene_data.get("site") or {}
        studio_name = studio_data.get("name")
        
        studio_logo = None
        if studio_name:
            studio_db = db.query(Studio).filter(Studio.name == studio_name).first()
            if studio_db:
                studio_logo = studio_db.logo_path
        
        if not studio_logo:
            studio_images = studio_data.get("images") or []
            studio_logo = studio_images[0].get("url") if studio_images else (studio_data.get("logo") or studio_data.get("image") or studio_data.get("poster"))
        
        parent_data = studio_data.get("parent") or studio_data.get("network") or {}
        parent_name = parent_data.get("name")
        
        parent_logo = None
        if parent_name:
            parent_studio_db = db.query(Studio).filter(Studio.name == parent_name).first()
            if parent_studio_db:
                parent_logo = parent_studio_db.logo_path
                
        if not parent_logo:
            parent_images = parent_data.get("images") or []
            parent_logo = parent_images[0].get("url") if parent_images else (parent_data.get("logo") or parent_data.get("image") or parent_data.get("poster"))
        # Resolve local paths from DB match if it exists
        match_db = db.query(MetadataMatch).filter(
            MetadataMatch.external_id == scene_uuid,
            MetadataMatch.media_type == MediaType.SCENE
        ).first()

        if match_db and match_db.media_item_id and not item:
            from app.domains.library.models import MediaItem
            item = db.query(MediaItem).filter(MediaItem.id == match_db.media_item_id).first()

        from app.domains.people.models import Person, MediaPersonLink
        from sqlalchemy.orm import joinedload
        cast_by_name = {}

        def calculate_age_at_release(birthday_str: str, release_date_str: str) -> Any:
            if not birthday_str or not release_date_str:
                return None
            try:
                from datetime import datetime
                b_date = datetime.strptime(birthday_str[:10], "%Y-%m-%d")
                r_date = datetime.strptime(release_date_str[:10], "%Y-%m-%d")
                age = r_date.year - b_date.year
                if (r_date.month, r_date.day) < (b_date.month, b_date.day):
                    age -= 1
                return age
            except:
                return None

        # 1. Add performers from local database match
        if match_db:
            people_links = db.query(MediaPersonLink).options(
                joinedload(MediaPersonLink.person)
            ).filter(MediaPersonLink.match_id == match_db.id).all()
            for link in sorted(people_links, key=lambda x: x.order if x.order is not None else 0):
                person = link.person
                cast_by_name[person.name.lower()] = {
                    "id": f"local:{person.id}",
                    "name": person.name,
                    "character": link.character_name,
                    "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                    "profile_path": self._resolve_img(person.local_profile_path or person.profile_path, "people"),
                    "popularity": person.rating_porndb if person.rating_porndb is not None else person.popularity or 0,
                    "rating_porndb": person.rating_porndb,
                    "scene_count": person.scene_count,
                    "gender": person.gender,
                    "age_at_release": calculate_age_at_release(person.birthday, date_str)
                }

        # 2. Add/merge performers from external scraper details
        for p_entry in scene_data.get("performers") or []:
            perf = p_entry.get("performer") or {}
            perf_name = perf.get("name")
            if not perf_name:
                continue
            if perf_name.lower() in cast_by_name:
                continue

            p_images = perf.get("images") or []
            p_img = p_images[0].get("url") if p_images else None
            gender_str = str(perf.get("gender") or "").upper()
            mapped_gender = 0
            if "FEMALE" in gender_str:
                mapped_gender = 1
            elif "MALE" in gender_str:
                mapped_gender = 2
            elif gender_str:
                mapped_gender = 3

            person_db = db.query(Person).filter(Person.name == perf_name).first()
            birthday_val = None
            if person_db:
                resolved_img = self._resolve_img(person_db.local_profile_path or person_db.profile_path, "people")
                p_id = f"local:{person_db.id}"
                birthday_val = person_db.birthday
            else:
                resolved_img = p_img
                p_id = f"{provider_prefix}:{perf.get('id')}" if provider_prefix else perf.get("id")

            cast_by_name[perf_name.lower()] = {
                "id": p_id,
                "name": perf_name,
                "character": None,
                "job": "Actor",
                "profile_path": resolved_img,
                "popularity": perf.get("rating_porndb") or 0,
                "rating_porndb": perf.get("rating_porndb"),
                "scene_count": perf.get("scene_count"),
                "gender": mapped_gender,
                "age_at_release": calculate_age_at_release(birthday_val, date_str)
            }

        cast = list(cast_by_name.values())
        
        from app.shared_kernel.user_context import get_current_user_id
        current_uid = get_current_user_id()

        
        metadata_override = None
        if match_db:
            metadata_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.metadata_match_id == match_db.id
            ).first()

        physical_override = None
        if match_db and match_db.media_item_id:
            physical_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.media_item_id == match_db.media_item_id
            ).first()

        override = metadata_override or physical_override
        if not override:
            override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.custom_title == title
            ).first()
        
        ext_background = scene_data.get("background")
        if isinstance(ext_background, dict):
            ext_background = ext_background.get("full") or ext_background.get("large") or ext_background.get("medium")
        if not ext_background:
            ext_background = scene_data.get("image") or poster_url

        if match_db:
            db_updated = False
            if not match_db.backdrop_path and ext_background:
                match_db.backdrop_path = ext_background
                db_updated = True
            if not match_db.release_date and date_str:
                from datetime import datetime
                try:
                    match_db.release_date = datetime.strptime(date_str, "%Y-%m-%d")
                    db_updated = True
                except:
                    pass
            if scene_data.get("rating") is not None and float(scene_data.get("rating")) > 0:
                try:
                    match_db.rating_porndb = float(scene_data.get("rating"))
                    db_updated = True
                except:
                    pass
            
            loc_db = next((l for l in match_db.localizations if l.locale == "en"), None)
            if not loc_db:
                from app.domains.metadata.models import MetadataLocalization
                loc_db = MetadataLocalization(
                    match_id=match_db.id,
                    locale="en",
                    title=title,
                    overview=scene_data.get("details"),
                    poster_path=poster_url
                )
                db.add(loc_db)
                db_updated = True
            else:
                if not loc_db.title and title:
                    loc_db.title = title
                    db_updated = True
                if not loc_db.overview and scene_data.get("details"):
                    loc_db.overview = scene_data.get("details")
                    db_updated = True
                if not loc_db.poster_path and poster_url:
                    loc_db.poster_path = poster_url
                    db_updated = True
            
            if db_updated:
                db.commit()

        local_poster = override.custom_poster if override else None
        local_backdrop = override.custom_backdrop if override else None
        local_logo = override.custom_logo if override else None
        
        if match_db:
            if not local_backdrop:
                local_backdrop = match_db.local_backdrop_path or match_db.backdrop_path
            loc_db = next((l for l in match_db.localizations if l.locale == "en"), None)
            if loc_db:
                if not local_poster:
                    local_poster = loc_db.local_poster_path or loc_db.poster_path
            
        poster_resolved = self._resolve_img(local_poster or poster_url, "posters")
        backdrop_resolved = self._resolve_img(local_backdrop or ext_background, "backdrops", size="original")

        # Merge watch properties
        is_watched = False
        watch_count = 0
        resume_position = 0
        last_watched_at_dt = None

        if metadata_override:
            is_watched = metadata_override.is_watched
            watch_count = metadata_override.watch_count or 0
            last_watched_at_dt = metadata_override.last_watched_at
        elif override:
            is_watched = override.is_watched
            watch_count = override.watch_count or 0
            last_watched_at_dt = override.last_watched_at

        if physical_override:
            if physical_override.is_watched:
                is_watched = True
            if physical_override.watch_count and physical_override.watch_count > watch_count:
                watch_count = physical_override.watch_count
            if physical_override.resume_position:
                resume_position = physical_override.resume_position
            if physical_override.last_watched_at:
                if not last_watched_at_dt or physical_override.last_watched_at > last_watched_at_dt:
                    last_watched_at_dt = physical_override.last_watched_at

        playback_logs = []
        if match_db and match_db.media_item_id:
            from app.domains.history.models import PlaybackLog
            logs = db.query(PlaybackLog).filter(
                PlaybackLog.user_id == current_uid,
                PlaybackLog.media_item_id == match_db.media_item_id
            ).order_by(PlaybackLog.watched_at.desc()).all()
            playback_logs = [
                {
                    "id": log.id,
                    "watched_at": log.watched_at.isoformat()
                }
                for log in logs
            ]

        effective_override = metadata_override if metadata_override else override

        technical = None
        if item:
            technical = {
                "resolution": item.resolution,
                "video_codec": item.video_codec,
                "audio_codec": item.audio_codec,
                "audio_channels": item.audio_channels,
                "hdr_type": item.hdr_type,
                "bit_depth": item.bit_depth,
                "framerate": item.framerate,
                "duration": item.duration,
                "size_bytes": item.size,
                "source": item.source.value if hasattr(item.source, "value") else str(item.source),
                "edition": item.edition.value if hasattr(item.edition, "value") else str(item.edition),
                "audio_type": item.audio_type.value if hasattr(item.audio_type, "value") else str(item.audio_type),
            }

        result = {
            "id": f"scene_{scene_uuid}",
            "title": title,
            "keywords": [],
            "trailer_key": None,
            "logo_path": self._resolve_img(override.custom_logo if (override and override.custom_logo) else (studio_logo or parent_logo), "logos"),
            "original_poster_path": poster_url,
            "original_backdrop_path": poster_url,
            "original_title": None,
            "tagline": None,
            "overview": scene_data.get("details"),
            "genres": [],
            "year": year,
            "release_date": date_str,
            "runtime": duration_sec,
            "formatted_duration": duration_str,
            "rating_tmdb": 0.0,
            "vote_count_tmdb": 0,
            "companies": [{"name": studio_name, "logo_path": self._resolve_img(studio_logo, "logos")}] if studio_name else [],
            "networks": [{"name": parent_name, "logo_path": self._resolve_img(parent_logo, "logos")}] if parent_name else [],
            "poster_path": poster_resolved,
            "backdrop_path": backdrop_resolved,
            "original_language": None,
            "type": "scene",
            "technical": technical,
            "cast": cast,
            "cast_total": len(cast),
            "people_complete": True,
            "directors": [],
            "writers": [],
            "is_adult": True,
            "is_favorite": effective_override.is_favorite if effective_override else False,
            "user_rating": effective_override.user_rating if effective_override else None,
            "user_comment": effective_override.user_comment if effective_override else None,
            "external_ids": {
                "stash_id": scene_uuid,
                "source": provider_prefix or "stash",
            },
            "custom_tags": [t.name for t in effective_override.tags] if (effective_override and effective_override.tags) else [],
            "suggested_tags": [t.get("name") for t in scene_data.get("tags") or [] if t.get("name")] if scene_data.get("tags") else (match_db.suggested_tags if (match_db and match_db.suggested_tags) else []),
            "tags": [],
            "is_tracked": effective_override.is_tracked if effective_override else False,
            "watch_count": watch_count,
            "is_watched": is_watched,
            "resume_position": resume_position,
            "last_watched_at": last_watched_at_dt.isoformat() if last_watched_at_dt else None,
            "playback_logs": playback_logs,
            "in_library": match_db is not None and match_db.media_item_id is not None,
            "library_item_id": match_db.media_item_id if match_db else None,
        }
        
        peaks_count = 0
        peaks_history = []
        if match_db and match_db.media_item_id:
            from app.domains.history.models import PlaybackPeakLog
            peaks = db.query(PlaybackPeakLog).filter(
                PlaybackPeakLog.user_id == current_uid,
                PlaybackPeakLog.media_item_id == match_db.media_item_id
            ).order_by(PlaybackPeakLog.video_position.asc()).all()
            peaks_count = len(peaks)
            peaks_history = [
                {
                    "id": p.id,
                    "video_position": p.video_position,
                    "watched_at": p.created_at.isoformat()
                }
                for p in peaks
            ]
        result["peaks_count"] = peaks_count
        result["peaks_history"] = peaks_history
        from app.domains.library.services.detail.external_links import generate_external_links
        result["external_links"] = generate_external_links(result["external_ids"], "scene")
        return SceneDetailResponse(**result)
