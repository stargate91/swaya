import logging
from typing import Optional, Any
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse
from datetime import datetime

logger = logging.getLogger(__name__)

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.users.models import UserOverride
from app.domains.history.models import PlaybackLog
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.library.services.detail._detail_formatter import DetailFormatter

class TvShowFormatter(DetailFormatter):
    def format(
        self,
        tv_tmdb_id: str,
        db: Session,
        tmdb_scraper: Any,
        seasons_limit: int = 999,
        initial_episodes_limit: int = 999,
        language: str = None
    ):
        from app.application.library.schemas import TvShowDetailResponse
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = language or DEFAULT_FALLBACK_LANGUAGE
        tmdb_data = tmdb_scraper.get_details(tv_tmdb_id_int, "tv", language=ui_lang)
        if not tmdb_data:
            return JSONResponse(status_code=404, content={"error": "TV Show not found on TMDB"})
        
        # Load local episodes to see what is in the library
        local_items = db.query(MediaItem).options(
            joinedload(MediaItem.extras),
            joinedload(MediaItem.matches)
        ).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()

        extras_list = []
        for item in local_items:
            if item.extras:
                match = next((m for m in item.matches if m.season_number is not None and m.episode_number is not None), None)
                if match:
                    parent_label = f"S{match.season_number:02d}E{match.episode_number:02d}"
                else:
                    parent_label = "Extras"

                for ex in item.extras:
                    extras_list.append({
                        "id": ex.id,
                        "name": ex.filename,
                        "path": ex.current_path,
                        "category": ex.category.value if hasattr(ex.category, "value") else str(ex.category),
                        "subtype": ex.subtype.value if (ex.subtype and hasattr(ex.subtype, "value")) else (str(ex.subtype) if ex.subtype else None),
                        "language": ex.language,
                        "parent_label": parent_label,
                    })
        
        local_episodes_map = {}
        for item in local_items:
            for match in item.matches:
                if match.season_number is not None and match.episode_number is not None:
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            local_episodes_map[(match.season_number, num)] = item
                    else:
                        local_episodes_map[(match.season_number, int(ep_num))] = item
        
        # Compute TV show level watch stats globally
        from app.shared_kernel.user_context import get_current_user_id
        current_uid = get_current_user_id()

        episode_matches = db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.media_type == MediaType.EPISODE,
            MetadataMatch.external_id == str(tv_tmdb_id_int)
        ).all()
        episode_match_ids = [m.id for m in episode_matches]
        local_item_ids = [item.id for item in local_items]

        overrides = db.query(UserOverride).filter(
            UserOverride.user_id == current_uid,
            (UserOverride.metadata_match_id.in_(episode_match_ids)) | (UserOverride.media_item_id.in_(local_item_ids))
        ).all() if (episode_match_ids or local_item_ids) else []

        item_episodes_map = {}
        for item in local_items:
            eps = []
            for match in item.matches:
                if match.season_number is not None and match.episode_number is not None:
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            eps.append((match.season_number, num))
                    else:
                        eps.append((match.season_number, int(ep_num)))
            item_episodes_map[item.id] = eps

        watched_episodes_set = set()
        for o in overrides:
            if o.is_watched:
                if o.metadata_match_id:
                    match = next((m for m in episode_matches if m.id == o.metadata_match_id), None)
                    if match:
                        if isinstance(match.episode_number, list):
                            for ep_num in match.episode_number:
                                watched_episodes_set.add((match.season_number, ep_num))
                        else:
                            watched_episodes_set.add((match.season_number, match.episode_number))
                elif o.media_item_id:
                    eps = item_episodes_map.get(o.media_item_id, [])
                    for s_num, ep_num in eps:
                        watched_episodes_set.add((s_num, ep_num))

        seasons = []
        all_season_meta = sorted(tmdb_data.get("seasons", []), key=lambda x: x.get("season_number") or 0)
        
        for idx, season_meta in enumerate(all_season_meta):
            season_number = season_meta.get("season_number")
            if season_number is None:
                continue
            
            if idx < seasons_limit:
                season_detail = tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
                all_episodes = season_detail.get("episodes", []) or []
                
                is_in_library = len(local_items) > 0
                ep_limit = len(all_episodes) if is_in_library else initial_episodes_limit

                episodes = []
                for ep in all_episodes[:ep_limit]:
                    ep_num = ep.get("episode_number")
                    local_item = local_episodes_map.get((season_number, ep_num))
                    
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
                    })
                
                local_count = sum(1 for ep in all_episodes if (season_number, ep.get("episode_number")) in local_episodes_map)
                episodes_loaded_count = len(episodes)
                episodes_complete = True
            else:
                episodes = []
                episodes_loaded_count = 0
                episodes_complete = False
                local_count = sum(1 for (s, e) in local_episodes_map.keys() if s == season_number)
                all_episodes = []

            watched_count = sum(1 for (s, e) in watched_episodes_set if s == season_number)
            episode_count = season_meta.get("episode_count") or len(all_episodes)
            is_season_watched = episode_count > 0 and watched_count >= episode_count

            seasons.append({
                "season_number": season_number,
                "title": season_meta.get("name") or f"Season {season_number}",
                "overview": season_meta.get("overview"),
                "poster_path": self._resolve_img(season_meta.get("poster_path"), "posters"),
                "air_date": season_meta.get("air_date"),
                "episode_count": episode_count,
                "local_episode_count": local_count,
                "episodes_loaded_count": episodes_loaded_count,
                "episodes_complete": episodes_complete,
                "episodes": episodes,
                "is_watched": is_season_watched,
            })
            
        tv_credits = tmdb_data.get("aggregate_credits", {}) or tmdb_data.get("credits", {})
        cast = []
        directors = []
        writers = []
        sound = []
        
        from app.domains.people.models import Person

        # Fetch local overrides for matching TMDB people
        person_ids = set()
        for creator in tmdb_data.get("created_by", []) or []:
            if creator.get("id"):
                person_ids.add(str(creator["id"]))
        for actor in tv_credits.get("cast", []):
            if actor.get("id"):
                person_ids.add(str(actor["id"]))
        for crew in tmdb_data.get("credits", {}).get("crew", []):
            if crew.get("id"):
                person_ids.add(str(crew["id"]))

        local_profiles = {}
        if person_ids:
            try:
                from sqlalchemy import or_
                from app.shared_kernel.user_context import get_current_user_id
                current_uid = get_current_user_id() or 1
                quoted_pids = [f'"{pid}"' for pid in person_ids]
                raw_pids = list(person_ids)
                local_people = db.query(Person).filter(
                    or_(
                        Person.external_ids["tmdb"].as_string().in_(raw_pids),
                        Person.external_ids["tmdb"].as_string().in_(quoted_pids)
                    )
                ).all()
                
                local_person_ids = [lp.id for lp in local_people]
                overrides = db.query(UserOverride).filter(
                    UserOverride.user_id == current_uid,
                    UserOverride.person_id.in_(local_person_ids)
                ).all()
                override_map = {ov.person_id: ov.custom_poster for ov in overrides if ov.custom_poster}

                for lp in local_people:
                    tmdb_id_str = lp.external_ids.get("tmdb")
                    if tmdb_id_str:
                        custom_img = override_map.get(lp.id)
                        local_profiles[int(tmdb_id_str)] = {
                            "profile_path": custom_img or lp.local_profile_path or lp.profile_path,
                            "birthday": lp.birthday
                        }
                
                missing_birthday_ids = [lp.id for lp in local_people if lp.birthday is None]
                if missing_birthday_ids:
                    try:
                        from app.domains.tasks import task_manager
                        if task_manager.people_enrich_worker:
                            task_manager.people_enrich_worker.enqueue_people(missing_birthday_ids)
                    except Exception as ex:
                        logger.error(f"Failed to auto-enqueue missing birthdays: {ex}")
            except Exception as e:
                logger.error(f"Failed to query custom performer avatars for TV detail: {e}")

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

        first_air_date = tmdb_data.get("first_air_date")

        for creator in tmdb_data.get("created_by", []) or []:
            creator_id = creator.get("id")
            resolved = local_profiles.get(creator_id) if creator_id else None
            resolved_img = resolved.get("profile_path") if resolved else None
            birthday_str = resolved.get("birthday") if resolved else None
            directors.append({
                "id": f"tmdb:{creator_id}" if creator_id else None,
                "name": creator.get("name"),
                "job": "Creator",
                "gender": creator.get("gender"),
                "profile_path": self._resolve_img(resolved_img or creator.get("profile_path"), "people"),
                "age_at_release": calculate_age_at_release(birthday_str, first_air_date)
            })
            
        for actor in tv_credits.get("cast", [])[:15]:
            actor_id = actor.get("id")
            resolved = local_profiles.get(actor_id) if actor_id else None
            resolved_img = resolved.get("profile_path") if resolved else None
            birthday_str = resolved.get("birthday") if resolved else None
            character = actor.get("character")
            if not character and "roles" in actor:
                roles = actor.get("roles", [])
                if roles:
                    character = ", ".join(filter(None, [r.get("character") for r in roles]))
            cast.append({
                "id": f"tmdb:{actor_id}" if actor_id else None,
                "name": actor.get("name"),
                "character": character,
                "gender": actor.get("gender"),
                "profile_path": self._resolve_img(resolved_img or actor.get("profile_path"), "people"),
                "age_at_release": calculate_age_at_release(birthday_str, first_air_date)
            })
            
        crew_list = tmdb_data.get("credits", {}).get("crew", [])
        for crew in crew_list:
            crew_id = crew.get("id")
            resolved = local_profiles.get(crew_id) if crew_id else None
            resolved_img = resolved.get("profile_path") if resolved else None
            birthday_str = resolved.get("birthday") if resolved else None
            crew_member = {
                "id": f"tmdb:{crew_id}" if crew_id else None,
                "name": crew.get("name"),
                "job": crew.get("job"),
                "gender": crew.get("gender"),
                "profile_path": self._resolve_img(resolved_img or crew.get("profile_path"), "people"),
                "age_at_release": calculate_age_at_release(birthday_str, first_air_date)
            }
            if crew.get("job") == "Director":
                directors.append(crew_member)
            elif crew.get("job") in ("Writer", "Screenplay"):
                writers.append(crew_member)
            elif crew.get("department") == "Sound" or crew.get("job") in ("Original Music Composer", "Music", "Composer"):
                sound.append(crew_member)
        
        override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
            UserOverride.user_id == current_uid,
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.TV
        ).first()
        
        from app.domains.media_assets.services.images import image_processing_service
        effective_backdrop = None
        if override and override.custom_backdrop:
            effective_backdrop = override.custom_backdrop
        else:
            effective_backdrop = image_processing_service.pick_backdrop_path(tmdb_data, preferred_language=ui_lang, allow_low_res=True)

        effective_logo = None
        if override and override.custom_logo:
            effective_logo = override.custom_logo
        else:
            effective_logo = image_processing_service.pick_logo_path(tmdb_data, preferred_language=ui_lang)
        
        loc_db = None
        series_match = db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.TV
        ).first()

        if series_match:
            db_updated = False
            if not series_match.backdrop_path and effective_backdrop:
                series_match.backdrop_path = effective_backdrop
                db_updated = True
            
            first_air_date = tmdb_data.get("first_air_date")
            if not series_match.release_date and first_air_date:
                try:
                    series_match.release_date = datetime.strptime(first_air_date, "%Y-%m-%d")
                    db_updated = True
                except:
                    pass
            if not series_match.rating_tmdb and tmdb_data.get("vote_average"):
                try:
                    series_match.rating_tmdb = float(tmdb_data.get("vote_average"))
                    db_updated = True
                except:
                    pass
            if not series_match.vote_count_tmdb and tmdb_data.get("vote_count"):
                try:
                    series_match.vote_count_tmdb = int(tmdb_data.get("vote_count"))
                    db_updated = True
                except:
                    pass
            if series_match.is_adult != tmdb_data.get("adult", False):
                series_match.is_adult = tmdb_data.get("adult", False)
                db_updated = True
            
            loc_db = next((l for l in series_match.localizations if l.locale == ui_lang), None)
            if not loc_db:
                loc_db = MetadataLocalization(
                    match_id=series_match.id,
                    locale=ui_lang,
                    title=tmdb_data.get("name") or tmdb_data.get("original_name") or "Unknown TV Show",
                    overview=tmdb_data.get("overview"),
                    poster_path=tmdb_data.get("poster_path"),
                    tagline=tmdb_data.get("tagline")
                )
                db.add(loc_db)
                db_updated = True
            else:
                if not loc_db.title and (tmdb_data.get("name") or tmdb_data.get("original_name")):
                    loc_db.title = tmdb_data.get("name") or tmdb_data.get("original_name")
                    db_updated = True
                if not loc_db.overview and tmdb_data.get("overview"):
                    loc_db.overview = tmdb_data.get("overview")
                    db_updated = True
                if not loc_db.poster_path and tmdb_data.get("poster_path"):
                    loc_db.poster_path = tmdb_data.get("poster_path")
                    db_updated = True
                if not loc_db.tagline and tmdb_data.get("tagline"):
                    loc_db.tagline = tmdb_data.get("tagline")
                    db_updated = True
            
            if db_updated:
                db.commit()

        keywords_list = []
        if tmdb_data.get("keywords"):
            raw_kws = tmdb_data.get("keywords", {})
            if isinstance(raw_kws, dict):
                keywords_list = [k["name"] for k in raw_kws.get("results", []) if isinstance(k, dict) and "name" in k]

        videos = (tmdb_data.get("videos") or {}).get("results") or []
        trailer_key = None
        youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
        if not youtube_trailers:
            youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
        if youtube_trailers:
            trailer_key = youtube_trailers[0].get("key")

        from app.shared_kernel.genre_utils import split_genres as _split_genres



        playback_logs_db = db.query(PlaybackLog).filter(
            PlaybackLog.media_item_id.in_(local_item_ids)
        ).order_by(PlaybackLog.watched_at.desc()).all() if local_item_ids else []

        localizations = db.query(MetadataLocalization).filter(
            MetadataLocalization.match_id.in_(episode_match_ids)
        ).all() if episode_match_ids else []
        loc_map = {l.match_id: l.title for l in localizations if l.title}



        playback_logs = []
        for log in playback_logs_db:
            eps = item_episodes_map.get(log.media_item_id, [])
            for s_num, ep_num in eps:
                match = next((m for m in episode_matches if m.season_number == s_num and m.episode_number == ep_num), None)
                ep_title = loc_map.get(match.id) if match else None
                if not ep_title:
                    ep_title = f"Episode {ep_num}"
                playback_logs.append({
                    "id": f"{log.id}_{s_num}_{ep_num}",
                    "watched_at": log.watched_at.isoformat(),
                    "seasonNumber": s_num,
                    "episodeNumber": ep_num,
                    "episodeTitle": ep_title,
                    "episodeId": f"tmdb_{tv_tmdb_id_int}_{s_num}_{ep_num}" if not match else str(match.media_item_id or f"tmdb_{tv_tmdb_id_int}_{s_num}_{ep_num}")
                })

        in_progress_episodes = []
        for o in overrides:
            if o.resume_position > 0 and not o.is_watched:
                s_num = None
                ep_num = None
                ep_title = None
                if o.metadata_match_id:
                    match = next((m for m in episode_matches if m.id == o.metadata_match_id), None)
                    if match:
                        s_num = match.season_number
                        ep_num = match.episode_number
                        ep_title = loc_map.get(match.id)
                elif o.media_item_id:
                    eps = item_episodes_map.get(o.media_item_id, [])
                    if eps:
                        s_num, ep_num = eps[0]
                        match = next((m for m in episode_matches if m.season_number == s_num and m.episode_number == ep_num), None)
                        if match:
                            ep_title = loc_map.get(match.id)
                
                if s_num is not None and ep_num is not None:
                    if not ep_title:
                        ep_title = f"Episode {ep_num}"
                    in_progress_episodes.append({
                        "id": f"tmdb_{tv_tmdb_id_int}_{s_num}_{ep_num}",
                        "episode_number": ep_num,
                        "title": ep_title,
                        "resume_position": o.resume_position,
                        "season_number": s_num
                    })

        watched_episodes_count = len(watched_episodes_set)

        result = {
            "id": f"tmdb_{tv_tmdb_id_int}",
            "tv_tmdb_id": tv_tmdb_id_int,
            "keywords": keywords_list,
            "trailer_key": trailer_key,
            "extras": extras_list,
            "imdb_id": tmdb_data.get("external_ids", {}).get("imdb_id") or (series_match.imdb_id if series_match else None),
            "title": tmdb_data.get("name") or tmdb_data.get("original_name") or "Unknown TV Show",
            "tagline": loc_db.tagline if (loc_db and loc_db.tagline) else tmdb_data.get("tagline"),
            "logo_path": self._resolve_img(effective_logo, "logos"),
            "backdrop_path": self._resolve_img(effective_backdrop, "backdrops", size="original"),
            "poster_path": self._resolve_img(override.custom_poster if (override and override.custom_poster) else tmdb_data.get("poster_path"), "posters"),
            "year": int(tmdb_data.get("first_air_date", "").split("-")[0]) if tmdb_data.get("first_air_date") else None,
            "first_air_date": tmdb_data.get("first_air_date"),
            "last_air_date": tmdb_data.get("last_air_date"),
            "release_status": tmdb_data.get("status"),
            "number_of_seasons": tmdb_data.get("number_of_seasons") or len(seasons),
            "number_of_episodes": tmdb_data.get("number_of_episodes") or 0,
            "overview": tmdb_data.get("overview"),
            "rating_tmdb": tmdb_data.get("vote_average"),
            "rating_imdb": series_match.rating_imdb if series_match else None,
            "rating_rotten": series_match.rating_rotten if series_match else None,
            "rating_meta": series_match.rating_meta if series_match else None,
            "genres": _split_genres([g["name"] for g in tmdb_data.get("genres", [])]) if tmdb_data.get("genres") else [],
            "type": "tv",
            "cast": cast,
            "directors": directors,
            "writers": writers,
            "sound": sound,
            "seasons": seasons,
            "companies": [{"name": c.get("name"), "logo_path": self._resolve_img(c.get("logo_path"), "logos")} for c in tmdb_data.get("production_companies", [])] if tmdb_data.get("production_companies") else [],
            "networks": [{"name": n.get("name"), "logo_path": self._resolve_img(n.get("logo_path"), "logos")} for n in tmdb_data.get("networks", [])] if tmdb_data.get("networks") else [],
            "is_adult": tmdb_data.get("adult", False),
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "is_tracked": override.is_tracked if override else False,
            "in_library": len(local_items) > 0,
            "progressive_seasons": True,
            "watch_stats": {
                "total_episodes_count": tmdb_data.get("number_of_episodes") or 0,
                "watched_episodes_count": watched_episodes_count,
                "in_progress_episodes": in_progress_episodes,
                "playback_logs": playback_logs,
            },
        }
        ext_ids = {
            "tmdb": tv_tmdb_id_int
        }
        imdb_id = result.get("imdb_id")
        if imdb_id:
            ext_ids["imdb"] = imdb_id

        from app.domains.library.services.detail.external_links import generate_external_links
        result["external_links"] = generate_external_links(ext_ids, "tv")
        return TvShowDetailResponse(**result)
