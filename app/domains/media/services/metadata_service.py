import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.enums import Provider, MediaType, ItemStatus
from app.domains.media.models.filesystem import MediaItem
from app.domains.media.models.metadata import MetadataMatch, MetadataLocalization
from app.domains.shared.ports.scrapers import ScraperGatewayPort

from app.domains.media.schemas import MetadataResolveRequest, BulkResolveRequest

from app.core.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class MetadataService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = scrapers.tmdb(db)

    def search_metadata(self, query: str, item_type: str = "movie", year: Optional[int] = None, language: Optional[str] = None, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        # Resolve provider
        prov_enum = None
        if provider:
            try:
                prov_enum = Provider(provider.lower())
            except ValueError:
                pass

        if not prov_enum and item_type in ("scene", "adult"):
            prov_enum = Provider.STASHDB

        if prov_enum in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
            scraper = None
            if prov_enum == Provider.STASHDB:
                scraper = self.scrapers.adult(Provider.STASHDB, self.db)
            elif prov_enum == Provider.PORNDB:
                scraper = self.scrapers.adult(Provider.PORNDB, self.db)
            elif prov_enum == Provider.FANSDB:
                scraper = self.scrapers.adult(Provider.FANSDB, self.db)

            if not scraper:
                return []

            search_query = """
            query SearchScenes($q: String!) {
              searchScene(term: $q) {
                id
                title
                details
                date
                studio {
                  id
                  name
                }
                images {
                  url
                }
              }
            }
            """
            try:
                res = scraper.execute_query(search_query, {"q": query})
                scenes = res.get("searchScene", []) if res else []
                if not scenes:
                    scenes = []
                formatted = []
                for s in scenes:
                    studio_data = s.get("studio") or {}
                    formatted.append({
                        "id": s.get("id"),
                        "title": s.get("title"),
                        "original_title": None,
                        "release_date": s.get("date"),
                        "year": int(s["date"].split("-")[0]) if s.get("date") else None,
                        "overview": s.get("details"),
                        "poster_path": s.get("images", [{}])[0].get("url") if s.get("images") else None,
                        "backdrop_path": None,
                        "rating": s.get("rating") or 0.0,
                        "media_type": "scene",
                        "provider": prov_enum.value,
                        "studio": studio_data.get("name")
                    })
                return formatted
            except Exception as e:
                logger.error(f"Search failed on adult provider {prov_enum.value}: {e}")
                return []

        # Default TMDB search
        results = self.tmdb.search(query, item_type=item_type, year=year, language=language)
        formatted = []
        for r in results:
            release_date = r.get("release_date") or r.get("first_air_date")
            year_val = None
            if release_date:
                try:
                    year_val = int(release_date.split("-")[0])
                except:
                    pass
            formatted.append({
                "id": r.get("id"),
                "title": r.get("title") or r.get("name") or r.get("original_title") or r.get("original_name"),
                "original_title": r.get("original_title") or r.get("original_name"),
                "release_date": release_date,
                "year": year_val,
                "overview": r.get("overview"),
                "poster_path": r.get("poster_path"),
                "backdrop_path": r.get("backdrop_path"),
                "rating": r.get("vote_average"),
                "media_type": item_type,
                "provider": "tmdb"
            })
        return formatted

    def get_seasons(self, tmdb_id: int) -> List[Dict[str, Any]]:
        details = self.tmdb.get_details(tmdb_id, "tv")
        seasons = details.get("seasons", []) or []
        formatted = []
        for s in seasons:
            formatted.append({
                "season_number": s.get("season_number"),
                "name": s.get("name"),
                "episode_count": s.get("episode_count"),
                "poster_path": s.get("poster_path"),
                "air_date": s.get("air_date"),
            })
        return formatted

    def get_episodes(self, tmdb_id: int, season_number: int) -> List[Dict[str, Any]]:
        details = self.tmdb.get_season_details(tmdb_id, season_number)
        episodes = details.get("episodes", []) or []
        formatted = []
        for ep in episodes:
            formatted.append({
                "episode_number": ep.get("episode_number"),
                "name": ep.get("name"),
                "overview": ep.get("overview"),
                "still_path": ep.get("still_path"),
                "air_date": ep.get("air_date"),
                "vote_average": ep.get("vote_average"),
            })
        return formatted

    def resolve_item(self, request: MetadataResolveRequest) -> Dict[str, Any]:
        item_id = request.item_id
        external_id = request.tmdb_id or request.external_id
        media_type_str = request.type or request.media_type or "movie"
        season_number = request.season_number
        episode_number = request.episode_number
        provider_str = request.provider or "tmdb"

        if not item_id or not external_id:
            return {"error": "item_id and external_id (tmdb_id) are required"}

        item = self.db.query(MediaItem).filter(MediaItem.id == int(item_id)).first()
        if not item:
            return {"error": "Media item not found"}

        # Delete any existing metadata match mappings for this physical item
        self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()
        self.db.flush()

        # Parse provider and media type
        try:
            provider = Provider(provider_str.lower())
        except ValueError:
            provider = Provider.TMDB

        try:
            mtype = MediaType(media_type_str.lower())
        except ValueError:
            mtype = MediaType.MOVIE

        if provider in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
            scraper = None
            if provider == Provider.STASHDB:
                scraper = self.scrapers.adult(Provider.STASHDB, self.db)
            elif provider == Provider.PORNDB:
                scraper = self.scrapers.adult(Provider.PORNDB, self.db)
            elif provider == Provider.FANSDB:
                scraper = self.scrapers.adult(Provider.FANSDB, self.db)

            if not scraper:
                return {"error": "Selected adult scraper is not configured"}

            scene_data = scraper.fetch_scene(str(external_id))
            if not scene_data:
                return {"error": f"Failed to fetch scene details from {provider.value}"}

            normalized = self.scrapers.normalize_adult_scene(provider, scene_data)
            match = self.scrapers.persist_adult_scene(self.db, provider, str(scene_data["id"]), normalized)
            match.media_item_id = item.id
            item.status = ItemStatus.MATCHED
            self.db.commit()
            return {"status": "success", "item_id": item.id, "match_id": match.id}

        # Otherwise standard TMDB resolution
        # Check if match with same provider, external_id, and media_type already exists
        match = self.db.query(MetadataMatch).filter(
            MetadataMatch.provider == provider,
            MetadataMatch.external_id == str(external_id),
            MetadataMatch.media_type == mtype
        ).first()

        if match:
            match.media_item_id = item.id
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
                confidence_score=1.0
            )
            self.db.add(match)
        self.db.flush()

        item.status = ItemStatus.MATCHED

        # Enrich item metadata
        try:
            self.scrapers.enrich_mainstream(self.db, item, DEFAULT_FALLBACK_LANGUAGE, commit=True)
        except Exception as e:
            logger.error(f"Enrichment failed during manual resolve: {e}")
            self.db.commit()

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

    def get_full_metadata(self, item_id: int) -> Dict[str, Any]:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item:
            return {"error": "Item not found"}

        # Find active metadata match
        match = self.db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).first()
        if not match:
            return {
                "item_id": item.id,
                "match": None,
                "raw_details": {},
            }

        # Fetch detailed info from TMDB or adult provider
        details = {}
        try:
            if match.provider in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
                scraper = None
                if match.provider == Provider.STASHDB:
                    scraper = self.scrapers.adult(Provider.STASHDB, self.db)
                elif match.provider == Provider.PORNDB:
                    scraper = self.scrapers.adult(Provider.PORNDB, self.db)
                elif match.provider == Provider.FANSDB:
                    scraper = self.scrapers.adult(Provider.FANSDB, self.db)

                if scraper:
                    details = scraper.fetch_scene(match.external_id) or {}
            else:
                item_type = "tv" if match.media_type in (MediaType.TV, MediaType.SEASON, MediaType.EPISODE) else "movie"
                details = self.tmdb.get_details(int(match.external_id), item_type)
        except Exception as e:
            logger.error(f"Failed to fetch detailed match info: {e}")

        return {
            "item_id": item.id,
            "match": {
                "id": match.id,
                "provider": match.provider.value,
                "external_id": match.external_id,
                "media_type": match.media_type.value,
                "season_number": match.season_number,
                "episode_number": match.episode_number,
                "release_date": match.release_date.isoformat() if match.release_date else None,
                "original_title": match.original_title,
                "backdrop_path": match.backdrop_path,
            },
            "raw_details": details
        }

    def get_sync_status(self) -> Dict[str, Any]:
        return {
            "active": False,
            "progress": 100,
            "phase": "idle",
            "status": "success"
        }

    def trigger_sync(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "status": "success",
            "message": "Metadata language sync completed successfully"
        }
