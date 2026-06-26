import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_service_port import ImageServicePort
from app.domains.people.services.filmography_service import FilmographyService
from app.domains.people.services.detail_reader import PerformerDetailReader
from app.domains.people.services.asset_manager import PerformerAssetManager
from app.application.people.schemas import (
    PeopleSearchResponse,
    PersonDetailResponse,
    PersonFilmographyResponse,
)

logger = logging.getLogger(__name__)

class PeopleDetailService:
    def __init__(
        self,
        db: Session,
        scrapers: ScraperGatewayPort,
        library_port: Optional[LibraryPort] = None,
        image_service: Optional[ImageServicePort] = None
    ):
        self.db = db
        self.scrapers = scrapers
        
        if library_port is None:
            from app.infrastructure.media.db_media_resolver import DbMediaResolver
            library_port = DbMediaResolver(db)
        self.library_port = library_port
        
        if image_service is None:
            from app.domains.media_assets.services.images import image_processing_service
            image_service = image_processing_service
        self.image_service = image_service
        
        self.filmography_service = FilmographyService(db, library_port=library_port, image_service=image_service)
        
        self.reader = PerformerDetailReader(
            db=db,
            scrapers=scrapers,
            library_port=library_port,
            image_service=image_service,
            filmography_service=self.filmography_service
        )
        
        self.asset_manager = PerformerAssetManager(
            db=db,
            library_port=library_port,
            image_service=image_service
        )

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

    def get_people(
        self,
        search: str = None,
        role: str = None,
        sort_by: str = "library_count",
        include_inactive: bool = False,
        adult_only: bool = False,
        gender: str = "all",
        offset: int = 0,
        limit: int = 20,
    ) -> PeopleSearchResponse:
        return self.reader.get_people(
            search=search,
            role=role,
            sort_by=sort_by,
            include_inactive=include_inactive,
            adult_only=adult_only,
            gender=gender,
            offset=offset,
            limit=limit
        )

    def get_person_detail(self, person_id: int) -> PersonDetailResponse:
        return self.reader.get_person_detail(person_id)

    def get_person_movies(self, person_id: int, page: int = 1, page_size: int = 12, source: Optional[str] = None) -> PersonFilmographyResponse:
        return self.reader.get_person_movies(person_id, page=page, page_size=page_size, source=source)

    def get_person_tv(self, person_id: int, page: int = 1, page_size: int = 12) -> PersonFilmographyResponse:
        return self.reader.get_person_tv(person_id, page=page, page_size=page_size)

    def get_person_scenes(self, person_id: int, page: int = 1, page_size: int = 12, source: Optional[str] = None) -> PersonFilmographyResponse:
        return self.reader.get_person_scenes(person_id, page=page, page_size=page_size, source=source)

    def get_person_credit_backdrops(self, person_id: int, tmdb_id: int, media_type: str) -> Dict[str, Any]:
        return self.reader.get_person_credit_backdrops(person_id, tmdb_id=tmdb_id, media_type=media_type)

    def update_person_backdrop(self, person_id: int, backdrop_path: str) -> Dict[str, Any]:
        return self.asset_manager.update_person_backdrop(person_id, backdrop_path)

    def handle_person_backdrop_upload(self, person_id: int, filename: str, file_stream) -> Dict[str, Any]:
        return self.asset_manager.handle_person_backdrop_upload(person_id, filename, file_stream)

    def update_person_profile(self, person_id: int, profile_path: str) -> Dict[str, Any]:
        return self.asset_manager.update_person_profile(person_id, profile_path)

    def handle_person_profile_upload(self, person_id: int, filename: str, file_stream) -> Dict[str, Any]:
        return self.asset_manager.handle_person_profile_upload(person_id, filename, file_stream)

    def search_people_tmdb(self, query: str, language: Optional[str] = None, adult_only: bool = False, page: int = 1, source: str = "all") -> List[Dict[str, Any]]:
        return self.reader.search_people_tmdb(query, language=language, adult_only=adult_only, page=page, source=source)

    def add_person_tmdb(
        self,
        db_id_or_external: str,
        name: Optional[str] = None,
        profile_path: Optional[str] = None,
        gender: Optional[int] = None,
        is_adult: Optional[bool] = None
    ) -> Dict[str, Any]:
        return self.reader.add_person_tmdb(
            db_id_or_external=db_id_or_external,
            name=name,
            profile_path=profile_path,
            gender=gender,
            is_adult=is_adult
        )
