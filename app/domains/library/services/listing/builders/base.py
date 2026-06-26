from datetime import datetime
from typing import Tuple, Any, List
from sqlalchemy import func, or_, and_, desc
from sqlalchemy.orm import Session, joinedload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.users.models import UserOverride, Tag, user_override_tags
from app.domains.people.models import MediaPersonLink
from app.shared_kernel.enums import ItemStatus, MediaType, Provider
from app.shared_kernel.user_context import get_current_user_id
from app.domains.library.services.listing.filter_params import ListingFilterParams

class BaseQueryBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.current_user_id = get_current_user_id()
        self.lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]

    def _apply_common_filters(
        self,
        query: Any,
        params: ListingFilterParams,
        joined_localization: bool,
        joined_override: bool
    ) -> Tuple[Any, bool, bool]:
        # NSFW filter
        query = query.filter(MetadataMatch.is_adult == params.include_adult)

        # Search filter
        if params.search:
            if not joined_localization:
                query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
                joined_localization = True
            if params.filter_ownership == "tracked":
                query = query.filter(MetadataLocalization.title.ilike(f"%{params.search}%"))
            else:
                query = query.filter(
                    or_(
                        MetadataLocalization.title.ilike(f"%{params.search}%"),
                        MediaItem.filename.ilike(f"%{params.search}%")
                    )
                )

        # Favorite filter
        if params.filter_favorite in ("favorite", "not_favorite"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            if params.filter_favorite == "favorite":
                query = query.filter(UserOverride.is_favorite == True)
            else:
                query = query.filter(or_(UserOverride.is_favorite == False, UserOverride.is_favorite == None))

        # Watched filter
        if params.filter_watched in ("watched", "unwatched"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            if params.filter_watched == "watched":
                query = query.filter(UserOverride.is_watched == True)
            else:
                query = query.filter(or_(UserOverride.is_watched == False, UserOverride.is_watched == None))

        # Genre filter
        if params.selected_genre:
            if not joined_localization:
                query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
                joined_localization = True
            query = query.filter(MetadataLocalization.genres.like(f'%"{params.selected_genre}"%'))

        # Decade filter
        if params.selected_decade and params.selected_decade.endswith("s") and params.selected_decade[:-1].isdigit():
            start_year = int(params.selected_decade[:-1])
            end_year = start_year + 9
            query = query.filter(
                MetadataMatch.release_date >= datetime(start_year, 1, 1),
                MetadataMatch.release_date <= datetime(end_year, 12, 31)
            )

        # Year filter
        if params.selected_year:
            query = query.filter(
                MetadataMatch.release_date >= datetime(params.selected_year, 1, 1),
                MetadataMatch.release_date <= datetime(params.selected_year, 12, 31)
            )

        # Tags filter
        if params.selected_tags:
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            query = query.join(user_override_tags, user_override_tags.c.user_override_id == UserOverride.id)\
                         .join(Tag, Tag.id == user_override_tags.c.tag_id)\
                         .filter(Tag.name.in_(params.selected_tags))

        return query, joined_localization, joined_override

    def _apply_sorting(
        self,
        query: Any,
        params: ListingFilterParams,
        joined_localization: bool,
        joined_override: bool
    ) -> Any:
        if params.sort_by in ("title_asc", "title_desc", "default"):
            if not joined_localization:
                query = query.outerjoin(MetadataLocalization, MetadataLocalization.match_id == MetadataMatch.id)
                joined_localization = True
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            
            val_col = func.coalesce(UserOverride.custom_title, MetadataLocalization.title, MediaItem.filename)
            if params.sort_by == "title_desc":
                query = query.order_by(desc(val_col))
            else:
                query = query.order_by(val_col.asc())
        elif params.sort_by in ("date_desc", "release_date_desc", "year_desc"):
            query = query.order_by(desc(MetadataMatch.release_date))
        elif params.sort_by in ("date_asc", "release_date_asc", "year_asc"):
            query = query.order_by(MetadataMatch.release_date.asc())
        elif params.sort_by in ("rating_desc", "user_rating_desc"):
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            query = query.order_by(desc(func.coalesce(
                UserOverride.user_rating,
                MetadataMatch.rating_porndb,
                MetadataMatch.rating_tmdb,
            )))
        elif params.sort_by == "user_rating_asc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            query = query.order_by(func.coalesce(
                UserOverride.user_rating,
                MetadataMatch.rating_porndb,
                MetadataMatch.rating_tmdb,
            ).asc())
        elif params.sort_by == "rating_imdb_desc":
            query = query.order_by(desc(MetadataMatch.rating_imdb))
        elif params.sort_by == "rating_imdb_asc":
            query = query.order_by(MetadataMatch.rating_imdb.asc())
        elif params.sort_by == "duration_desc":
            query = query.order_by(desc(MediaItem.duration))
        elif params.sort_by == "duration_asc":
            query = query.order_by(MediaItem.duration.asc())
        elif params.sort_by in ("file_size_desc", "size_desc"):
            query = query.order_by(desc(MediaItem.size))
        elif params.sort_by in ("file_size_asc", "size_asc"):
            query = query.order_by(MediaItem.size.asc())
        elif params.sort_by == "last_watched_desc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            query = query.order_by(desc(UserOverride.last_watched_at))
        elif params.sort_by == "last_watched_asc":
            if not joined_override:
                query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
                joined_override = True
            query = query.order_by(UserOverride.last_watched_at.asc())

        return query

    def format_results(self, items: List[MetadataMatch]) -> List[dict]:
        match_ids = [m.id for m in items]
        overrides_dict = {}
        people_links_dict = {}
        if match_ids:
            ovs = self.db.query(UserOverride).filter(
                UserOverride.user_id == self.current_user_id,
                UserOverride.metadata_match_id.in_(match_ids)
            ).all()
            for ov in ovs:
                overrides_dict[ov.metadata_match_id] = ov
                
            links = self.db.query(MediaPersonLink).options(
                joinedload(MediaPersonLink.person)
            ).filter(MediaPersonLink.match_id.in_(match_ids)).all()
            for link in links:
                people_links_dict.setdefault(link.match_id, []).append(link)

        formatted_items = []
        for match in items:
            loc = match.localizations[0] if match.localizations else None
            item = match.media_item
            
            o = overrides_dict.get(match.id)
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
            match_people = people_links_dict.get(match.id, [])
            if match_people:
                for link in sorted(match_people, key=lambda x: x.order):
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
                "tmdb_id": int(match.external_id) if (match.provider == Provider.TMDB and match.external_id and match.external_id.isdigit()) else None,
                "tv_tmdb_id": int(match.external_id) if (match.media_type == MediaType.TV and match.provider == Provider.TMDB and match.external_id and match.external_id.isdigit()) else None,
                "path": item.current_path if item else None,
                "duration": (item.duration or 0.0) if item else 0.0,
                "size": (item.size or 0) if item else 0,
                "in_library": item is not None,
                "release_date": match.release_date.isoformat() if match.release_date else None,
                "user_rating": o.user_rating if o else None,
                "people": people_list,
            })
        return formatted_items
