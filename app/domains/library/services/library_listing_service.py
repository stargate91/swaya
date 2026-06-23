import logging
from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy import func, or_, and_, desc
from sqlalchemy.orm import Session, selectinload, joinedload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.users.models import UserOverride, Tag, user_override_tags
from app.domains.people.models import MediaPersonLink
from app.shared_kernel.enums import ItemStatus, MediaType
from app.shared_kernel.user_context import get_current_user_id
from app.domains.library.schemas import (
    ContinueWatchingItem,
    LibraryTabResponse,
    GroupedLibraryResponse,
)

logger = logging.getLogger(__name__)

class LibraryListingService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_continue_watching(self, limit: int = 12, include_adult: bool = False) -> List[ContinueWatchingItem]:
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
            
            results.append(ContinueWatchingItem(
                id=item.id,
                title=title,
                tv_title=tv_title,
                episode_title=episode_title,
                type=match.media_type.value if match else "movie",
                season_number=match.season_number if match else None,
                episode_number=match.episode_number if match else None,
                tv_tmdb_id=tv_tmdb_id,
                tmdb_id=int(match.external_id) if (match and match.external_id.isdigit()) else None,
                backdrop_path=match.backdrop_path if match else None,
                still_path=match.still_path if match else None,
                resume_position=o.resume_position,
                duration=item.duration or 0,
                is_watched=o.is_watched,
                last_watched_at=o.last_watched_at.isoformat() if o.last_watched_at else None,
            ))
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
    ) -> LibraryTabResponse:
        """
        Retrieves a paginated, filtered, and sorted list of library items for a specific UI tab.
        """
        query = self.db.query(MetadataMatch).outerjoin(
            MediaItem, MetadataMatch.media_item_id == MediaItem.id
        ).options(
            selectinload(MetadataMatch.localizations),
            selectinload(MetadataMatch.media_item),
            selectinload(MetadataMatch.overrides),
            selectinload(MetadataMatch.people).selectinload(MediaPersonLink.person)
        )

        joined_localization = False
        joined_override = False
        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]

        # Ownership filter
        if filter_ownership in ("tracked", "unowned"):
            query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
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
        if tab in ("tv", "adult_tv"):
            query = query.filter(MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE, MediaType.SEASON]))
        elif tab in ("scenes", "adult_scenes"):
            query = query.filter(MetadataMatch.media_type == MediaType.SCENE)
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
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            if filter_favorite == "favorite":
                query = query.filter(UserOverride.is_favorite == True)
            else:
                query = query.filter(or_(UserOverride.is_favorite == False, UserOverride.is_favorite == None))

        # Watched filter
        if filter_watched in ("watched", "unwatched"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
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
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            query = query.join(user_override_tags, user_override_tags.c.user_override_id == UserOverride.id)\
                         .join(Tag, Tag.id == user_override_tags.c.tag_id)\
                         .filter(Tag.name.in_(selected_tags))

        # Sorting
        if sort_by in ("title_asc", "title_desc", "default"):
            if not joined_localization:
                query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
                joined_localization = True
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            
            val_col = func.coalesce(UserOverride.custom_title, MetadataLocalization.title, MediaItem.filename)
            if sort_by == "title_desc":
                query = query.order_by(desc(val_col))
            else:
                query = query.order_by(val_col.asc())
        elif sort_by in ("date_desc", "release_date_desc", "year_desc"):
            query = query.order_by(desc(MetadataMatch.release_date))
        elif sort_by in ("date_asc", "release_date_asc", "year_asc"):
            query = query.order_by(MetadataMatch.release_date.asc())
        elif sort_by in ("rating_desc", "user_rating_desc"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            query = query.order_by(desc(func.coalesce(
                UserOverride.user_rating,
                MetadataMatch.rating_porndb,
                MetadataMatch.rating_tmdb,
            )))
        elif sort_by == "user_rating_asc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            query = query.order_by(func.coalesce(
                UserOverride.user_rating,
                MetadataMatch.rating_porndb,
                MetadataMatch.rating_tmdb,
            ).asc())
        elif sort_by == "duration_desc":
            query = query.order_by(desc(MediaItem.duration))
        elif sort_by == "duration_asc":
            query = query.order_by(MediaItem.duration.asc())
        elif sort_by in ("file_size_desc", "size_desc"):
            query = query.order_by(desc(MediaItem.size))
        elif sort_by in ("file_size_asc", "size_asc"):
            query = query.order_by(MediaItem.size.asc())
        elif sort_by == "last_watched_desc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            query = query.order_by(desc(UserOverride.last_watched_at))
        elif sort_by == "last_watched_asc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == get_current_user_id()))
                joined_override = True
            query = query.order_by(UserOverride.last_watched_at.asc())

        total_items = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        formatted_items = []
        for match in items:
            loc = match.localizations[0] if match.localizations else None
            item = match.media_item
            
            o = next((ov for ov in match.overrides if ov.user_id == get_current_user_id()), None) if match.overrides else None
            title = (o.custom_title if (o and o.custom_title) else None) or (loc.title if loc else (item.filename if item else "Unknown"))
            poster_path = (o.custom_poster if (o and o.custom_poster) else None) or (loc.poster_path if loc else None)
            backdrop_path = (o.custom_backdrop if (o and o.custom_backdrop) else None) or (match.backdrop_path or None)
            rating = (o.user_rating if (o and o.user_rating is not None) else None)
            if rating is None:
                rating = match.rating_porndb or match.rating_tmdb or 0.0

            from app.domains.media_assets.services.images import image_processing_service
            resolved_poster = image_processing_service.resolve_image_url(poster_path, "posters")
            resolved_backdrop = image_processing_service.resolve_image_url(backdrop_path, "backdrops")

            people_list = []
            if match.people:
                for link in sorted(match.people, key=lambda x: x.order):
                    person = link.person
                    if person:
                        people_list.append({
                            "id": person.id,
                            "name": person.name,
                            "gender": person.gender,
                            "role": link.role.value if hasattr(link.role, "value") else str(link.role),
                        })

            formatted_items.append({
                "id": item.id if item else f"stash_{match.external_id}" if match.media_type == MediaType.SCENE else f"tmdb_{match.external_id}",
                "title": title,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": resolved_poster,
                "backdrop_path": resolved_backdrop,
                "rating": rating,
                "rating_porndb": match.rating_porndb,
                "rating_imdb": match.rating_imdb,
                "type": match.media_type.value,
                "path": item.current_path if item else None,
                "duration": (item.duration or 0.0) if item else 0.0,
                "size": (item.size or 0) if item else 0,
                "in_library": item is not None,
                "release_date": match.release_date.isoformat() if match.release_date else None,
                "user_rating": o.user_rating if o else None,
                "people": people_list,
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
            MediaItem.status.in_(lib_statuses), MetadataMatch.media_type == MediaType.SCENE
        )
        movies_cnt_query = movies_cnt_query.filter(MetadataMatch.is_adult == include_adult)
        tv_cnt_query = tv_cnt_query.filter(MetadataMatch.is_adult == include_adult)
        adult_cnt_query = adult_cnt_query.filter(MetadataMatch.is_adult == include_adult)

        if include_adult:
            counts = {
                "adult": movies_cnt_query.count(),
                "adult_tv": tv_cnt_query.count(),
                "adult_scenes": adult_cnt_query.count(),
                "adult_people": 0
            }
        else:
            counts = {
                "movies": movies_cnt_query.count(),
                "tv": tv_cnt_query.count(),
                "scenes": adult_cnt_query.count(),
                "people": 0
            }

        return LibraryTabResponse(
            tab=tab,
            items=formatted_items,
            counts=counts,
            owned_counts=counts,
            total_items=total_items,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_grouped_library(self, include_adult: bool = False) -> GroupedLibraryResponse:
        """
        Returns a grouped snapshot of library items (movies, tv shows, adult scenes).
        """
        res_movies = self.get_library_tab_page("movies", page_size=20, include_adult=include_adult)
        res_tv = self.get_library_tab_page("tv", page_size=20, include_adult=include_adult)
        res_scenes = self.get_library_tab_page("scenes", page_size=20, include_adult=include_adult) if include_adult else LibraryTabResponse(
            tab="scenes", items=[], counts=res_movies.counts, owned_counts=res_movies.counts, total_items=0, page=1, page_size=20, total_pages=1
        )
        
        return GroupedLibraryResponse(
            movies=res_movies.items,
            tv=res_tv.items,
            scenes=res_scenes.items,
            people=[],
            counts=res_movies.counts
        )

