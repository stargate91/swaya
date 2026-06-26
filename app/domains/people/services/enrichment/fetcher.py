from typing import List, Optional
from app.shared_kernel.enums import Provider

class PrioritizedResultDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._priorities = {}
        self.current_provider = None

    def set_provider(self, provider):
        self.current_provider = provider

    def __setitem__(self, key, value):
        single_val_fields = {
            "birthday", "deathday", "place_of_birth", "gender", "profile_path",
            "ethnicity", "hair_color", "eye_color", "height", "weight",
            "measurements", "cup_size", "tattoos", "piercings", "same_sex_only",
            "career_start_year", "career_end_year", "known_for_department", "popularity", "homepage"
        }
        if key in single_val_fields:
            if value is None or value == "":
                if key in self and self[key] is not None:
                    return
                super().__setitem__(key, value)
                return
            
            priorities = {
                Provider.TMDB: 4,
                Provider.STASHDB: 3,
                Provider.FANSDB: 2,
                Provider.PORNDB: 1
            }
            prio = priorities.get(self.current_provider, 0)
            existing_prio = self._priorities.get(key, -1)
            if prio >= existing_prio:
                super().__setitem__(key, value)
                self._priorities[key] = prio
        else:
            if key == "biographies" and isinstance(value, dict):
                if key not in self:
                    super().__setitem__(key, {})
                priorities = {
                    Provider.TMDB: 4,
                    Provider.STASHDB: 3,
                    Provider.FANSDB: 2,
                    Provider.PORNDB: 1
                }
                prio = priorities.get(self.current_provider, 0)
                for loc, bio in value.items():
                    bio_key = f"bio_{loc}"
                    existing_prio = self._priorities.get(bio_key, -1)
                    if bio and prio >= existing_prio:
                        self[key][loc] = bio
                        self._priorities[bio_key] = prio
            else:
                super().__setitem__(key, value)

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

    result = PrioritizedResultDict({
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
        "same_sex_only": None,
        "socials": {},
        "urls": [],
        "known_for_department": None,
        "career_start_year": None,
        "career_end_year": None,
        "homepage": None,
        "provider_profiles": {}
    })

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

        result.set_provider(provider)

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
                result.set_provider(prov)
                result["links_to_create"].append({"provider": prov, "external_id": str(ext_id)})
        except ValueError:
            pass

    return result if has_data else None
