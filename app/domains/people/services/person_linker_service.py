import logging
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.domains.people.models import Person, ExternalSourceLink, MediaPersonLink
from app.domains.users.models import UserOverride, Tag
from app.shared_kernel.enums import Provider
from app.infrastructure.scrapers.support.gateway import scraper_gateway

logger = logging.getLogger(__name__)

class PersonLinkerService:
    def link_person_source(
        self,
        db: Session,
        person: Person,
        source: str,
        external_id: str,
        profile_url: Optional[str],
        overrides: Optional[dict],
        current_uid: Optional[int]
    ) -> Dict[str, Any]:
        """Links a Person to an external metadata provider, merges duplicates, and enriches attributes."""
        source = source.lower()
        person = db.merge(person)
        _ = person.external_links
        _ = person.localizations
        try:
            provider_enum = Provider(source)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

        existing_link = db.query(ExternalSourceLink).filter(
            ExternalSourceLink.provider == provider_enum,
            ExternalSourceLink.external_id == external_id
        ).first()

        duplicate_person = None
        if existing_link:
            duplicate_person = existing_link.person

        if not duplicate_person and source == "tmdb":
            try:
                tmdb_int = int(external_id)
                duplicate_person = db.query(Person).filter(Person.id == tmdb_int).first()
            except ValueError as e:
                logger.debug(f"Swallowed exception: {e}", exc_info=True)

        ext_ids = dict(person.external_ids or {})
        ext_ids[source] = str(external_id)
        ext_ids[f"{source}_id"] = str(external_id)
        if "source" not in ext_ids:
            ext_ids["source"] = source
        person.external_ids = ext_ids

        if source in ("stashdb", "fansdb", "theporndb", "porndb"):
            person.is_adult = True

        link = db.query(ExternalSourceLink).filter(
            ExternalSourceLink.person_id == person.id,
            ExternalSourceLink.provider == provider_enum,
            ExternalSourceLink.external_id == external_id
        ).first()
        if not link:
            link = ExternalSourceLink(
                person_id=person.id,
                provider=provider_enum,
                external_id=external_id,
                profile_url=profile_url
            )
            db.add(link)
            person.external_links.append(link)
        else:
            if profile_url:
                link.profile_url = profile_url

        if overrides:
            override_rec = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.person_id == person.id
            ).first()
            if not override_rec:
                override_rec = UserOverride(
                    user_id=current_uid,
                    person_id=person.id
                )
                db.add(override_rec)
            
            if "is_favorite" in overrides:
                override_rec.is_favorite = bool(overrides["is_favorite"])
            if "user_rating" in overrides:
                override_rec.user_rating = overrides["user_rating"]
                override_rec.user_rating_at = datetime.datetime.utcnow()
            if "user_comment" in overrides:
                override_rec.user_comment = overrides["user_comment"]
            if "custom_tags" in overrides:
                tags_input = overrides["custom_tags"] or []
                tags_list = []
                for t in tags_input:
                    tag_obj = None
                    if isinstance(t, dict):
                        tag_id = t.get("id")
                        tag_name = t.get("name")
                        if tag_id:
                            tag_obj = db.query(Tag).filter(Tag.id == tag_id).first()
                        elif tag_name:
                            tag_obj = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
                    elif isinstance(t, int):
                        tag_obj = db.query(Tag).filter(Tag.id == t).first()
                    elif isinstance(t, str):
                        tag_obj = db.query(Tag).filter(func.lower(Tag.name) == func.lower(t)).first()
                        if not tag_obj:
                            tag_obj = Tag(name=t, is_adult=bool(person.is_adult))
                            db.add(tag_obj)
                            db.flush()
                    if tag_obj and tag_obj not in tags_list:
                        tags_list.append(tag_obj)
                override_rec.tags = tags_list

        if duplicate_person and duplicate_person.id != person.id:
            existing_links = db.query(MediaPersonLink).filter(MediaPersonLink.person_id == person.id).all()
            existing_match_roles = {(l.match_id, l.role) for l in existing_links}

            dup_links = db.query(MediaPersonLink).filter(MediaPersonLink.person_id == duplicate_person.id).all()
            for dl in dup_links:
                if (dl.match_id, dl.role) not in existing_match_roles:
                    dl.person_id = person.id
                else:
                    db.delete(dl)

            for ext_link in duplicate_person.external_links:
                exists = db.query(ExternalSourceLink).filter(
                    ExternalSourceLink.person_id == person.id,
                    ExternalSourceLink.provider == ext_link.provider,
                    ExternalSourceLink.external_id == ext_link.external_id
                ).first()
                if not exists:
                    ext_link.person_id = person.id
                    target_ids = dict(person.external_ids or {})
                    target_ids[ext_link.provider.value] = ext_link.external_id
                    target_ids[f"{ext_link.provider.value}_id"] = ext_link.external_id
                    person.external_ids = target_ids
                else:
                    db.delete(ext_link)

            dup_overrides = db.query(UserOverride).filter(
                UserOverride.person_id == duplicate_person.id
            ).all()
            for do in dup_overrides:
                exists = db.query(UserOverride).filter(
                    UserOverride.user_id == do.user_id,
                    UserOverride.person_id == person.id
                ).first()
                if not exists:
                    do.person_id = person.id
                else:
                    if not exists.is_favorite and do.is_favorite:
                        exists.is_favorite = True
                    if exists.user_rating is None and do.user_rating is not None:
                        exists.user_rating = do.user_rating
                        exists.user_rating_at = do.user_rating_at
                    db.delete(do)

            db.delete(duplicate_person)

        try:
            from app.domains.people.services.people_enricher import PeopleEnricher
            enricher = PeopleEnricher(db, scrapers=scraper_gateway)
            
            links = db.query(ExternalSourceLink).filter(ExternalSourceLink.person_id == person.id).all()
            link_data = [{"provider": l.provider, "external_id": l.external_id} for l in links]
            
            for prov_name, ext_id in (person.external_ids or {}).items():
                try:
                    prov = Provider(prov_name.lower())
                    if not any(ld["provider"] == prov for ld in link_data):
                        link_data.append({"provider": prov, "external_id": str(ext_id)})
                except Exception as e:
                    logger.debug(f"Swallowed exception: {e}", exc_info=True)

            fetched_data = enricher.fetch_external_details(
                person.name,
                person.external_ids or {},
                link_data,
                is_adult=person.is_adult
            )
            if fetched_data:
                enricher.apply_enriched_data(person, fetched_data)
        except Exception as e:
            logger.error(f"Failed to dynamically enrich linked person {person.id}: {e}", exc_info=True)

        db.commit()
        return {"status": "success", "linked_person_id": person.id}

    def unlink_person_source(
        self,
        db: Session,
        person: Person,
        source: str,
        action: str
    ) -> Dict[str, Any]:
        """Unlinks a Person from an external metadata source, optionally splitting them into a new entity."""
        source = source.lower()
        action = action.lower()

        try:
            provider_enum = Provider(source)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

        link = db.query(ExternalSourceLink).filter(
            ExternalSourceLink.person_id == person.id,
            ExternalSourceLink.provider == provider_enum
        ).first()

        ext_ids = dict(person.external_ids or {})
        ext_ids.pop(source, None)
        ext_ids.pop(f"{source}_id", None)
        if ext_ids.get("source") == source:
            ext_ids.pop("source", None)
            for k in ["tmdb", "stashdb", "fansdb", "porndb", "theporndb"]:
                if k in ext_ids:
                    ext_ids["source"] = k
                    break
        person.external_ids = ext_ids

        if link:
            if link in person.external_links:
                person.external_links.remove(link)
            db.delete(link)
            db.flush()

        person.recalculate_projection(db)

        if action == "split":
            new_person = Person(
                name=f"{person.name} ({source.upper()})" if person.name else f"Split performer ({source})",
                is_adult=person.is_adult,
                known_for_department=person.known_for_department or "Acting",
                is_active=True,
                profile_path=link.profile_url if (link and link.profile_url) else person.profile_path,
                external_ids={
                    source: link.external_id if link else "",
                    f"{source}_id": link.external_id if link else "",
                    "source": source
                }
            )
            db.add(new_person)
            db.flush()

            if link:
                new_link = ExternalSourceLink(
                    person_id=new_person.id,
                    provider=provider_enum,
                    external_id=link.external_id,
                    profile_url=link.profile_url,
                    source_data=link.source_data
                )
                db.add(new_link)
                new_person.external_links.append(new_link)
                db.flush()
                new_person.recalculate_projection(db)

                try:
                    from app.domains.people.services.people_enricher import PeopleEnricher
                    new_person = db.merge(new_person)
                    _ = new_person.external_links
                    _ = new_person.localizations
                    enricher = PeopleEnricher(db, scrapers=scraper_gateway)
                    
                    link_data = [{"provider": provider_enum, "external_id": link.external_id}]
                    fetched_data = enricher.fetch_external_details(
                        new_person.name,
                        new_person.external_ids or {},
                        link_data,
                        is_adult=new_person.is_adult
                    )
                    if fetched_data:
                        enricher.apply_enriched_data(new_person, fetched_data)
                except Exception as e:
                    logger.error(f"Failed to enrich split person {new_person.id}: {e}", exc_info=True)

            from app.domains.metadata.models import MetadataMatch
            match_ids = db.query(MetadataMatch.id).filter(MetadataMatch.provider == provider_enum).all()
            match_ids_set = {mid for (mid,) in match_ids}

            person_links = db.query(MediaPersonLink).filter(
                MediaPersonLink.person_id == person.id
            ).all()

            for pl in person_links:
                if pl.match_id in match_ids_set:
                    pl.person_id = new_person.id

        db.commit()
        return {"status": "success", "person_id": person.id}
