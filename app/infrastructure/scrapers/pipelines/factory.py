from app.shared_kernel.enums import Provider, ScanMode

from app.infrastructure.scrapers.pipelines.porndb_movie import PornDbMovieResolverPipeline
from app.infrastructure.scrapers.pipelines.scenes import (
    FansDbSceneResolverPipeline,
    PornDbSceneResolverPipeline,
    SceneAutoResolverPipeline,
    StashDbSceneResolverPipeline,
)
from app.infrastructure.scrapers.pipelines.tmdb_omdb import TmdbOmdbResolverPipeline


def get_resolver_pipeline(
    mode: ScanMode,
    mainstream_resolver,
    adult_resolver,
    porndb_movie_resolver,
    include_adult: bool = False,
    provider: Optional[str] = None,
):
    # Normalized provider string
    p = str(provider or '').strip().lower()

    if mode == ScanMode.SCENES:
        if p == "stashdb":
            return StashDbSceneResolverPipeline(adult_resolver)
        elif p == "porndb":
            return PornDbSceneResolverPipeline(adult_resolver)
        elif p == "fansdb":
            return FansDbSceneResolverPipeline(adult_resolver)
        return SceneAutoResolverPipeline(adult_resolver)

    if mode == ScanMode.PORNDB_MOVIE or (mode == ScanMode.MOVIES_TV and include_adult and p == "porndb"):
        return PornDbMovieResolverPipeline(porndb_movie_resolver)

    return TmdbOmdbResolverPipeline(mainstream_resolver, include_adult)


def get_manual_resolver_pipeline(
    provider: Provider,
    media_type: str,
    mainstream_resolver,
    adult_resolver,
    porndb_movie_resolver,
    include_adult: bool = False,
):
    normalized_type = str(media_type or '').lower()
    if provider == Provider.TMDB:
        return TmdbOmdbResolverPipeline(mainstream_resolver, include_adult)
    if provider == Provider.PORNDB and normalized_type == 'movie':
        return PornDbMovieResolverPipeline(porndb_movie_resolver)
    if provider == Provider.STASHDB:
        return StashDbSceneResolverPipeline(adult_resolver)
    if provider == Provider.FANSDB:
        return FansDbSceneResolverPipeline(adult_resolver)
    if provider == Provider.PORNDB and normalized_type == 'scene':
        return PornDbSceneResolverPipeline(adult_resolver)
    return TmdbOmdbResolverPipeline(mainstream_resolver, include_adult)
