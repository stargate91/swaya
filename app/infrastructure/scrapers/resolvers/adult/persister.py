from typing import Optional
from sqlalchemy.orm import Session
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.enums import Provider, MediaType, ItemStatus

def persist_scene_match(
    db: Session,
    *,
    item: MediaItem,
    provider: Provider,
    scraper,
    scene_data: dict,
    confidence: float,
    is_active: bool = True,
    clear_existing: bool = True,
    status: ItemStatus = ItemStatus.MATCHED,
    media_item_id: Optional[int] = None,
):
    if clear_existing:
        db.query(MetadataMatch).filter(MetadataMatch.media_item_id == item.id).delete()

    from app.infrastructure.scrapers.support.normalizer import ScraperNormalizer
    from app.infrastructure.scrapers.support.persistence import ScraperPersister

    if provider == Provider.PORNDB:
        scene_data = scraper.enrich_scene_ratings(scene_data)
    normalized = ScraperNormalizer.normalize_adult_scene(provider.value, scene_data)
    persister = ScraperPersister(db)
    match = persister.persist_normalized_scene(provider, str(scene_data['id']), normalized, media_type=MediaType.SCENE, media_item_id=item.id)
    match.is_active = is_active
    match.confidence_score = confidence
    item.status = status
    return match
