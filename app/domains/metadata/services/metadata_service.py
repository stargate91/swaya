import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.ports.scrapers import ScraperGatewayPort

from app.application.metadata.schemas import MetadataResolveRequest, BulkResolveRequest
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

# Import sub-services
from app.domains.metadata.services.metadata_resolver import MetadataResolver
from app.domains.metadata.services.metadata_sync_service import MetadataSyncService

logger = logging.getLogger(__name__)

PORNDB_API_BASE = "https://api.theporndb.net"
SCRAPER_REQUEST_TIMEOUT = 15

class MetadataService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        self.db = db
        self.scrapers = scrapers
        self.tmdb = scrapers.tmdb(db)
        
        # Instantiate sub-services
        self.resolver = MetadataResolver(db, scrapers, self.tmdb)
        self.sync_service = MetadataSyncService()

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
        return self.resolver.resolve_item(request)

    def bulk_resolve(self, request: BulkResolveRequest) -> Dict[str, Any]:
        return self.resolver.bulk_resolve(request)

    def get_full_metadata(self, item_id: str, media_type: str = None, language: str = None) -> Dict[str, Any]:
        is_tmdb_direct = False
        tmdb_id_int = None
        
        if isinstance(item_id, str) and item_id.startswith("tmdb_"):
            try:
                tmdb_id_int = int(item_id.split("_")[1])
                is_tmdb_direct = True
            except (ValueError, IndexError):
                pass
        
        if not is_tmdb_direct and (media_type == "tv" or (isinstance(item_id, str) and "tv" in item_id)):
            try:
                clean_id = str(item_id)
                if clean_id.startswith("tmdb_"):
                    clean_id = clean_id.split("_")[1]
                tmdb_id_int = int(clean_id)
                is_tmdb_direct = True
            except (ValueError, IndexError):
                pass

        if is_tmdb_direct and tmdb_id_int is not None:
            details = {}
            try:
                resolved_media_type = media_type or "tv"
                item_type = "tv" if resolved_media_type == "tv" else "movie"
                details = self.tmdb.get_details(tmdb_id_int, item_type, language=language)
            except Exception as e:
                logger.error(f"Failed to fetch direct TMDB full metadata: {e}")
            return {
                "item_id": item_id,
                "match": None,
                "raw_details": details,
            }

        try:
            item_id_int = int(item_id)
        except ValueError:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("Invalid item ID format")

        item = self.db.query(MediaItem).filter(MediaItem.id == item_id_int).first()
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
                details = self.tmdb.get_details(int(match.external_id), item_type, language=language)
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
        return self.sync_service.get_sync_status()

    def trigger_sync(self, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.sync_service.trigger_sync(payload)
