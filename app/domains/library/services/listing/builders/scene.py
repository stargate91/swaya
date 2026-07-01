from typing import Tuple, Any, List
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import selectinload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride
from app.shared_kernel.enums import MediaType
from app.domains.library.services.listing.filter_params import ListingFilterParams
from app.domains.library.services.listing.builders.base import BaseQueryBuilder

class SceneQueryBuilder(BaseQueryBuilder):
    def build_query(self, params: ListingFilterParams) -> Tuple[Any, int, List[MetadataMatch]]:
        query = self.db.query(MetadataMatch).outerjoin(
            MediaItem, MetadataMatch.media_item_id == MediaItem.id
        ).options(
            selectinload(MetadataMatch.localizations),
            selectinload(MetadataMatch.media_item),
            selectinload(MetadataMatch.overrides)
        )

        joined_localization = False
        joined_override = False

        if params.filter_ownership in ("tracked", "unowned"):
            query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
            joined_override = True
            query = query.filter(
                MetadataMatch.media_item_id == None,
                UserOverride.is_tracked == True,
                MetadataMatch.media_type == MediaType.SCENE
            )
        elif params.filter_ownership == "all":
            query = query.outerjoin(UserOverride, and_(UserOverride.metadata_match_id == MetadataMatch.id, UserOverride.user_id == self.current_user_id))
            joined_override = True
            query = query.filter(
                or_(
                    and_(MetadataMatch.media_item_id != None, MediaItem.status.in_(self.lib_statuses)),
                    and_(MetadataMatch.media_item_id == None, UserOverride.is_tracked == True)
                ),
                MetadataMatch.is_active == True,
                MetadataMatch.media_type == MediaType.SCENE
            )
        else:
            query = query.filter(
                MetadataMatch.media_item_id != None,
                MediaItem.status.in_(self.lib_statuses),
                MetadataMatch.is_active == True,
            )

        if params.selected_performer_id:
            from app.domains.people.models import MediaPersonLink
            query = query.join(MetadataMatch.people_links).filter(MediaPersonLink.person_id == params.selected_performer_id)

        if params.selected_studio_id:
            from app.domains.metadata.models import Studio
            query = query.join(MetadataMatch.studios).filter(Studio.id == params.selected_studio_id)

        query, joined_localization, joined_override = self._apply_common_filters(
            query, params, joined_localization, joined_override
        )

        if params.filter_ownership not in ("tracked", "unowned", "all"):
            canonical_match_ids = self.db.query(
                func.min(MetadataMatch.id)
            ).filter(
                MetadataMatch.media_item_id != None,
                MetadataMatch.is_active == True,
                MetadataMatch.is_adult == params.include_adult,
                MetadataMatch.media_type == MediaType.SCENE
            ).group_by(MetadataMatch.media_item_id).subquery()
            query = query.filter(MetadataMatch.id.in_(canonical_match_ids))
        elif params.filter_ownership == "all":
            canonical_match_ids = self.db.query(
                func.min(MetadataMatch.id)
            ).filter(
                MetadataMatch.media_item_id != None,
                MetadataMatch.is_active == True,
                MetadataMatch.is_adult == params.include_adult,
                MetadataMatch.media_type == MediaType.SCENE
            ).group_by(MetadataMatch.media_item_id).subquery()
            query = query.filter(
                or_(
                    MetadataMatch.id.in_(canonical_match_ids),
                    and_(MetadataMatch.media_item_id == None, UserOverride.is_tracked == True)
                )
            )

        query = self._apply_sorting(query, params, joined_localization, joined_override)
        total_items = query.count()
        items = query.offset((params.page - 1) * params.page_size).limit(params.page_size).all()
        return query, total_items, items
