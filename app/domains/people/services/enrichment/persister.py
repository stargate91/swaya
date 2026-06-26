import logging
from app.domains.people.models import Person, PersonLocalization, ExternalSourceLink
from app.domains.people.services.enrichment.helpers import EnrichmentHelpers

logger = logging.getLogger(__name__)

def apply_enriched_data(enricher, person: Person, data: dict):
    if data.get("birthday"):
        person.birthday = data["birthday"]
    if data.get("deathday"):
        person.deathday = data["deathday"]
    if data.get("place_of_birth"):
        person.place_of_birth = data["place_of_birth"]
    if data.get("known_for_department"):
        person.known_for_department = data["known_for_department"]
    if data.get("homepage"):
        person.homepage = data["homepage"]
    if data.get("gender") is not None:
        person.gender = data["gender"]
    if data.get("popularity") is not None:
        person.popularity = data["popularity"]
    if data.get("rating_porndb") is not None:
        person.rating_porndb = float(data["rating_porndb"])
    if data.get("scene_count") is not None:
        person.scene_count = max(person.scene_count or 0, int(data["scene_count"]))
    if data.get("ethnicity"):
        person.ethnicity = data["ethnicity"]
    if data.get("hair_color"):
        person.hair_color = data["hair_color"]
    if data.get("eye_color"):
        person.eye_color = data["eye_color"]
    if data.get("height") is not None:
        person.height = data["height"]
    if data.get("measurements"):
        person.measurements = data["measurements"]
    if data.get("cup_size"):
        person.cup_size = data["cup_size"]
        
    # Save extended performer attributes
    if data.get("weight") is not None:
        person.weight = data["weight"]
    if data.get("aliases"):
        existing_aliases = person.aliases or []
        person.aliases = list(set(existing_aliases + data["aliases"]))
    if data.get("tattoos"):
        person.tattoos = data["tattoos"]
    if data.get("piercings"):
        person.piercings = data["piercings"]
    if data.get("orientation"):
        person.orientation = data["orientation"]
    if data.get("career_start_year") is not None:
        person.career_start_year = data["career_start_year"]
    if data.get("career_end_year") is not None:
        person.career_end_year = data["career_end_year"]
    if data.get("socials"):
        existing_socials = person.socials or {}
        existing_socials.update(data["socials"])
        person.socials = existing_socials

    if data.get("urls"):
        ids = person.external_ids or {}
        existing_urls = ids.get("urls") or []
        existing_urls_set = {u.get("url") if isinstance(u, dict) else u for u in existing_urls}
        for new_url in data["urls"]:
            url_str = new_url.get("url") if isinstance(new_url, dict) else new_url
            if url_str and url_str not in existing_urls_set:
                existing_urls.append({"url": url_str})
                existing_urls_set.add(url_str)
        ids["urls"] = existing_urls
        person.external_ids = ids

    for l in data["links_to_create"]:
        link = enricher.db.query(ExternalSourceLink).filter(
            ExternalSourceLink.person_id == person.id,
            ExternalSourceLink.provider == l["provider"],
            ExternalSourceLink.external_id == l["external_id"]
        ).first()
        if not link:
            new_link = ExternalSourceLink(
                person_id=person.id,
                provider=l["provider"],
                external_id=l["external_id"]
            )
            enricher.db.add(new_link)

    for locale, bio in data["biographies"].items():
        save_bio(enricher, person.id, locale, bio)

    profile_path = data.get("profile_path")
    if profile_path:
        person.profile_path = profile_path
        tmdb_id = person.external_ids.get("tmdb") if person.external_ids else None
        
        from app.domains.media_assets.services.images import image_processing_service
        url = image_processing_service.get_download_url(profile_path, "people") or profile_path
        
        if tmdb_id:
            import os
            clean_path = os.path.basename(profile_path)
            filename = f"tmdb_{tmdb_id}_{clean_path}"
        else:
            import os
            ext = os.path.splitext(profile_path)[1] or ".jpg"
            ext_id = "unknown"
            prov_val = "perf"
            if person.external_ids:
                for k, v in person.external_ids.items():
                    prov_val = k
                    ext_id = v
                    break
            filename = f"{prov_val}_{ext_id}{ext}"

        existing_imgs = person.images or []
        new_imgs = data.get("images") or []
        person.images = EnrichmentHelpers.merge_images(existing_imgs, new_imgs)

        if enricher.image_downloader:
            enricher.image_downloader.enqueue_download(url, "people", filename)
        else:
            logger.warning("No image_downloader available for profile image download")

def save_bio(enricher, person_id: int, locale: str, biography: str):
    loc = enricher.db.query(PersonLocalization).filter(
        PersonLocalization.person_id == person_id,
        PersonLocalization.locale == locale
    ).first()
    if not loc:
        loc = PersonLocalization(person_id=person_id, locale=locale, biography=biography)
        enricher.db.add(loc)
    else:
        loc.biography = biography
