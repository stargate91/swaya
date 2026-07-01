import logging
from typing import Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.users.models import Tag
from app.domains.library.schemas import FilterOptionsResponse, TagGroupItem
from app.shared_kernel.ports.user_repository_port import UserRepositoryPort

logger = logging.getLogger(__name__)

class LibraryFilterService:
    def __init__(self, db_session: Session, user_repository: Optional[UserRepositoryPort] = None):
        self.db = db_session
        self.user_repository = user_repository

    def get_library_filter_options(self, tab: str, filter_ownership: str = "owned", filter_status: str = "active") -> FilterOptionsResponse:
        """
        Retrieves filter options available for the specified library tab.
        """
        is_adult = "adult" in tab.lower() or tab.lower() == "scenes"
        
        from app.domains.library.models import MediaItem
        from app.shared_kernel.enums import ItemStatus, MediaType
        from sqlalchemy import select
        
        lib_statuses = [ItemStatus.ORGANIZED, ItemStatus.RENAMED]
        
        # Determine the set of active MetadataMatch IDs for the current tab based on ownership
        if filter_ownership in ("tracked", "unowned"):
            from app.domains.users.models import UserOverride
            from app.shared_kernel.user_context import get_current_user_id
            current_uid = get_current_user_id() or 1
            
            if tab == "movies":
                match_ids_subquery = select(MetadataMatch.id).join(UserOverride, UserOverride.metadata_match_id == MetadataMatch.id).filter(
                    MetadataMatch.media_item_id == None,
                    UserOverride.is_tracked == True,
                    UserOverride.user_id == current_uid,
                    MetadataMatch.media_type == MediaType.MOVIE,
                    MetadataMatch.is_adult == is_adult
                ).scalar_subquery()
            elif tab in ("scenes", "adult_scenes"):
                match_ids_subquery = select(MetadataMatch.id).join(UserOverride, UserOverride.metadata_match_id == MetadataMatch.id).filter(
                    MetadataMatch.media_item_id == None,
                    UserOverride.is_tracked == True,
                    UserOverride.user_id == current_uid,
                    MetadataMatch.media_type == MediaType.SCENE,
                    MetadataMatch.is_adult == is_adult
                ).scalar_subquery()
            elif tab in ("tv", "series", "tv_shows", "adult_tv", "adult_series"):
                match_ids_subquery = select(MetadataMatch.id).join(UserOverride, UserOverride.metadata_match_id == MetadataMatch.id).filter(
                    MetadataMatch.media_item_id == None,
                    UserOverride.is_tracked == True,
                    UserOverride.user_id == current_uid,
                    MetadataMatch.media_type == MediaType.TV,
                    MetadataMatch.is_adult == is_adult
                ).scalar_subquery()
            else:
                match_ids_subquery = select(MetadataMatch.id).join(UserOverride, UserOverride.metadata_match_id == MetadataMatch.id).filter(
                    MetadataMatch.media_item_id == None,
                    UserOverride.is_tracked == True,
                    UserOverride.user_id == current_uid,
                    MetadataMatch.is_adult == is_adult
                ).scalar_subquery()
        else:
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

        performers = []
        studios = []
        hair_colors = []
        ethnicities = []
        eye_colors = []
        tattoos = []
        piercings = []
        breast_types = []
        if is_adult:
            from app.domains.people.models import Person, MediaPersonLink
            from app.domains.metadata.models import Studio
            from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter

            settings_adapter = DbSettingsAdapter(self.db)
            gender_pref = settings_adapter.get_setting("adult_gender_preference")

            performers_query = self.db.query(Person.id, Person.name).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery)
            )

            if gender_pref == "female":
                performers_query = performers_query.filter(Person.gender.in_([1, "1"]))
            elif gender_pref == "male":
                performers_query = performers_query.filter(Person.gender.in_([2, "2"]))

            performers_query = performers_query.distinct().order_by(Person.name.asc()).all()
            performers = [{"id": r.id, "name": r.name} for r in performers_query]

            active_studios = self.db.query(Studio).join(
                Studio.matches
            ).filter(
                MetadataMatch.id.in_(match_ids_subquery)
            ).distinct().all()
            
            studio_map = {}
            for s in active_studios:
                studio_map[s.id] = s
                if s.parent_studio_id:
                    if s.parent_studio_id not in studio_map:
                        parent = s.parent_studio or self.db.query(Studio).filter(Studio.id == s.parent_studio_id).first()
                        if parent:
                            studio_map[parent.id] = parent
            
            # Group into parents and children
            parents = [s for s in studio_map.values() if s.parent_studio_id is None]
            children = [s for s in studio_map.values() if s.parent_studio_id is not None]
            
            # Sort parents alphabetically
            parents.sort(key=lambda x: (x.name or "").lower())
            
            # Group children by their parent_studio_id
            children_by_parent = {}
            for c in children:
                children_by_parent.setdefault(c.parent_studio_id, []).append(c)
                
            # Sort each group of children alphabetically
            for p_id in children_by_parent:
                children_by_parent[p_id].sort(key=lambda x: (x.name or "").lower())
                
            hierarchical_studios = []
            for p in parents:
                hierarchical_studios.append((p, False))
                # Add children of this parent
                if p.id in children_by_parent:
                    for c in children_by_parent[p.id]:
                        hierarchical_studios.append((c, True))
                        
            # Add any orphaned children that didn't find their parent in parents list
            orphaned_children = [c for c in children if c.parent_studio_id not in studio_map]
            if orphaned_children:
                orphaned_children.sort(key=lambda x: (x.name or "").lower())
                for c in orphaned_children:
                    hierarchical_studios.append((c, False))
                    
            # Build final list with indentation for children
            studios = []
            for s, is_child in hierarchical_studios:
                name = s.name or ""
                if is_child:
                    name = f"  ↳ {name}"
                studios.append({"id": s.id, "name": name})

            hair_colors_query = self.db.query(Person.hair_color).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery),
                Person.hair_color != None,
                Person.hair_color != ""
            ).distinct().order_by(Person.hair_color.asc()).all()
            hair_colors = [r[0] for r in hair_colors_query]

            ethnicities_query = self.db.query(Person.ethnicity).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery),
                Person.ethnicity != None,
                Person.ethnicity != ""
            ).distinct().order_by(Person.ethnicity.asc()).all()
            ethnicities = [r[0] for r in ethnicities_query]

            eye_colors_query = self.db.query(Person.eye_color).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery),
                Person.eye_color != None,
                Person.eye_color != ""
            ).distinct().order_by(Person.eye_color.asc()).all()
            eye_colors = [r[0] for r in eye_colors_query]

            tattoos_query = self.db.query(Person.tattoos).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery),
                Person.tattoos != None,
                Person.tattoos != ""
            ).distinct().order_by(Person.tattoos.asc()).all()
            tattoos = [r[0] for r in tattoos_query]

            piercings_query = self.db.query(Person.piercings).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery),
                Person.piercings != None,
                Person.piercings != ""
            ).distinct().order_by(Person.piercings.asc()).all()
            piercings = [r[0] for r in piercings_query]

            breast_types_query = self.db.query(Person.breast_type).join(
                MediaPersonLink, MediaPersonLink.person_id == Person.id
            ).filter(
                MediaPersonLink.match_id.in_(match_ids_subquery),
                Person.breast_type != None,
                Person.breast_type != ""
            ).distinct().order_by(Person.breast_type.asc()).all()
            breast_types = [r[0] for r in breast_types_query]

        return FilterOptionsResponse(
            genres=genres,
            years=years,
            tags=tags,
            performers=performers,
            studios=studios,
            hair_colors=hair_colors,
            ethnicities=ethnicities,
            eye_colors=eye_colors,
            tattoos=tattoos,
            piercings=piercings,
            breast_types=breast_types
        )

    def get_tag_groups(self, is_adult: bool = False) -> List[TagGroupItem]:
        """
        Retrieves available tag groups, with each tag enriched with its associated items.
        """
        # Self-healing: Mark tags as adult if they are linked to adult items/performers
        if self.user_repository:
            self.user_repository.auto_heal_adult_tags()

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
                        
                        # Dynamically resolve an automatic backdrop from the person's linked media items
                        p_backdrop = None
                        for link in person.media_links:
                            if link.match and (link.match.local_backdrop_path or link.match.backdrop_path):
                                p_backdrop = image_processing_service.resolve_image_url(
                                    link.match.local_backdrop_path or link.match.backdrop_path, 
                                    "backdrops"
                                )
                                break

                        p_item = {
                            "id": person.id,
                            "title": person.name,
                            "name": person.name,
                            "poster_path": p_img,
                            "profile_path": p_img,
                            "backdrop_path": p_backdrop,
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

                        resolved_backdrop = image_processing_service.resolve_image_url(
                            match.local_backdrop_path or match.backdrop_path, 
                            "backdrops"
                        )
                        resolved_still = image_processing_service.resolve_image_url(
                            match.local_still_path or match.still_path, 
                            "stills"
                        )

                        m_item = {
                            "id": item.id if item else f"stash_{match.external_id}" if match.media_type == MediaType.SCENE else f"tmdb_{match.external_id}",
                            "title": title,
                            "poster_path": resolved_poster,
                            "backdrop_path": resolved_backdrop,
                            "still_path": resolved_still or resolved_backdrop,
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
