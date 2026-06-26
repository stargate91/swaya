import logging
from typing import Dict, Any

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.application.metadata.schemas import MetadataResolveRequest, BulkResolveRequest
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class MetadataResolver:
    def __init__(self, db: Any, scrapers: Any, tmdb: Any):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = tmdb

    def resolve_item(self, request: MetadataResolveRequest) -> Dict[str, Any]:
        db = self.db
        item_id = request.item_id
        external_id = request.tmdb_id or request.external_id
        media_type_str = request.type or request.media_type or "movie"
        season_number = request.season_number
        episode_number = request.episode_number
        provider_str = request.provider or "tmdb"

        if not item_id or not external_id:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("item_id and external_id (tmdb_id) are required")

        item = db.query(MediaItem).filter(MediaItem.id == int(item_id)).first()
        if not item:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Media item not found")

        # Delete any existing metadata match mappings for this physical item
        db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
        db.flush()

        # Parse provider and media type
        try:
            provider = Provider(provider_str.lower())
        except ValueError:
            provider = Provider.TMDB

        try:
            mtype = MediaType(media_type_str.lower())
        except ValueError:
            mtype = MediaType.MOVIE

        # Promote TV show match to EPISODE if the item is an episode or we have season/episode numbers
        inferred_type = str((item.parsed_info or {}).get("type") or "").lower()
        if mtype == MediaType.TV and (inferred_type == "episode" or season_number is not None or episode_number is not None):
            if season_number is None:
                season_number = (item.parsed_info or {}).get("season")
            if episode_number is None:
                episode_number = (item.parsed_info or {}).get("episode")
            
            if season_number is not None:
                try:
                    season_number = int(season_number)
                except (ValueError, TypeError):
                    pass
            if episode_number is not None:
                try:
                    if isinstance(episode_number, list):
                        episode_number = [int(x) for x in episode_number if str(x).isdigit()]
                    elif str(episode_number).isdigit():
                        episode_number = int(episode_number)
                except (ValueError, TypeError):
                    pass

            if season_number is not None and episode_number is not None:
                mtype = MediaType.EPISODE

        if provider in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
            scraper = None
            if provider == Provider.STASHDB:
                scraper = self.scrapers.adult(Provider.STASHDB, db)
            elif provider == Provider.PORNDB:
                scraper = self.scrapers.adult(Provider.PORNDB, db)
            elif provider == Provider.FANSDB:
                scraper = self.scrapers.adult(Provider.FANSDB, db)

            if not scraper:
                from app.shared_kernel.exceptions import BadRequestException
                raise BadRequestException("Selected adult scraper is not configured")

            if provider == Provider.PORNDB and mtype == MediaType.MOVIE:
                movie_data = scraper.fetch_movie(str(external_id))
                if not movie_data:
                    from app.shared_kernel.exceptions import BadRequestException
                    raise BadRequestException(f"Failed to fetch movie details from {provider.value}")

                from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer
                normalized = ScraperNormalizer.normalize_porndb_movie(movie_data)
                match = self.scrapers.persist_adult_scene(
                    db, provider, str(movie_data["id"]), normalized, media_type=MediaType.MOVIE, media_item_id=item.id
                )
                item.status = ItemStatus.MATCHED
                db.commit()
                return {"status": "success", "item_id": item.id, "match_id": match.id}

            scene_data = scraper.fetch_scene(str(external_id))
            if not scene_data:
                from app.shared_kernel.exceptions import BadRequestException
                raise BadRequestException(f"Failed to fetch scene details from {provider.value}")

            normalized = self.scrapers.normalize_adult_scene(provider, scene_data)
            match = self.scrapers.persist_adult_scene(db, provider, str(scene_data["id"]), normalized, media_item_id=item.id)
            item.status = ItemStatus.MATCHED
            db.commit()
            return {"status": "success", "item_id": item.id, "match_id": match.id}

        # Otherwise standard TMDB resolution
        # Check if match with same provider, external_id, and media_type already exists
        match = db.query(MetadataMatch).filter(
            MetadataMatch.media_item_id == item.id,
            MetadataMatch.provider == provider,
            MetadataMatch.external_id == str(external_id),
            MetadataMatch.media_type == mtype
        ).first()

        if match:
            match.is_active = True
            if request.is_adult:
                match.is_adult = True
            if season_number is not None:
                match.season_number = season_number
            if episode_number is not None:
                match.episode_number = episode_number
        else:
            match = MetadataMatch(
                media_item_id=item.id,
                provider=provider,
                external_id=str(external_id),
                media_type=mtype,
                season_number=season_number,
                episode_number=episode_number,
                confidence_score=1.0,
                is_active=True,
                is_adult=bool(request.is_adult)
            )
            db.add(match)
        db.flush()

        item.status = ItemStatus.MATCHED

        # Enrich item metadata
        try:
            self.scrapers.enrich_mainstream(db, item, DEFAULT_FALLBACK_LANGUAGE, commit=True)
        except Exception as e:
            logger.error(f"Enrichment failed during manual resolve: {e}")
            db.commit()

        return {"status": "success", "item_id": item.id, "match_id": match.id}

    def bulk_resolve(self, request: BulkResolveRequest) -> Dict[str, Any]:
        resolutions = request.resolutions or []
        count = 0
        for res in resolutions:
            try:
                ret = self.resolve_item(res)
                if "error" not in ret:
                    count += 1
            except Exception as e:
                logger.error(f"Bulk resolve error for item {res.item_id}: {e}")
        return {"status": "success", "resolved_count": count}
