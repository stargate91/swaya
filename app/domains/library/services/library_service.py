import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import func, or_, and_, desc
from sqlalchemy.orm import Session, joinedload, selectinload

from app.domains.library.models import MediaItem, Library, ExtraFile
from app.domains.metadata.models import MetadataMatch, MetadataLocalization, Studio, MediaCollection
from app.domains.users.models import User, Tag, UserOverride
from app.shared_kernel.enums import ItemStatus, MediaType, Provider

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class LibraryService:
    """
    Service responsible for retrieving and formatting library-level media statistics,
    continue-watching queue, and paginated lists of media items.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes >= 1024 ** 4:
            return f"{size_bytes / (1024 ** 4):.1f} TB"
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024 ** 3):.1f} GB"
        return f"{size_bytes / (1024 ** 2):.0f} MB"

    def get_stats(self, include_adult: bool = False) -> dict[str, Any]:
        """
        Calculates and returns statistics of library media assets, including storage,
        genres, and manual review counts.
        """
        # Standard status values for matched library files
        library_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]

        movie_query = self.db.query(func.count(MediaItem.id)).select_from(MediaItem).join(
            MetadataMatch, (MetadataMatch.media_item_id == MediaItem.id)
        ).filter(
            MediaItem.status.in_(library_statuses),
            MetadataMatch.media_type == MediaType.MOVIE,
            MetadataMatch.is_adult == include_adult
        )
        total_movies = movie_query.scalar() or 0

        tv_query = self.db.query(func.count(func.distinct(MetadataMatch.parent_id))).select_from(MediaItem).join(
            MetadataMatch, (MetadataMatch.media_item_id == MediaItem.id)
        ).filter(
            MediaItem.status.in_(library_statuses),
            MetadataMatch.media_type == MediaType.EPISODE,
            MetadataMatch.is_adult == include_adult
        )
        total_tv = tv_query.scalar() or 0

        episodes_query = self.db.query(func.count(MediaItem.id)).select_from(MediaItem).join(
            MetadataMatch, (MetadataMatch.media_item_id == MediaItem.id)
        ).filter(
            MediaItem.status.in_(library_statuses),
            MetadataMatch.media_type == MediaType.EPISODE,
            MetadataMatch.is_adult == include_adult
        )
        total_episodes = episodes_query.scalar() or 0

        scenes_query = self.db.query(func.count(MediaItem.id)).select_from(MediaItem).join(
            MetadataMatch, (MetadataMatch.media_item_id == MediaItem.id)
        ).filter(
            MediaItem.status.in_(library_statuses),
            MetadataMatch.media_type.in_([MediaType.SCENE, MediaType.JAV]),
            MetadataMatch.is_adult == include_adult
        )
        total_scenes = scenes_query.scalar() or 0

        # Calculate storage sizes
        items = self.db.query(MediaItem).select_from(MediaItem).join(MetadataMatch).filter(
            MediaItem.status.in_(library_statuses)
        ).options(joinedload(MediaItem.matches)).all()
        
        movie_bytes = 0
        tv_bytes = 0
        adult_bytes = 0
        drives = set()

        for item in items:
            size = item.size or 0
            path = item.current_path
            if path:
                if ":" in path:
                    drives.add(path.split(":")[0].upper() + ":")
                elif path.startswith("/"):
                    drives.add("/")

            is_tv = False
            is_scene = False
            is_adult_item = False
            for m in item.matches:
                if m.is_adult:
                    is_adult_item = True
                if m.media_type in (MediaType.TV, MediaType.EPISODE):
                    is_tv = True
                elif m.media_type in (MediaType.SCENE, MediaType.JAV):
                    is_scene = True

            if is_adult_item and not include_adult:
                continue

            if is_tv:
                tv_bytes += size
            elif is_scene:
                adult_bytes += size
            else:
                movie_bytes += size

        total_bytes = movie_bytes + tv_bytes + adult_bytes
        storage_str = self._format_size(total_bytes)

        # Unmatched / manual reviews
        unmatched = self.db.query(func.count(MediaItem.id)).filter(
            MediaItem.status.in_([ItemStatus.NEW, ItemStatus.ERROR, ItemStatus.NO_MATCH, ItemStatus.UNCERTAIN, ItemStatus.MULTIPLE])
        ).scalar() or 0

        # Dynamic genre and decade calculations
        from itertools import combinations
        
        matches = self.db.query(MetadataMatch).join(
            MediaItem, MetadataMatch.media_item_id == MediaItem.id
        ).filter(
            MediaItem.status.in_(library_statuses)
        ).options(
            joinedload(MetadataMatch.localizations),
            joinedload(MetadataMatch.parent).joinedload(MetadataMatch.parent).joinedload(MetadataMatch.localizations)
        ).all()

        seen_tv = set()
        unique_matches = []
        for m in matches:
            if not include_adult and m.is_adult:
                continue
            if m.media_type == MediaType.MOVIE:
                unique_matches.append(m)
            elif m.media_type == MediaType.EPISODE:
                tv_match = None
                if m.parent and m.parent.parent:
                    tv_match = m.parent.parent
                elif m.parent:
                    tv_match = m.parent
                
                if tv_match:
                    if not include_adult and tv_match.is_adult:
                        continue
                    if tv_match.id not in seen_tv:
                        seen_tv.add(tv_match.id)
                        unique_matches.append(tv_match)
                else:
                    unique_matches.append(m)

        genre_dist = {}
        genre_dist_ids = {}
        genre_labels = {}
        decade_dist = {}
        genre_pair_dist = {}

        def _split_genres(genres_list):
            res = []
            for g in genres_list:
                if not g:
                    continue
                parts = [p.strip() for p in g.replace("/", ",").replace(";", ",").split(",") if p.strip()]
                res.extend(parts)
            return res

        for m in unique_matches:
            # Decade
            year = None
            if m.release_date:
                year = m.release_date.year
            if year and year >= 1900:
                decade = (year // 10) * 10
                decade_str = f"{decade}s"
                decade_dist[decade_str] = decade_dist.get(decade_str, 0) + 1

            # Genres
            loc = m.localizations[0] if m.localizations else None
            if loc and loc.genres:
                split_names = _split_genres(loc.genres)
                unique_genre_keys = []
                for name in split_names:
                    genre_key = name
                    genre_dist_ids[genre_key] = genre_dist_ids.get(genre_key, 0) + 1
                    if genre_key not in genre_labels:
                        genre_labels[genre_key] = name
                    if genre_key not in unique_genre_keys:
                        unique_genre_keys.append(genre_key)
                
                for source_id, target_id in combinations(sorted(unique_genre_keys), 2):
                    pair_key = f"{source_id}|{target_id}"
                    genre_pair_dist[pair_key] = genre_pair_dist.get(pair_key, 0) + 1

        for genre_id, count in genre_dist_ids.items():
            label = genre_labels.get(genre_id, genre_id)
            genre_dist[label] = count

        top_genre_ids = sorted(genre_dist_ids.items(), key=lambda x: x[1], reverse=True)[:12]
        top_genre_id_set = {genre_id for genre_id, _ in top_genre_ids}
        constellation_nodes = [
            {
                "id": genre_id,
                "label": genre_labels.get(genre_id, genre_id),
                "count": count,
            }
            for genre_id, count in top_genre_ids
        ]
        constellation_links = []
        for pair_key, count in sorted(genre_pair_dist.items(), key=lambda x: x[1], reverse=True):
            source_id, target_id = pair_key.split("|", 1)
            if source_id not in top_genre_id_set or target_id not in top_genre_id_set:
                continue
            constellation_links.append({
                "source": source_id,
                "target": target_id,
                "count": count,
            })
            if len(constellation_links) >= 24:
                break

        return {
            "total_movies": total_movies,
            "total_tv": total_tv,
            "total_episodes": total_episodes,
            "total_scenes": total_scenes,
            "storage": storage_str,
            "drive_count": len(drives) or 1,
            "unmatched": unmatched,
            "storage_breakdown": {
                "movies": self._format_size(movie_bytes),
                "tv": self._format_size(tv_bytes),
                "scenes": self._format_size(adult_bytes),
                "extras": "0 MB"
            },
            "manual_review_total": unmatched,
            "manual_review_breakdown": {
                "new": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.NEW).scalar() or 0,
                "error": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.ERROR).scalar() or 0,
                "uncertain": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.UNCERTAIN).scalar() or 0,
                "no_match": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.NO_MATCH).scalar() or 0,
                "multiple": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.MULTIPLE).scalar() or 0
            },
            "genre_distribution": genre_dist,
            "genre_distribution_ids": genre_dist_ids,
            "genre_labels": genre_labels,
            "genre_constellation": {"nodes": constellation_nodes, "links": constellation_links},
            "decade_distribution": decade_dist
        }

    def get_continue_watching(self, limit: int = 12, include_adult: bool = False) -> list[dict[str, Any]]:
        """
        Retrieves the queue of items currently being watched by the user, ordered by watch date.
        """
        query = self.db.query(UserOverride).join(
            MediaItem, UserOverride.media_item_id == MediaItem.id
        ).join(
            MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id
        ).filter(
            UserOverride.resume_position > 0,
            UserOverride.is_watched == False
        ).options(
            joinedload(UserOverride.media_item),
            joinedload(UserOverride.metadata_match).joinedload(MetadataMatch.localizations),
            joinedload(UserOverride.metadata_match).joinedload(MetadataMatch.parent).joinedload(MetadataMatch.parent).joinedload(MetadataMatch.localizations)
        )
        query = query.filter(MetadataMatch.is_adult == include_adult)

        overrides = query.order_by(UserOverride.last_watched_at.desc()).limit(limit).all()

        results = []
        for o in overrides:
            item = o.media_item
            match = o.metadata_match
            loc = match.localizations[0] if match and match.localizations else None
            
            title = o.custom_title if o.custom_title else (loc.title if loc else item.filename)
            tv_title = None
            episode_title = None
            tv_tmdb_id = None
            
            if match and match.media_type == MediaType.EPISODE:
                episode_title = title
                tv_match = None
                if match.parent and match.parent.parent:
                    tv_match = match.parent.parent
                elif match.parent:
                    tv_match = match.parent
                
                if tv_match:
                    tv_override = self.db.query(UserOverride).filter(
                        UserOverride.metadata_match_id == tv_match.id,
                        UserOverride.user_id == o.user_id
                    ).first()
                    tv_loc = tv_match.localizations[0] if tv_match.localizations else None
                    tv_title = (tv_override.custom_title if (tv_override and tv_override.custom_title) else None) or (tv_loc.title if tv_loc else None)
                    tv_tmdb_id = int(tv_match.external_id) if tv_match.external_id.isdigit() else None
            
            results.append({
                "id": item.id,
                "title": title,
                "tv_title": tv_title,
                "episode_title": episode_title,
                "type": match.media_type.value if match else "movie",
                "season_number": match.season_number if match else None,
                "episode_number": match.episode_number if match else None,
                "tv_tmdb_id": tv_tmdb_id,
                "tmdb_id": int(match.external_id) if (match and match.external_id.isdigit()) else None,
                "backdrop_path": match.backdrop_path if match else None,
                "still_path": match.still_path if match else None,
                "resume_position": o.resume_position,
                "duration": item.duration or 0,
                "is_watched": o.is_watched,
                "last_watched_at": o.last_watched_at.isoformat() if o.last_watched_at else None,
            })
        return results

    def get_library_tab_page(
        self,
        tab: str,
        page: int = 1,
        page_size: int = 40,
        sort_by: str = "title_asc",
        search: str = "",
        selected_tags: Optional[List[str]] = None,
        selected_genre: Optional[str] = None,
        selected_decade: Optional[str] = None,
        selected_year: Optional[int] = None,
        filter_favorite: str = "all",
        filter_watched: str = "all",
        filter_ownership: str = "owned",
        filter_status: str = "active",
        filter_gender: str = "all",
        people_role: str = "all",
        include_adult: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieves a paginated, filtered, and sorted list of library items for a specific UI tab.
        """
        query = self.db.query(MetadataMatch).outerjoin(
            MediaItem, MetadataMatch.media_item_id == MediaItem.id
        ).options(
            selectinload(MetadataMatch.localizations),
            selectinload(MetadataMatch.media_item),
            selectinload(MetadataMatch.overrides)
        )

        joined_localization = False
        joined_override = False
        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]

        # Ownership filter
        if filter_ownership == "tracked":
            query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == 1))
            joined_override = True
            query = query.filter(
                MetadataMatch.media_item_id == None,
                UserOverride.is_tracked == True
            )
        else: # Default: owned
            query = query.filter(
                MetadataMatch.media_item_id != None,
                MediaItem.status.in_(lib_statuses)
            )

        # Tab filters: movies vs tv vs adult/scenes
        if tab == "tv":
            query = query.filter(MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE, MediaType.SEASON]))
        elif tab in ("adult", "scenes"):
            query = query.filter(MetadataMatch.media_type.in_([MediaType.SCENE, MediaType.JAV]))
        else:
            query = query.filter(MetadataMatch.media_type == MediaType.MOVIE)

        # NSFW filter
        query = query.filter(MetadataMatch.is_adult == include_adult)

        # Search filter
        if search:
            query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
            joined_localization = True
            if filter_ownership == "tracked":
                query = query.filter(MetadataLocalization.title.ilike(f"%{search}%"))
            else:
                query = query.filter(
                    or_(
                        MetadataLocalization.title.ilike(f"%{search}%"),
                        MediaItem.filename.ilike(f"%{search}%")
                    )
                )

        # Favorite filter
        if filter_favorite in ("favorite", "not_favorite"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == 1))
                joined_override = True
            if filter_favorite == "favorite":
                query = query.filter(UserOverride.is_favorite == True)
            else:
                query = query.filter(or_(UserOverride.is_favorite == False, UserOverride.is_favorite == None))

        # Watched filter
        if filter_watched in ("watched", "unwatched"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == 1))
                joined_override = True
            if filter_watched == "watched":
                query = query.filter(UserOverride.is_watched == True)
            else:
                query = query.filter(or_(UserOverride.is_watched == False, UserOverride.is_watched == None))

        # Genre filter
        if selected_genre:
            if not joined_localization:
                query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
                joined_localization = True
            query = query.filter(MetadataLocalization.genres.like(f'%"{selected_genre}"%'))

        # Decade filter
        if selected_decade and selected_decade.endswith("s") and selected_decade[:-1].isdigit():
            start_year = int(selected_decade[:-1])
            end_year = start_year + 9
            query = query.filter(
                MetadataMatch.release_date >= datetime(start_year, 1, 1),
                MetadataMatch.release_date <= datetime(end_year, 12, 31)
            )

        # Year filter
        if selected_year:
            query = query.filter(
                MetadataMatch.release_date >= datetime(selected_year, 1, 1),
                MetadataMatch.release_date <= datetime(selected_year, 12, 31)
            )

        # Tags filter
        if selected_tags:
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == 1))
                joined_override = True
            from app.domains.users.models import Tag, user_override_tags
            query = query.join(user_override_tags, user_override_tags.c.user_override_id == UserOverride.id)\
                         .join(Tag, Tag.id == user_override_tags.c.tag_id)\
                         .filter(Tag.name.in_(selected_tags))

        # Sorting
        if sort_by in ("title_asc", "title_desc", "default"):
            if not joined_localization:
                query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
                joined_localization = True
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == 1))
                joined_override = True
            
            val_col = func.coalesce(UserOverride.custom_title, MetadataLocalization.title, MediaItem.filename)
            if sort_by == "title_desc":
                query = query.order_by(desc(val_col))
            else:
                query = query.order_by(val_col.asc())
        elif sort_by == "date_desc":
            query = query.order_by(desc(MetadataMatch.release_date))
        elif sort_by == "date_asc":
            query = query.order_by(MetadataMatch.release_date.asc())
        elif sort_by == "rating_desc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == 1))
                joined_override = True
            query = query.order_by(desc(func.coalesce(
                UserOverride.user_rating,
                MetadataMatch.rating_porndb,
                MetadataMatch.rating_tmdb,
            )))

        total_items = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        formatted_items = []
        for match in items:
            loc = match.localizations[0] if match.localizations else None
            item = match.media_item
            
            o = next((ov for ov in match.overrides if ov.user_id == 1), None) if match.overrides else None
            title = (o.custom_title if (o and o.custom_title) else None) or (loc.title if loc else (item.filename if item else "Unknown"))
            poster_path = (o.custom_poster if (o and o.custom_poster) else None) or (loc.poster_path if loc else None)
            backdrop_path = (o.custom_backdrop if (o and o.custom_backdrop) else None) or (match.backdrop_path or None)
            rating = (o.user_rating if (o and o.user_rating is not None) else None)
            if rating is None:
                rating = match.rating_porndb or match.rating_tmdb or 0.0

            formatted_items.append({
                "id": item.id if item else None,
                "title": title,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": poster_path,
                "backdrop_path": backdrop_path,
                "rating": rating,
                "rating_porndb": match.rating_porndb,
                "rating_imdb": match.rating_imdb,
                "type": match.media_type.value,
                "path": item.current_path if item else None,
                "duration": (item.duration or 0.0) if item else 0.0,
                "size": (item.size or 0) if item else 0
            })

        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1

        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]
        
        movies_cnt_query = self.db.query(MediaItem).select_from(MediaItem).join(MetadataMatch).filter(
            MediaItem.status.in_(lib_statuses), MetadataMatch.media_type == MediaType.MOVIE
        )
        tv_cnt_query = self.db.query(MediaItem).select_from(MediaItem).join(MetadataMatch).filter(
            MediaItem.status.in_(lib_statuses), MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE, MediaType.SEASON])
        )
        adult_cnt_query = self.db.query(MediaItem).select_from(MediaItem).join(MetadataMatch).filter(
            MediaItem.status.in_(lib_statuses), MetadataMatch.media_type.in_([MediaType.SCENE, MediaType.JAV])
        )
        movies_cnt_query = movies_cnt_query.filter(MetadataMatch.is_adult == include_adult)
        tv_cnt_query = tv_cnt_query.filter(MetadataMatch.is_adult == include_adult)
        adult_cnt_query = adult_cnt_query.filter(MetadataMatch.is_adult == include_adult)

        counts = {
            "movies": movies_cnt_query.count(),
            "tv": tv_cnt_query.count(),
            "scenes": adult_cnt_query.count(),
            "people": 0
        }

        return {
            "tab": tab,
            "items": formatted_items,
            "counts": counts,
            "owned_counts": counts,
            "total_items": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_grouped_library(self, include_adult: bool = False) -> dict[str, Any]:
        """
        Returns a grouped snapshot of library items (movies, tv shows, adult scenes).
        """
        res_movies = self.get_library_tab_page("movies", page_size=20, include_adult=include_adult)
        res_tv = self.get_library_tab_page("tv", page_size=20, include_adult=include_adult)
        res_scenes = self.get_library_tab_page("scenes", page_size=20, include_adult=include_adult) if include_adult else {"items": []}
        
        return {
            "movies": res_movies["items"],
            "tv": res_tv["items"],
            "scenes": res_scenes["items"],
            "people": [],
            "counts": res_movies["counts"]
        }

    def get_library_filter_options(self, tab: str, filter_ownership: str = "owned", filter_status: str = "active") -> dict[str, Any]:
        """
        Retrieves filter options available for the specified library tab.
        """
        return {
            "genres": [],
            "years": [],
            "tags": []
        }

    def get_tag_groups(self, is_adult: bool = False) -> list[dict[str, Any]]:
        """
        Retrieves available tag groups.
        """
        return []

    def get_movie_collections(
        self,
        page: int = 1,
        page_size: Optional[int] = 40,
        search: str = "",
        tab: str = "movies",
        include_adult: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieves a paginated and filtered list of movie collections in the library.
        """
        from app.shared_kernel.language import LanguageService as LangHelper
        from app.domains.settings.models import UserSetting, SystemSetting
        from app.infrastructure.settings.formatter_config_adapter import load_formatter_config_from_db

        # Get ui language
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        try:
            setting = self.db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "ui_language").first()
            if not setting:
                setting = self.db.query(SystemSetting).filter(SystemSetting.key == "ui_language").first()
            if setting and setting.value:
                ui_lang = str(setting.value).split("-", 1)[0].strip().lower()
        except:
            pass

        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]
        
        query = self.db.query(MetadataMatch).join(
            MediaItem, MetadataMatch.media_item_id == MediaItem.id
        ).filter(
            MediaItem.status.in_(lib_statuses),
            MetadataMatch.collection_id != None
        )

        query = query.filter(MetadataMatch.is_adult == include_adult)

        if tab == "movies":
            query = query.filter(MetadataMatch.media_type == MediaType.MOVIE)

        matches = query.options(
            selectinload(MetadataMatch.collection).selectinload(MediaCollection.localizations),
            selectinload(MetadataMatch.localizations),
            selectinload(MetadataMatch.overrides)
        ).all()

        collections_map = {}
        normalized_search = search.strip().lower() if search else ""

        for match in matches:
            collection = match.collection
            if not collection:
                continue

            col_loc = LangHelper.get_best_localization(collection.localizations, ui_lang) if collection.localizations else None
            collection_title = col_loc.title if col_loc and col_loc.title else f"Collection {collection.external_id}"

            if normalized_search and normalized_search not in collection_title.lower():
                continue

            col_id = collection.id
            entry = collections_map.get(col_id)
            if not entry:
                entry = {
                    "id": f"collection_{collection.external_id}",
                    "tmdb_id": int(collection.external_id) if collection.external_id.isdigit() else 0,
                    "title": collection_title,
                    "overview": col_loc.overview if col_loc else None,
                    "poster_path": col_loc.poster_path if col_loc else None,
                    "has_local_poster": bool(col_loc and col_loc.local_poster_path),
                    "poster_remote_path": None,
                    "backdrop_path": collection.backdrop_path,
                    "owned_count": 0,
                    "total_count": 0,
                    "type": "collection",
                    "movies": []
                }
                collections_map[col_id] = entry

            loc = match.localizations[0] if match.localizations else None
            item = match.media_item
            o = next((ov for ov in match.overrides if ov.user_id == 1), None) if match.overrides else None
            
            title = (o.custom_title if (o and o.custom_title) else None) or (loc.title if loc else (item.filename if item else "Unknown"))
            poster_path = (o.custom_poster if (o and o.custom_poster) else None) or (loc.poster_path if loc else None)
            backdrop_path = (o.custom_backdrop if (o and o.custom_backdrop) else None) or (match.backdrop_path or None)
            rating = (o.user_rating if (o and o.user_rating is not None) else None)
            if rating is None:
                rating = match.rating_porndb or match.rating_tmdb or 0.0

            entry["owned_count"] += 1
            entry["movies"].append({
                "id": item.id if item else None,
                "title": title,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": poster_path,
                "backdrop_path": backdrop_path,
                "rating": rating,
                "rating_porndb": match.rating_porndb,
                "rating_imdb": match.rating_imdb,
                "type": match.media_type.value,
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "path": item.current_path if item else None,
                "is_favorite": o.is_favorite if o else False,
                "user_rating": o.user_rating if o else None
            })

        # Apply config filtering
        config = load_formatter_config_from_db(self.db)
        collection_mode = config.collection_folder_mode
        threshold = config.collection_folder_threshold

        filtered_collections = []
        for col in collections_map.values():
            if collection_mode == "never":
                continue
            elif collection_mode == "threshold":
                if col["owned_count"] >= threshold:
                    filtered_collections.append(col)
            else:
                if col["owned_count"] >= 1:
                    filtered_collections.append(col)

        sorted_collections = sorted(
            filtered_collections,
            key=lambda c: (-c["owned_count"], str(c["title"]).lower(), c["tmdb_id"])
        )

        total_items = len(sorted_collections)
        total_pages = (total_items + page_size - 1) // page_size if page_size and total_items > 0 else 1
        current_page = max(1, min(page, total_pages))
        
        start_idx = (current_page - 1) * page_size if page_size else 0
        end_idx = start_idx + page_size if page_size else total_items
        paged_collections = sorted_collections[start_idx:end_idx]

        return {
            "items": paged_collections,
            "total_items": total_items,
            "page": current_page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    # NOTE: get_people_group() has been moved to
    # app.domains.people.services.people_library_service.PeopleLibraryService

