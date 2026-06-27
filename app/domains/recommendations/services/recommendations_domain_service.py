from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.shared_kernel.enums import Provider, MediaType, ItemStatus, CustomListType
from app.domains.users.models import CustomList, CustomListItem
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch

class RecommendationsDomainService:
    @staticmethod
    def annotate_recommendations(
        items: List[Dict[str, Any]],
        bindings: Dict[tuple, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        annotated = []
        for item in items:
            tmdb_id = item.get("id")
            media_type = item.get("media_type") or ("movie" if item.get("title") else "tv")
            bind = bindings.get((media_type, tmdb_id), {})
            annotated.append({
                **item,
                "media_type": media_type,
                "in_library": bind.get("media_item_id") is not None,
                "media_item_id": bind.get("media_item_id"),
                "rating_imdb": bind.get("rating_imdb"),
                "rating_tmdb": bind.get("rating_tmdb") or item.get("vote_average"),
                "last_air_date": bind.get("last_air_date") or item.get("last_air_date"),
                "release_status": bind.get("release_status") or item.get("release_status"),
            })
        return annotated

    @staticmethod
    def fetch_watchlist_tmdb_ids(db: Session) -> List[int]:
        watchlist = db.query(CustomList).filter(CustomList.name == "Watchlist").first()
        if not watchlist:
            return []
        return [
            int(item.match.external_id) for item in watchlist.items
            if item.match and item.match.provider == Provider.TMDB and item.match.external_id.isdigit()
        ]

    @staticmethod
    def resolve_local_recommendation_bindings(db: Session, items: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
        movie_ids = set()
        tv_ids = set()
        for item in items or []:
            tmdb_id = item.get("id")
            if not tmdb_id:
                continue
            media_type = item.get("media_type") or ("movie" if item.get("title") else "tv")
            if media_type == "tv":
                tv_ids.add(str(tmdb_id))
            else:
                movie_ids.add(str(tmdb_id))

        if not movie_ids and not tv_ids:
            return {}

        bindings = {}

        # 1. Query TV matches directly from metadata_matches table
        if tv_ids:
            tv_rows = db.query(
                MetadataMatch.external_id,
                MetadataMatch.rating_tmdb,
                MetadataMatch.rating_imdb,
                MetadataMatch.last_air_date,
                MetadataMatch.release_status
            ).filter(
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.media_type == MediaType.TV,
                MetadataMatch.external_id.in_(tv_ids)
            ).all()
            for r in tv_rows:
                ext_id = int(r.external_id)
                bindings[("tv", ext_id)] = {
                    "media_item_id": ext_id,
                    "rating_imdb": r.rating_imdb,
                    "rating_tmdb": r.rating_tmdb,
                    "last_air_date": r.last_air_date.isoformat() if r.last_air_date else None,
                    "release_status": r.release_status,
                }

        # 2. Query Movie matches joined with MediaItem to verify active status
        if movie_ids:
            movie_rows = db.query(
                MediaItem.id,
                MetadataMatch.external_id,
                MetadataMatch.rating_tmdb,
                MetadataMatch.rating_imdb,
                MetadataMatch.release_status
            ).join(
                MetadataMatch, MetadataMatch.media_item_id == MediaItem.id
            ).filter(
                MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED]),
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.media_type == MediaType.MOVIE,
                MetadataMatch.external_id.in_(movie_ids)
            ).all()
            for r in movie_rows:
                ext_id = int(r.external_id)
                bindings[("movie", ext_id)] = {
                    "media_item_id": r.id,
                    "rating_imdb": r.rating_imdb,
                    "rating_tmdb": r.rating_tmdb,
                    "last_air_date": None,
                    "release_status": r.release_status,
                }

        return bindings
