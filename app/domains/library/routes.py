from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel

from app.shared_kernel.database import get_db
from app.shared_kernel.enums import ScanMode
from app.domains.library.models import MediaItem, Library
from app.domains.metadata.models import MetadataMatch
from app.domains.metadata.schemas import MetadataMatchRead
from app.domains.library.schemas import (
    MediaItemRead,
    LibraryRead,
    LibraryStatsResponse,
    ContinueWatchingItem,
    LibraryTabResponse,
    GroupedLibraryResponse,
    TagGroupItem,
    FilterOptionsResponse,
    MovieCollectionsResponse,
    MovieDetailResponse,
    TvShowDetailResponse,
    TvSeasonDetailResponse,
    CollectionDetailResponse,
    SceneDetailResponse,
)
from app.domains.people.schemas import PeopleGroupItem
from app.domains.users.schemas import (
    ItemOverridesUpdate,
    ItemStatusUpdate,
    ImageOverrideUpdate,
    BulkOverridesUpdate,
    BulkTagsUpdate,
    BulkWatchedUpdate,
)

# Mainstream (SFW) Media Router
mainstream_router = APIRouter(prefix="/api/v1/mainstream/media", tags=["Mainstream Media"])

# Adult (NSFW) Media Router
adult_router = APIRouter(prefix="/api/v1/adult/media", tags=["Adult Media"])

# Common Media Router
router = APIRouter(prefix="/api/v1/media", tags=["General Media"])

# Legacy Library Endpoints for Swaya Frontend
library_router = APIRouter(prefix="/api/v1", tags=["Library"])


# --- Mainstream Router Endpoints ---
@mainstream_router.get("", response_model=List[MetadataMatchRead])
def list_mainstream_metadata(db: Session = Depends(get_db), limit: int = 50):
    """List mainstream metadata matches (SFW)."""
    return db.query(MetadataMatch).filter(MetadataMatch.is_adult == False).limit(limit).all()


# --- Adult Router Endpoints ---
@adult_router.get("", response_model=List[MetadataMatchRead])
def list_adult_metadata(db: Session = Depends(get_db), limit: int = 50):
    """List adult metadata matches (NSFW)."""
    return db.query(MetadataMatch).filter(MetadataMatch.is_adult == True).limit(limit).all()


# General Media Router Endpoints ---
@router.get("/items", response_model=List[MediaItemRead])
def list_media_items(db: Session = Depends(get_db), limit: int = 50):
    """Retrieve indexed physical media files."""
    return db.query(MediaItem).limit(limit).all()


@router.get("/libraries", response_model=List[LibraryRead])
def list_libraries(db: Session = Depends(get_db)):
    """Retrieve registered media source roots."""
    return db.query(Library).all()


from app.domains.library.services.library_stats_service import LibraryStatsService
from app.domains.library.services.library_listing_service import LibraryListingService
from app.domains.library.services.library_collection_service import LibraryCollectionService
from app.domains.library.services.library_filter_service import LibraryFilterService

from typing import Union

@library_router.get("/library/stats", response_model=LibraryStatsResponse)
def get_stats(db: Session = Depends(get_db), include_adult: bool = False):
    return LibraryStatsService(db).get_stats(include_adult=include_adult)


@library_router.get("/library/continue-watching", response_model=List[ContinueWatchingItem])
def get_continue_watching(db: Session = Depends(get_db), limit: int = 12, include_adult: bool = False):
    return LibraryListingService(db).get_continue_watching(limit=limit, include_adult=include_adult)


@library_router.get("/library", response_model=Union[LibraryTabResponse, GroupedLibraryResponse])
def get_library_items(
    db: Session = Depends(get_db),
    tab: Optional[str] = None,
    page: int = 1,
    page_size: int = 40,
    sort_by: str = "title_asc",
    search: str = "",
    selected_tags: Optional[str] = None,
    selected_genre: Optional[str] = None,
    selected_decade: Optional[str] = None,
    selected_year: Optional[int] = None,
    filter_favorite: str = "all",
    filter_watched: str = "all",
    filter_ownership: str = "owned",
    filter_status: str = "active",
    filter_gender: str = "all",
    people_role: str = "all",
    include_adult: bool = False,
):
    service = LibraryListingService(db)
    if tab:
        tags_list = None
        if selected_tags:
            tags_list = [t.strip() for t in selected_tags.split(",") if t.strip()]
        return service.get_library_tab_page(
            tab=tab,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            search=search,
            selected_tags=tags_list,
            selected_genre=selected_genre,
            selected_decade=selected_decade,
            selected_year=selected_year,
            filter_favorite=filter_favorite,
            filter_watched=filter_watched,
            filter_ownership=filter_ownership,
            filter_status=filter_status,
            filter_gender=filter_gender,
            people_role=people_role,
            include_adult=include_adult,
        )

    return service.get_grouped_library(include_adult=include_adult)


@library_router.get("/library/tags", response_model=List[TagGroupItem])
def get_library_tags(db: Session = Depends(get_db), is_adult: bool = False):
    return LibraryFilterService(db).get_tag_groups(is_adult)


@library_router.get("/library/filters", response_model=FilterOptionsResponse)
def get_library_filters(
    db: Session = Depends(get_db),
    tab: str = "movies",
    filter_ownership: str = "owned",
    filter_status: str = "active"
):
    return LibraryFilterService(db).get_library_filter_options(tab, filter_ownership, filter_status)


@library_router.get("/library/collections", response_model=MovieCollectionsResponse)
def get_movie_collections(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: Optional[int] = 40,
    search: str = "",
    tab: str = "movies",
    include_adult: bool = False,
):
    return LibraryCollectionService(db).get_movie_collections(
        page=page,
        page_size=page_size,
        search=search,
        tab=tab,
        include_adult=include_adult,
    )



from app.domains.people.services.people_library_service import PeopleLibraryService

@library_router.get("/library/people/{role}", response_model=List[PeopleGroupItem])
def get_library_people(
    role: str,
    db: Session = Depends(get_db),
    filter_status: str = "active",
    tab: str = "people",
    include_adult: bool = False,
):
    return PeopleLibraryService(db).get_people_group(
        role=role,
        filter_status=filter_status,
        tab=tab,
        include_adult=include_adult,
    )


from app.domains.library.services.detail.movie_detail_service import MovieDetailService
from app.domains.library.services.detail.tv_detail_service import TvDetailService
from app.domains.library.services.detail.scene_detail_service import SceneDetailService
from app.domains.library.services.detail.collection_detail_service import CollectionDetailService
from app.shared_kernel.ports.scrapers import ScraperGatewayPort

def get_scraper_gateway() -> ScraperGatewayPort:
    from app.infrastructure.scrapers.support.gateway import scraper_gateway
    return scraper_gateway

@library_router.get("/library/item/{item_id}", response_model=Union[MovieDetailResponse, SceneDetailResponse])
def get_library_item_detail(
    item_id: str,
    full_people: bool = False,
    db: Session = Depends(get_db),
    scrapers: ScraperGatewayPort = Depends(get_scraper_gateway)
):
    if item_id.startswith("stash_"):
        return SceneDetailService(db, scrapers).get_scene_detail(item_id)
    return MovieDetailService(db, scrapers).get_library_item_detail(item_id, full_people=full_people)


@library_router.get("/library/tv/{tv_tmdb_id}", response_model=TvShowDetailResponse)
def get_library_tv_detail(
    tv_tmdb_id: str,
    seasons_limit: int = 5,
    initial_episodes_limit: int = 4,
    db: Session = Depends(get_db),
    scrapers: ScraperGatewayPort = Depends(get_scraper_gateway)
):
    return TvDetailService(db, scrapers).get_library_tv_detail(
        tv_tmdb_id, seasons_limit=seasons_limit, initial_episodes_limit=initial_episodes_limit
    )


@library_router.get("/library/tv/{tv_tmdb_id}/season/{season_number}", response_model=TvSeasonDetailResponse)
def get_library_tv_season_detail(
    tv_tmdb_id: str,
    season_number: int,
    db: Session = Depends(get_db),
    scrapers: ScraperGatewayPort = Depends(get_scraper_gateway)
):
    return TvDetailService(db, scrapers).get_library_tv_season_detail(tv_tmdb_id, season_number)


@library_router.get("/library/collection/{collection_tmdb_id}", response_model=CollectionDetailResponse)
def get_library_collection_detail(
    collection_tmdb_id: str,
    language: str | None = None,
    db: Session = Depends(get_db),
    scrapers: ScraperGatewayPort = Depends(get_scraper_gateway)
):
    return CollectionDetailService(db, scrapers).get_collection_detail(collection_tmdb_id, language=language)

