from typing import List, Optional
from app.shared_kernel.enums import Provider

def fetch_external_details(
    enricher,
    name: str,
    external_ids: dict,
    links: List[dict],
    settings: Optional[dict] = None,
    is_adult: bool = False
) -> Optional[dict]:
    all_links = list(links)
    if not all_links:
        for prov_name, ext_id in external_ids.items():
            try:
                prov = Provider(prov_name)
                all_links.append({"provider": prov, "external_id": str(ext_id)})
            except ValueError:
                pass

    result = {
        "birthday": None,
        "deathday": None,
        "place_of_birth": None,
        "gender": None,
        "popularity": None,
        "rating_porndb": None,
        "scene_count": None,
        "profile_path": None,
        "images": None,
        "ethnicity": None,
        "hair_color": None,
        "eye_color": None,
        "height": None,
        "measurements": None,
        "cup_size": None,
        "biographies": {},
        "links_to_create": [],
        "aliases": [],
        "weight": None,
        "tattoos": None,
        "piercings": None,
        "orientation": None,
        "socials": {},
        "urls": [],
        "known_for_department": None,
        "career_start_year": None,
        "career_end_year": None
    }

    has_data = False
    processed_pairs = set()
    to_process = list(all_links)

    while to_process:
        l = to_process.pop(0)
        provider = l["provider"]
        external_id = l["external_id"]

        pair = (provider, external_id)
        if pair in processed_pairs:
            continue
        processed_pairs.add(pair)

        if provider == Provider.TMDB:
            if enricher.tmdb_enricher:
                if enricher.tmdb_enricher.enrich_tmdb(external_id, result):
                    has_data = True
        elif provider in (Provider.STASHDB, Provider.PORNDB, Provider.FANSDB):
            if enricher.adult_enricher:
                if enricher.adult_enricher.enrich_adult(provider, external_id, result, to_process, processed_pairs):
                    has_data = True

    existing_providers = {l["provider"] for l in links}
    for prov_name, ext_id in external_ids.items():
        try:
            prov = Provider(prov_name)
            if prov not in existing_providers:
                result["links_to_create"].append({"provider": prov, "external_id": str(ext_id)})
        except ValueError:
            pass

    return result if has_data else None
