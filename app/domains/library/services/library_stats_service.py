import logging
from typing import Any
from itertools import combinations
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.enums import ItemStatus, MediaType
from app.domains.library.schemas import LibraryStatsResponse

logger = logging.getLogger(__name__)

class LibraryStatsService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes >= 1024 ** 4:
            return f"{size_bytes / (1024 ** 4):.1f} TB"
        if size_bytes >= 1024 ** 3:
            return f"{size_bytes / (1024 ** 3):.1f} GB"
        return f"{size_bytes / (1024 ** 2):.0f} MB"

    def get_stats(self, include_adult: bool = False) -> LibraryStatsResponse:
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
            MetadataMatch.media_type == MediaType.SCENE,
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
                elif m.media_type == MediaType.SCENE:
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

        return LibraryStatsResponse(
            total_movies=total_movies,
            total_tv=total_tv,
            total_episodes=total_episodes,
            total_scenes=total_scenes,
            storage=storage_str,
            drive_count=len(drives) or 1,
            unmatched=unmatched,
            storage_breakdown={
                "movies": self._format_size(movie_bytes),
                "tv": self._format_size(tv_bytes),
                "scenes": self._format_size(adult_bytes),
                "extras": "0 MB"
            },
            manual_review_total=unmatched,
            manual_review_breakdown={
                "new": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.NEW).scalar() or 0,
                "error": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.ERROR).scalar() or 0,
                "uncertain": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.UNCERTAIN).scalar() or 0,
                "no_match": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.NO_MATCH).scalar() or 0,
                "multiple": self.db.query(func.count(MediaItem.id)).filter(MediaItem.status == ItemStatus.MULTIPLE).scalar() or 0
            },
            genre_distribution=genre_dist,
            genre_distribution_ids=genre_dist_ids,
            genre_labels=genre_labels,
            genre_constellation={"nodes": constellation_nodes, "links": constellation_links},
            decade_distribution=decade_dist
        )

