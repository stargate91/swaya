from typing import Tuple, Any, List
from sqlalchemy import and_
from sqlalchemy.orm import selectinload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride
from app.shared_kernel.enums import MediaType
from app.domains.library.services.listing.filter_params import ListingFilterParams
from app.domains.library.services.listing.builders.base import BaseQueryBuilder

class TvQueryBuilder(BaseQueryBuilder):
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
                MetadataMatch.media_type == MediaType.TV
            )
        else:
            parent_ids = set()
            current_parents = {
                r[0] for r in self.db.query(MetadataMatch.parent_id).join(
                    MediaItem, MetadataMatch.media_item_id == MediaItem.id
                ).filter(MediaItem.status.in_(self.lib_statuses), MetadataMatch.parent_id != None).all()
            }
            while current_parents:
                parent_ids.update(current_parents)
                current_parents = {
                    r[0] for r in self.db.query(MetadataMatch.parent_id).filter(
                        MetadataMatch.id.in_(current_parents), MetadataMatch.parent_id != None
                    ).all()
                }
            query = query.filter(
                MetadataMatch.id.in_(parent_ids),
                MetadataMatch.media_type == MediaType.TV,
                MetadataMatch.is_active == True,
            )

        query, joined_localization, joined_override = self._apply_common_filters(
            query, params, joined_localization, joined_override
        )

        query = self._apply_sorting(query, params, joined_localization, joined_override)
        total_items = query.count()
        items = query.offset((params.page - 1) * params.page_size).limit(params.page_size).all()
        return query, total_items, items
