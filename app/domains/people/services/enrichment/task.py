import logging
import concurrent.futures
import time
from typing import List, Optional, Callable

from app.domains.people.models import Person, MediaPersonLink, ExternalSourceLink
from app.shared_kernel.constants import DEFAULT_MAX_WORKERS

logger = logging.getLogger(__name__)

def enrich_people_for_matches(
    enricher,
    task_id: int,
    match_ids: List[int],
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> int:
    """
    Enriches all people associated with the metadata matches.
    Fetches bio, details, and schedules profile downloads in parallel.
    Returns the number of enriched people.
    """
    links = enricher.db.query(MediaPersonLink).filter(MediaPersonLink.match_id.in_(match_ids)).all()
    person_ids = list(set(link.person_id for link in links))
    if not person_ids:
        return 0

    logger.info(f"Enriching {len(person_ids)} people linked to matches: {match_ids}")
    enriched_count = 0
    total = len(person_ids)

    executor = enricher._get_executor()
    max_workers = DEFAULT_MAX_WORKERS

    def enrich_worker(person_id: int) -> bool:
        if enricher._is_cancelled(task_id):
            return False

        while enricher._has_active_heavy_tasks():
            if enricher._is_cancelled(task_id):
                return False
            time.sleep(2)

        # 1. Quick read of external IDs and name (Release SQLite transaction immediately)
        local_db = enricher._get_temp_db()
        try:
            person = local_db.query(Person).filter(Person.id == person_id).first()
            if not person:
                return False
            person_name = person.name
            links = local_db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person_id).all()
            link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
            external_ids = person.external_ids or {}
            is_adult = person.is_adult
        finally:
            local_db.close()

        # 3. Perform network API request outside of database transaction
        from app.domains.people.services.people_enricher import PeopleEnricher
        sub_enricher = PeopleEnricher(
            None,
            enricher.scrapers,
            enricher.session_factory,
            enricher._is_cancelled_cb,
            enricher._has_active_heavy_tasks_cb,
            enricher._executor,
            enricher._update_progress_cb,
            task_monitor=enricher.task_monitor
        )
        fetched_data = sub_enricher.fetch_external_details(person_name, external_ids, link_data, is_adult=is_adult)
        if not fetched_data:
            return False

        # 4. Short transaction: save the retrieved data to database
        local_db = enricher._get_temp_db()
        try:
            person = local_db.query(Person).filter(Person.id == person_id).first()
            if person:
                sub_enricher.db = local_db
                sub_enricher.apply_enriched_data(person, fetched_data)
                local_db.commit()
                return True
        except Exception as ex:
            local_db.rollback()
            logger.error(f"Failed to save enriched data for person ID {person_id}: {ex}", exc_info=True)
        finally:
            local_db.close()
        return False

    future_to_id = {}
    id_iter = iter(person_ids)
    completed = 0

    while not enricher._is_cancelled(task_id):
        while len(future_to_id) < max_workers:
            try:
                pid = next(id_iter)
            except StopIteration:
                break
            future = executor.submit(enrich_worker, pid)
            future_to_id[future] = pid

        if not future_to_id:
            break

        done, _pending = concurrent.futures.wait(set(future_to_id.keys()), return_when=concurrent.futures.FIRST_COMPLETED)
        for future in done:
            res = future.result()
            if res:
                enriched_count += 1
            completed += 1
            future_to_id.pop(future, None)

            progress = (completed / total) * 100.0
            enricher._update_progress(task_id, progress)
            if progress_callback:
                progress_callback(completed, total)

    for future in list(future_to_id.keys()):
        res = future.result()
        if res:
            enriched_count += 1
        completed += 1
        progress = (completed / total) * 100.0
        enricher._update_progress(task_id, progress)
        if progress_callback:
            progress_callback(completed, total)

    return enriched_count
