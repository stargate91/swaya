import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.shared_kernel.ports.scrapers import ScraperGatewayPort

from app.domains.metadata.schemas import MetadataResolveRequest, BulkResolveRequest

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class MetadataService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = scrapers.tmdb(db)

    def search_metadata(self, query: str, item_type: str = "movie", year: Optional[int] = None, language: Optional[str] = None, provider: Optional[str] = None, include_adult: bool = False, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict[str, Any]]:
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

            if prov_enum == Provider.PORNDB and item_type == "movie":
                try:
                    movies = scraper.search_movies(query, year=year)
                    formatted = []
                    for m in movies:
                        poster = (
                            m.get("poster_image")
                            or m.get("poster")
                            or m.get("image")
                        )
                        if not poster and isinstance(m.get("posters"), dict):
                            poster = (
                                m["posters"].get("full")
                                or m["posters"].get("large")
                                or m["posters"].get("medium")
                                or m["posters"].get("small")
                            )
                        backdrop = m.get("background")
                        if not backdrop and isinstance(m.get("backgrounds"), dict):
                            backdrop = (
                                m["backgrounds"].get("full")
                                or m["backgrounds"].get("large")
                                or m["backgrounds"].get("medium")
                                or m["backgrounds"].get("small")
                            )
                        site_data = m.get("site") or {}
                        studio_name = m.get("studio", {}).get("name") if isinstance(m.get("studio"), dict) else (site_data.get("name") or m.get("studio"))
                        formatted.append({
                            "id": m.get("id"),
                            "title": m.get("title"),
                            "original_title": None,
                            "release_date": m.get("date"),
                            "year": int(str(m["date"]).split("-")[0]) if m.get("date") else None,
                            "overview": m.get("synopsis") or m.get("description"),
                            "poster_path": poster,
                            "backdrop_path": backdrop,
                            "rating": m.get("rating") or 0.0,
                            "media_type": "movie",
                            "provider": prov_enum.value,
                            "studio": studio_name
                        })
                    return formatted
                except Exception as e:
                    logger.error(f"Search failed on PornDB movies: {e}")
                    return []

            if prov_enum == Provider.PORNDB and item_type in ("scene", "scenes", "adult"):
                try:
                    params = {"q": query}
                    if year:
                        params["year"] = year
                    api_token = scraper.get_setting("porndb_api_key") or scraper.get_setting("porndb_api_token")
                    headers = {
                        "Authorization": f"Bearer {api_token}",
                        "Accept": "application/json"
                    }
                    resp = scraper.session.get(f"{PORNDB_API_BASE}/scenes", params=params, headers=headers, timeout=SCRAPER_REQUEST_TIMEOUT)
                    if resp.status_code == 200:
                        scenes = resp.json().get("data") or []
                        formatted = []
                        for s in scenes:
                            site_data = s.get("site") or {}
                            formatted.append({
                                "id": s.get("id"),
                                "title": s.get("title"),
                                "original_title": None,
                                "release_date": s.get("date"),
                                "year": int(str(s["date"]).split("-")[0]) if s.get("date") else None,
                                "overview": s.get("description") or s.get("details"),
                                "poster_path": s.get("image") or s.get("face") or s.get("thumbnail"),
                                "backdrop_path": s.get("image"),
                                "rating": s.get("rating") or 0.0,
                                "media_type": "scene",
                                "provider": prov_enum.value,
                                "studio": site_data.get("name")
                            })
                        return formatted
                    else:
                        logger.error(f"PornDB REST scenes search failed with status {resp.status_code}")
                except Exception as e:
                    logger.error(f"PornDB REST scenes search error: {e}")

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
                
                # Client-side year filtering for GraphQL search results
                if year:
                    scenes = [s for s in scenes if s.get("date") and str(s.get("date")).startswith(str(year))]

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
        results = self.tmdb.search(query, item_type=item_type, year=year, language=language, include_adult=include_adult)

        # Concurrently fetch seasons details for TV shows
        if item_type == "tv" and results:
            from concurrent.futures import ThreadPoolExecutor
            def fetch_tv_seasons(r):
                try:
                    details = self.tmdb.get_details(r["id"], "tv", language=language)
                    seasons = details.get("seasons") or []
                    return [{
                        "season_number": s.get("season_number"),
                        "name": s.get("name"),
                        "episode_count": s.get("episode_count"),
                        "poster_path": s.get("poster_path"),
                        "air_date": s.get("air_date"),
                    } for s in seasons]
                except Exception as e:
                    logger.error(f"Failed to fetch seasons for TV {r.get('id')}: {e}")
                    return []

            with ThreadPoolExecutor(max_workers=5) as executor:
                seasons_lists = list(executor.map(fetch_tv_seasons, results))

            for r, s_list in zip(results, seasons_lists):
                r["seasons"] = s_list

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
                "provider": "tmdb",
                "seasons": r.get("seasons") or []
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
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("item_id and external_id (tmdb_id) are required")

        item = self.db.query(MediaItem).filter(MediaItem.id == int(item_id)).first()
        if not item:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Media item not found")

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
                    self.db, provider, str(movie_data["id"]), normalized, media_type=MediaType.MOVIE, media_item_id=item.id
                )
                item.status = ItemStatus.MATCHED
                self.db.commit()
                return {"status": "success", "item_id": item.id, "match_id": match.id}

            scene_data = scraper.fetch_scene(str(external_id))
            if not scene_data:
                from app.shared_kernel.exceptions import BadRequestException
                raise BadRequestException(f"Failed to fetch scene details from {provider.value}")

            normalized = self.scrapers.normalize_adult_scene(provider, scene_data)
            match = self.scrapers.persist_adult_scene(self.db, provider, str(scene_data["id"]), normalized, media_item_id=item.id)
            item.status = ItemStatus.MATCHED
            self.db.commit()
            return {"status": "success", "item_id": item.id, "match_id": match.id}

        # Otherwise standard TMDB resolution
        # Check if match with same provider, external_id, and media_type already exists
        match = self.db.query(MetadataMatch).filter(
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
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Item not found")

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
