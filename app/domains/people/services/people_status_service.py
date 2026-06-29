import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Any, List, Dict, Optional
from sqlalchemy.orm import Session

from app.domains.people.models import Person, ExternalSourceLink
from app.domains.users.models import UserOverride
from app.shared_kernel.enums import Provider
from app.shared_kernel.exceptions import NotFoundException
from app.shared_kernel.user_context import get_current_user_id

logger = logging.getLogger(__name__)


class PersonEnrichmentQueue:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(PersonEnrichmentQueue, cls).__new__(cls)
                cls._instance._init_queue()
            return cls._instance

    def _init_queue(self):
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True, name="PersonEnrichmentWorker")
        self.worker_thread.start()

    def enqueue(self, person_id: int):
        self.queue.put(person_id)

    def _worker(self):
        while True:
            try:
                person_id = self.queue.get()
                if person_id is None:
                    break
                self._enrich_person(person_id)
            except Exception as e:
                logger.error(f"Error in PersonEnrichmentQueue worker: {e}", exc_info=True)
            finally:
                self.queue.task_done()

    def _enrich_person(self, person_id: int):
        from app.shared_kernel.database import SessionLocal
        from app.infrastructure.scrapers.support.gateway import scraper_gateway
        from app.domains.people.services.people_enricher import PeopleEnricher

        db = SessionLocal()
        try:
            person = db.query(Person).filter(Person.id == person_id).first()
            if not person:
                return

            logger.info(f"Background enriching activated person: {person.name} (ID: {person_id})")
            enricher = PeopleEnricher(db, scrapers=scraper_gateway)
            
            ext_ids = person.external_ids or {}
            links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
            link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
            
            for prov_name, ext_id in ext_ids.items():
                try:
                     prov = Provider(prov_name.lower())
                     if not any(ld["provider"] == prov for ld in link_data):
                         link_data.append({"provider": prov, "external_id": str(ext_id)})
                except Exception:
                     pass

            fetched_data = enricher.fetch_external_details(
                person.name,
                ext_ids,
                link_data,
                is_adult=person.is_adult
            )
            if fetched_data:
                enricher.apply_enriched_data(person, fetched_data)
                db.commit()
                logger.info(f"Successfully enriched activated person: {person.name}")
        except Exception as e:
            logger.error(f"Failed to enrich person {person_id} in background queue: {e}", exc_info=True)
        finally:
            db.close()


_enrichment_queue = PersonEnrichmentQueue()


def enqueue_person_enrichment(person_id: int):
    _enrichment_queue.enqueue(person_id)


class PeopleStatusService:
    def __init__(
        self,
        db: Session,
        scrapers: Optional[Any] = None,
        library_port: Optional[Any] = None,
        image_service: Optional[Any] = None
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

    def resolve_person(self, person_id: Any) -> Optional[Person]:
        """Resolves a person by numeric ID or by provider:external_id format."""
        person_id_str = str(person_id)
        if ":" in person_id_str:
            parts = person_id_str.split(":", 1)
            source_name = parts[0]
            uuid_str = parts[1]
            
            scraper_name = "porndb" if source_name == "theporndb" else source_name
            try:
                provider_enum = Provider(scraper_name)
                link = self.db.query(ExternalSourceLink).filter(
                    ExternalSourceLink.provider == provider_enum,
                    ExternalSourceLink.external_id == uuid_str
                ).first()
                if link:
                    return link.person
            except Exception:
                pass
            return None
        else:
            try:
                p_id = int(person_id_str)
                return self.db.query(Person).filter(Person.id == p_id).first()
            except (ValueError, TypeError):
                return None

    def list_people_by_type(self, is_adult: bool, limit: int = 50) -> List[Person]:
        """Retrieve mainstream (is_adult=False) or adult (is_adult=True) people."""
        return self.db.query(Person).filter(Person.is_adult == is_adult).limit(limit).all()

    def update_person_status(self, person_id: str, payload_data: Dict[str, Any], fields_set: set) -> Dict[str, Any]:
        """Updates person active status and/or user-specific overrides (favorite, rating, comment)."""
        person = self.resolve_person(person_id)
        if not person:
            # Try to import/create the person dynamically if we have scrapers
            if self.scrapers:
                from app.domains.people.services.people_search_service import PeopleSearchService
                search_service = PeopleSearchService(
                    self.db,
                    self.scrapers,
                    self.library_port,
                    self.image_service
                )
                try:
                    res = search_service.add_person_tmdb(person_id, is_active=True)
                    if res and res.get("status") == "success":
                        person = self.resolve_person(res["id"])
                except Exception as e:
                    logger.error(f"Failed to dynamically import virtual person {person_id}: {e}")

            if not person:
                raise NotFoundException("Person not found")

        user_id = get_current_user_id() or 1

        newly_activated = False

        # 1. Update Person level fields
        if "is_active" in fields_set and payload_data.get("is_active") is not None:
            if payload_data.get("is_active") and not person.is_active:
                newly_activated = True
            person.is_active = payload_data.get("is_active")

        # Auto-activate on user interaction
        has_user_interaction = (
            ("user_rating" in fields_set and payload_data.get("user_rating") is not None)
            or ("is_favorite" in fields_set and payload_data.get("is_favorite"))
            or ("user_comment" in fields_set and payload_data.get("user_comment") is not None)
        )
        if has_user_interaction:
            if not person.is_active:
                newly_activated = True
            person.is_active = True

        # 2. Update UserOverride fields
        has_override_update = (
            "user_rating" in fields_set
            or "is_favorite" in fields_set
            or "user_comment" in fields_set
        )
        if has_override_update:
            override = self.db.query(UserOverride).filter(
                UserOverride.user_id == user_id,
                UserOverride.person_id == person.id
            ).first()

            if not override:
                override = UserOverride(
                    user_id=user_id,
                    person_id=person.id
                )
                self.db.add(override)

            if "user_rating" in fields_set:
                rating_val = payload_data.get("user_rating")
                override.user_rating = float(rating_val) if rating_val is not None else None
                override.user_rating_at = datetime.now(timezone.utc) if rating_val is not None else None

            if "is_favorite" in fields_set:
                fav_val = payload_data.get("is_favorite")
                override.is_favorite = fav_val if fav_val is not None else False
                override.is_favorite_at = datetime.now(timezone.utc) if fav_val else None

            if "user_comment" in fields_set:
                comment_val = payload_data.get("user_comment")
                override.user_comment = comment_val
                override.user_comment_at = datetime.now(timezone.utc) if comment_val else None

        self.db.commit()

        if newly_activated:
            enqueue_person_enrichment(person.id)

        override = self.db.query(UserOverride).filter(
            UserOverride.user_id == user_id,
            UserOverride.person_id == person.id
        ).first()

        return {
            "status": "ok",
            "is_active": person.is_active,
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
        }
