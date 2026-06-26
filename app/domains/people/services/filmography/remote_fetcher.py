import logging
import math
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType
from app.domains.people.models import Person, MediaPersonLink
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_service_port import ImageServicePort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService

logger = logging.getLogger(__name__)

class RemoteCreditsFetcher:
    def __init__(self, db: Session, library_port: LibraryPort, image_service: ImageServicePort):
        self.db = db
        self.library_port = library_port
        self.image_service = image_service

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

    def fetch_remote_credits(
        self,
        person_id: int,
        source: str,
        media_type: str, # "scene" or "movie"
        page: int,
        page_size: int
    ) -> Optional[dict]:
        from app.infrastructure.scrapers.support.gateway import scraper_gateway
        
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return None
            
        ext_ids = person.external_ids or {}
        ext_id = ext_ids.get(source.lower()) or ext_ids.get(f"{source.lower()}_id")
        if not ext_id and source.lower() == "porndb":
            ext_id = ext_ids.get("theporndb") or ext_ids.get("theporndb_id")
            
        if not ext_id:
            try:
                prov_enum = Provider(source.lower())
                link = next((l for l in person.external_links if l.provider == prov_enum), None)
                if link:
                    ext_id = link.external_id
            except ValueError:
                pass
                
        if not ext_id:
            return None
            
        mapped_items = []
        total_items = 0
        
        remote_per_page = 5000
        
        if source.lower() in ("stashdb", "fansdb"):
            if media_type != "scene":
                return {"items": [], "page": page, "page_size": page_size, "total_items": 0, "total_pages": 1}
                
            try:
                prov_enum = Provider(source.lower())
                scraper = scraper_gateway.adult(prov_enum, db)
                query = """
                query QueryScenes($input: SceneQueryInput!) {
                  queryScenes(input: $input) {
                    count
                    scenes {
                      id
                      title
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
                }
                """
                variables = {
                    "input": {
                        "performers": {
                            "value": [ext_id],
                            "modifier": "INCLUDES"
                        },
                        "page": 1,
                        "per_page": remote_per_page,
                        "direction": "DESC",
                        "sort": "DATE"
                    }
                }
                res_data = scraper.execute_query(query, variables)
                if res_data and "queryScenes" in res_data:
                    qs = res_data["queryScenes"]
                    total_items = qs.get("count") or 0
                    raw_scenes = qs.get("scenes") or []
                    for s in raw_scenes:
                        sid = s.get("id")
                        title = s.get("title") or "Unknown"
                        date_str = s.get("date")
                        year = None
                        if date_str:
                            try:
                                year = int(date_str.split("-")[0])
                            except:
                                pass
                        studio_name = s.get("studio", {}).get("name") if s.get("studio") else None
                        poster_url = s["images"][0].get("url") if s.get("images") else None
                        
                        mapped_items.append({
                            "id": sid,
                            "title": title,
                            "type": "scene",
                            "media_type": "scene",
                            "year": year,
                            "studio": studio_name,
                            "poster_path": poster_url,
                            "in_library": False,
                            "stash_id": sid,
                            "source": source.lower(),
                        })
            except Exception as e:
                logger.error(f"Error querying StashDB/FansDB scene credits: {e}")
                
        elif source.lower() == "porndb":
            try:
                scraper = scraper_gateway.adult(Provider.PORNDB, db)
                api_token = scraper.get_setting("porndb_api_key") or scraper.get_setting("porndb_api_token")
                if api_token:
                    import requests
                    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
                    
                    if media_type == "movie":
                        data_list = []
                        current_page = 1
                        while len(data_list) < 5000:
                            url = f"https://api.theporndb.net/performers/{ext_id}/movies?page={current_page}&per_page=100"
                            resp = requests.get(url, headers=headers, timeout=10)
                            if resp.status_code != 200:
                                break
                            page_data = resp.json().get("data") or []
                            if not page_data:
                                break
                            data_list.extend(page_data)
                            if len(page_data) < 100:
                                break
                            current_page += 1

                        total_items = len(data_list)
                        for x in data_list:
                            xid = x.get("id")
                            title = x.get("title") or "Unknown"
                            date_str = x.get("date")
                            year = None
                            if date_str:
                                try:
                                    year = int(date_str.split("-")[0])
                                except:
                                    pass
                            studio_name = x.get("site", {}).get("name") if x.get("site") else None
                            poster_url = x.get("poster")
                            rating = x.get("rating")
                            
                            mapped_items.append({
                                "id": xid,
                                "title": title,
                                "type": "movie",
                                "media_type": "movie",
                                "year": year,
                                "studio": studio_name,
                                "poster_path": poster_url,
                                "rating": 0.0,
                                "rating_porndb": rating,
                                "in_library": False,
                                "stash_id": xid,
                                "source": "porndb",
                            })
                            
                    elif media_type == "scene":
                        data_list = []
                        current_page = 1
                        while len(data_list) < 5000:
                            url = f"https://api.theporndb.net/performers/{ext_id}/scenes?page={current_page}&per_page=100"
                            resp = requests.get(url, headers=headers, timeout=10)
                            if resp.status_code != 200:
                                break
                            page_data = resp.json().get("data") or []
                            if not page_data:
                                break
                            data_list.extend(page_data)
                            if len(page_data) < 100:
                                break
                            current_page += 1

                        total_items = len(data_list)
                        for x in data_list:
                            xid = x.get("id")
                            title = x.get("title") or "Unknown"
                            date_str = x.get("date")
                            year = None
                            if date_str:
                                try:
                                    year = int(date_str.split("-")[0])
                                except:
                                    pass
                            studio_name = x.get("site", {}).get("name") if x.get("site") else None
                            poster_url = x.get("poster")
                            rating = x.get("rating")
                            
                            mapped_items.append({
                                "id": xid,
                                "title": title,
                                "type": "scene",
                                "media_type": "scene",
                                "year": year,
                                "studio": studio_name,
                                "poster_path": poster_url,
                                "rating": 0.0,
                                "rating_porndb": rating,
                                "in_library": False,
                                "stash_id": xid,
                                "source": "porndb",
                            })
            except Exception as e:
                logger.error(f"Error querying PornDB REST API for performer {person_id}: {e}")
                
        local_items = []
        try:
            prov_enum = Provider(source.lower())
            active_match_ids = self.library_port.get_active_match_ids(media_type=media_type)
            from app.shared_kernel.language import LanguageService
            
            links = db.query(MediaPersonLink).filter(
                MediaPersonLink.person_id == person_id,
                MediaPersonLink.match_id.in_(active_match_ids)
            ).all()
            
            ui_lang = DEFAULT_FALLBACK_LANGUAGE
            for link in links:
                match = link.match
                item = match.media_item
                match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
                title = match_loc.title if match_loc else item.filename
                
                local_items.append({
                    "id": item.id,
                    "title": title,
                    "type": media_type,
                    "media_type": media_type,
                    "year": match.release_date.year if match.release_date else None,
                    "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                    "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops", size="original"),
                    "rating": match.rating_tmdb or 0.0,
                    "rating_porndb": match.rating_porndb,
                    "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                    "character": link.character_name,
                    "in_library": True,
                    "library_item_id": item.id,
                    "stash_id": match.external_id if (match.provider and match.provider.value == source.lower()) else None,
                    "source": source.lower(),
                })
        except Exception as e:
            logger.error(f"Error querying local items in _fetch_remote_credits: {e}")

        local_by_ext_id = {str(li["stash_id"]).lower().strip(): li for li in local_items if li.get("stash_id")}
        combined_items = []
        
        for item in mapped_items:
            ext_id_key = str(item["id"]).lower().strip()
            if ext_id_key in local_by_ext_id:
                local_item = local_by_ext_id[ext_id_key]
                item.update({
                    "in_library": True,
                    "library_item_id": local_item["id"],
                })
                local_item["_merged"] = True
            combined_items.append(item)
            
        for li in local_items:
            if not li.get("_merged"):
                combined_items.append(li)
                
        combined_items.sort(
            key=lambda x: (
                0 if x.get("in_library") else 1,
                -(x.get("year") or 0),
                x.get("title") or ""
            )
        )
        
        total_items = max(total_items, len(combined_items))
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = combined_items[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }
