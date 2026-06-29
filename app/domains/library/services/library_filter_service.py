import logging
from typing import Any, List
from sqlalchemy.orm import Session
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.users.models import Tag
from app.application.library.schemas import FilterOptionsResponse, TagGroupItem

logger = logging.getLogger(__name__)

class LibraryFilterService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_library_filter_options(self, tab: str, filter_ownership: str = "owned", filter_status: str = "active") -> FilterOptionsResponse:
        """
        Retrieves filter options available for the specified library tab.
        """
        is_adult = "adult" in tab.lower() or tab.lower() == "scenes"
        
        from app.domains.library.models import MediaItem
        from app.shared_kernel.enums import ItemStatus, MediaType
        from sqlalchemy import select
        
        lib_statuses = [ItemStatus.ORGANIZED, ItemStatus.RENAMED]
        
        # Determine the set of active, owned MetadataMatch IDs for the current tab
        if tab == "movies":
            match_ids_subquery = select(MetadataMatch.id).join(MediaItem).filter(
                MediaItem.status.in_(lib_statuses),
                MetadataMatch.media_type == MediaType.MOVIE,
                MetadataMatch.is_active == True,
                MetadataMatch.is_adult == is_adult
            ).scalar_subquery()
        elif tab in ("scenes", "adult_scenes"):
            match_ids_subquery = select(MetadataMatch.id).join(MediaItem).filter(
                MediaItem.status.in_(lib_statuses),
                MetadataMatch.media_type == MediaType.SCENE,
                MetadataMatch.is_active == True,
                MetadataMatch.is_adult == is_adult
            ).scalar_subquery()
        elif tab in ("tv", "series", "tv_shows", "adult_tv", "adult_series"):
            season_parent_ids = select(MetadataMatch.parent_id).join(MediaItem).filter(
                MediaItem.status.in_(lib_statuses),
                MetadataMatch.media_type == MediaType.EPISODE,
                MetadataMatch.is_active == True,
                MetadataMatch.is_adult == is_adult
            ).scalar_subquery()
            
            tv_ids = select(MetadataMatch.parent_id).filter(
                MetadataMatch.id.in_(season_parent_ids),
                MetadataMatch.parent_id != None
            ).scalar_subquery()
            
            match_ids_subquery = select(MetadataMatch.id).filter(
                MetadataMatch.id.in_(tv_ids),
                MetadataMatch.media_type == MediaType.TV,
                MetadataMatch.is_adult == is_adult
            ).scalar_subquery()
        else:
            match_ids_subquery = select(MetadataMatch.id).filter(
                MetadataMatch.is_adult == is_adult
            ).scalar_subquery()
            
        # 1. Fetch years
        query_years = self.db.query(MetadataMatch.release_date).filter(
            MetadataMatch.id.in_(match_ids_subquery),
            MetadataMatch.release_date != None
        ).distinct().all()
        
        years = sorted(list(set(r.release_date.year for r in query_years)), reverse=True)

        # 2. Fetch genres
        from app.shared_kernel.genre_utils import split_genres as _split_genres
        query_genres = self.db.query(MetadataLocalization.genres).filter(
            MetadataLocalization.match_id.in_(match_ids_subquery),
            MetadataLocalization.genres != None
        ).all()
        
        genres_set = set()
        for row in query_genres:
            if row.genres and isinstance(row.genres, list):
                for genre in _split_genres(row.genres):
                    if genre:
                        genres_set.add(genre.strip())
        genres = sorted(list(genres_set))

        tags_query = self.db.query(Tag).filter(Tag.is_adult == is_adult).all()
        tags = [
            {
                "id": t.id,
                "name": t.name,
                "color": t.color,
                "is_adult": t.is_adult
            }
            for t in tags_query
        ]

        return FilterOptionsResponse(
            genres=genres,
            years=years,
            tags=tags
        )

    def get_tag_groups(self, is_adult: bool = False) -> List[TagGroupItem]:
        """
        Retrieves available tag groups, with each tag enriched with its associated items.
        """
        from app.shared_kernel.enums import MediaType
        from app.domains.metadata.models import MetadataMatch, MetadataLocalization
        from app.domains.people.models import Person
        from app.domains.library.models import MediaItem
        from app.domains.users.models import UserOverride
        from app.domains.media_assets.services.images import image_processing_service

        tags_query = self.db.query(Tag).filter(Tag.is_adult == is_adult).all()
        if not tags_query:
            return []

        tags = []
        for t in tags_query:
            tag_data = {
                "id": t.id,
                "name": t.name,
                "color": t.color,
                "is_adult": t.is_adult,
                "movies": [],
                "tv": [],
                "people": [],
                "adult": [],
                "adult_tv": [],
                "adult_people": [],
                "adult_scenes": [],
            }

            for o in t.overrides:
                if o.person_id:
                    person = self.db.query(Person).filter(Person.id == o.person_id).first()
                    if person:
                        p_img = image_processing_service.resolve_image_url(person.profile_path, "people")
                        p_item = {
                            "id": person.id,
                            "title": person.name,
                            "name": person.name,
                            "poster_path": p_img,
                            "profile_path": p_img,
                            "type": "person",
                        }
                        if person.is_adult:
                            tag_data["adult_people"].append(p_item)
                        else:
                            tag_data["people"].append(p_item)
                else:
                    match = None
                    if o.metadata_match_id:
                        match = self.db.query(MetadataMatch).filter(MetadataMatch.id == o.metadata_match_id).first()
                    elif o.media_item_id:
                        match = self.db.query(MetadataMatch).filter(
                            MetadataMatch.media_item_id == o.media_item_id,
                            MetadataMatch.is_active == True
                        ).first()

                    if match:
                        loc = self.db.query(MetadataLocalization).filter(MetadataLocalization.match_id == match.id).first()
                        item = match.media_item

                        title = (o.custom_title if o.custom_title else None) or (loc.title if loc else (item.filename if item else "Unknown"))
                        poster_path = (o.custom_poster if o.custom_poster else None) or (loc.local_poster_path if (loc and loc.local_poster_path) else (loc.poster_path if loc else None))
                        resolved_poster = image_processing_service.resolve_image_url(poster_path, "posters")

                        m_item = {
                            "id": item.id if item else f"stash_{match.external_id}" if match.media_type == MediaType.SCENE else f"tmdb_{match.external_id}",
                            "title": title,
                            "poster_path": resolved_poster,
                            "type": match.media_type.value,
                            "year": match.release_date.year if match.release_date else None,
                            "is_favorite": o.is_favorite,
                            "user_rating": o.user_rating,
                        }

                        if match.media_type == MediaType.MOVIE:
                            if match.is_adult:
                                tag_data["adult"].append(m_item)
                            else:
                                tag_data["movies"].append(m_item)
                        elif match.media_type == MediaType.TV:
                            if match.is_adult:
                                tag_data["adult_tv"].append(m_item)
                            else:
                                tag_data["tv"].append(m_item)
                        elif match.media_type == MediaType.SCENE:
                            tag_data["adult_scenes"].append(m_item)

            tags.append(tag_data)

        return [
            TagGroupItem(
                id=1,
                name="General" if not is_adult else "Adult",
                tags=tags
            )
        ]
