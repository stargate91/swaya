# Backend Refactoring Audit — Kritikustól Nice-to-do-ig

## ⛔ ABSZOLÚT ALAPSZABÁLY: MŰKÖDŐ LOGIKA NEM MÓDOSULHAT / NEM TÖRHET MEG!
* **Azonos Viselkedés (Zero-Behavior-Change):** A refaktorálás kizárólag a kód szerkezeti átrendezésére (fájlok szétbontása, domain határok tisztázása, importok tisztítása) irányulhat. Az üzleti logika, a meglévő funkciók, az adatformátumok és a működési logikák **teljesen érintetlenül kell, hogy maradjanak**!
* **Tilos az önkényes átírás:** Bármilyen működő kódrészlet logikájának megváltoztatása szigorúan tilos, a meglévő működést minden esetben hiánytalanul meg kell őrizni. Semmi sem törhet meg!

---

## 🔴 KRITIKUS (Azonnal — nagy tech debt, nehezen bővíthető)

### 1. `library_service.py` — God Object (845 sor)
**Probléma:** Egyetlen osztályban van a stats, continue-watching, paginated listing, collections, people group, filter options, tag groups. 7+ felelősség egy fájlban.

**Megoldás:** Szétdarabolni 4-5 service-re:
- `library_stats_service.py` — stats + storage számítás
- `library_listing_service.py` — tab page + grouped library
- `library_collection_service.py` — collection listing
- `library_people_service.py` → áthelyezni a `people` domainbe
- `library_filter_service.py` — filter options + tag groups

**Cross-domain imports megszüntetendők:**
- `from app.domains.metadata.models` → 3 helyen
- `from app.domains.users.models` → 2 helyen  
- `from app.domains.settings.models` → 1 helyen
- `from app.domains.people.models` → 1 helyen (inline import is!)

> 🗺️ **MAPPÁZÁS KELL** — Új fájlok: `app/domains/library/services/` alá 4-5 új service

---

### 2. `library_detail_service.py` — God Object (696 sor)
**Probléma:** 3 teljesen különböző detail pathway egy osztályban (StashDB virtual, TMDB virtual, local MediaItem), + TV detail, season detail, collection detail. Mindegyik saját formázási logikával.

**Megoldás:** Szétdarabolni provider-specifikus detail service-ekre:
- `movie_detail_service.py` — local item + virtual TMDB
- `tv_detail_service.py` — TV show + season detail
- `scene_detail_service.py` — StashDB/FansDB scenes
- `collection_detail_service.py` — collection detail
- Közös `_detail_formatter.py` — shared helper (image resolve, override apply)

**Cross-domain imports:** metadata, people, users, media_assets mind importálva

> 🗺️ **MAPPÁZÁS KELL** — `app/domains/library/services/detail/` almappa 5 fájllal

---

### 3. `library/routes.py` — Mega Route File (437 sor)
**Probléma:** Egyetlen route fájl tartalmaz 4 különböző routert (`mainstream_router`, `adult_router`, `router`, `library_router`) + 30+ endpointot. Scanner, renamer, playback, recommendations, overrides, discovery mind ide van bedrótózva.

**Megoldás:**
- Override endpointok → `users/routes.py`-ba (saját domain!)
- Scanner/renamer → `app/application/media/routes.py` (application layer)
- Recommendations/discovery/watchlist → `app/application/recommendations/routes.py`
- Playback/watch-history → saját route fájl

> 🗺️ **MAPPÁZÁS KELL** — Route szétbontás 4-5 fájlba. Frontend API útvonalak NEM változnak, csak a backend fájl szervezés.

---

## 🟠 FONTOS (Rövid távon — kód minőség + karbantarthatóság)

### 4. `overrides_service.py` — Cross-domain Boundary Violation
**Probléma:** A `users` domain service-e közvetlenül importál `library.models.MediaItem`-et és `metadata.models.MetadataMatch`-et. Az `_get_or_create_override` metódus saját maga oldja fel az item ID-ket DB query-kkel más domain modelljeire.

**Megoldás:** Item resolution logikát portba / shared service-be kiemelni. Az override service csak `UserOverride`-dal dolgozzon, az ID feloldást dependency injectionnel kapja.

> 🔧 **Refaktor helyben** — Nincs mappázás, de interface/port kell hozzá

---

### 5. `lists_service.py` — 4 domain modell közvetlen import ✅ KÉSZ
**Probléma:** `users` domain service importál `library.MediaItem`, `metadata.MetadataMatch`, `metadata.MetadataLocalization`, `people.Person` modelleket. Gyakorlatilag mindenhez hozzányúl.

**Megoldás:** ~~A list item resolution logikát portokba kiemelni, vagy a `ListsService`-t az `application` layerbe mozgatni.~~
**Elvégezve:** `ListsService` áthelyezve → `app/application/catalog/lists_service.py`

---

### 6. `people_detail_service.py` — Cross-domain + 418 sor
**Probléma:** 5 domain importálva (library, metadata, people, settings, media_assets). Formázási logika (filmográfia aggregáció, popularity számítás) összekeveredve a DB lekérdezésekkel.

**Megoldás:** 
- Filmography aggregation → külön `filmography_service.py`
- Image resolution → shared infrastructure service-en keresztül
- Settings query → port/interface-en keresztül

> 🗺️ **MAPPÁZÁS KELL** — `app/domains/people/services/` alá új fájl

---

### 7. Inline Importok (Code Smell)
**Probléma:** Több helyen function-level inline importok:
- `library_service.py:446`: `from app.domains.users.models import Tag, user_override_tags`
- `library_service.py:588`: `from app.shared_kernel.language import LanguageService`
- `library_service.py:731`: `from app.domains.people.models import Person`
- `library_routes.py:62, 162, 192, 249, 304`: route fájlban 5 inline service import

**Megoldás:** A God Object feldarabolás automatikusan megoldja ezeket.

> 🔧 **Refaktor helyben** — A szétdarabolás mellékterméke

---

## 🟡 KÖZEPES (Középtávon — architektúra tisztaság)

### 8. `people_enricher.py` — Tight Coupling to Settings + Media Assets
**Probléma:** 392 sor, közvetlenül importálja `settings.models` és `media_assets.services`. A settings olvasás és image kezelés nem portokon/interface-eken keresztül történik.

**Megoldás:** 
- `SettingsPort` bevezetése a `shared_kernel/ports/`-ba
- Image service DI-vel injektálni

> 🔧 **Refaktor helyben** — Port bevezetés, nincs mappázás

---

### 9. Application Layer Hiányos Használata
**Probléma:** Az `application/` layer már létezik (`playback_service`, `scanner_service`, `renamer_engine`, `recommendations_service`), de ezek route-jai még a `library/routes.py`-ban vannak. Az application layer service-eknek saját route fájljaik kellenének.

**Megoldás:** Application layer route-ok létrehozása:
- `app/application/media/routes.py` — scanner, renamer, playback
- `app/application/recommendations/routes.py` — recommendations, discovery, watchlist

> 🗺️ **MAPPÁZÁS KELL** — `app/application/*/routes.py` fájlok

---

### 10. `scanner_service.py` + `scan_collector.py` — Settings Cross-domain
**Probléma:** Scanner kód közvetlenül importálja `settings.models.SystemSetting`-et. A scanner categorizer és collector is.

**Megoldás:** `SettingsPort` interface-en keresztül konfigurációt kapni.

> 🔧 **Refaktor helyben**

---

### 11. Dict-alapú Return Típusok Mindenhol
**Probléma:** A service-ek szinte mindenhol `Dict[str, Any]`-t adnak vissza. Nincs típusbiztonság, a frontend és a service réteg között szerződés csak implicit.

**Megoldás:** Response DTO-k (Pydantic modellek) bevezetése legalább a kritikus endpointokhoz.

> 🔧 **Refaktor helyben** — Schemas bővítés, nincs mappázás

---

## 🟢 NICE-TO-DO (Hosszú távon — finomhangolás)

### 12. Hardcoded `user_id = 1`
**Probléma:** `overrides_service.py:28`, `library_service.py` (361, 401, 411, 444, 457, 471 sorok), `library_detail_service.py:108`. Mindenhol `user_id == 1` van hardcode-olva.

**Megoldás:** User context injektálás middleware-ből vagy dependency injection-ből.

> 🔧 **Refaktor helyben** — Ha multi-user support kell

---

### 13. `ImageProcessingService` Közvetlen Instanciálás
**Probléma:** 6+ helyen `ImageProcessingService()` közvetlenül példányosítva (detail service-ek, enricher, overrides, settings). Nincs DI.

**Megoldás:** Singleton / DI container-ből kapni.

> 🔧 **Refaktor helyben**

---

### 14. Error Handling Inkonzisztencia
**Probléma:** Egyes service-ek `{"error": "..."}` dict-et adnak, mások `JSONResponse`-t, megint mások `HTTPException`-t. Nincs egységes error pattern.

**Megoldás:** Unified error handling: service-ek custom exception-öket dobjanak, route layer konvertálja HTTP response-szá.

> 🔧 **Refaktor helyben**

---

### 15. `MetadataMatchRead` Hiányzó Referencia
**Probléma:** `library/routes.py:36, 43`: `MetadataMatchRead` nincs importálva, runtime `globals()` check-kel kerüli meg → ez soha nem fog működni, mindig `list`-re esik vissza.

**Megoldás:** Megfelelő response model létrehozása és importálása, vagy explicit `list` response model.

> 🔧 **Refaktor helyben** — Bug fix jellegű

---

## Összefoglaló Tábla

| # | Prioritás | Fájl/Terület | Fő Probléma | Mappázás kell? |
|---|-----------|-------------|-------------|---------------|
| 1 | 🔴 Kritikus | `library_service.py` | God Object (845 sor, 7+ felelősség) | ✅ Igen |
| 2 | 🔴 Kritikus | `library_detail_service.py` | God Object (696 sor, 6 pathway) | ✅ Igen |
| 3 | 🔴 Kritikus | `library/routes.py` | Mega Route (437 sor, 30+ endpoint, 4 router) | ✅ Igen |
| 4 | 🟠 Fontos | `overrides_service.py` | Cross-domain boundary violation | ❌ Helyben |
| 5 | 🟠 Fontos | ~~`lists_service.py`~~ | ~~4 domain modell import~~ | ✅ KÉSZ |
| 6 | 🟠 Fontos | `people_detail_service.py` | 5 domain import + 418 sor | ✅ Igen |
| 7 | 🟠 Fontos | Inline imports (6+ helyen) | Code smell | ❌ Helyben |
| 8 | 🟡 Közepes | `people_enricher.py` | Settings + media_assets coupling | ❌ Helyben |
| 9 | 🟡 Közepes | Application layer routes | Route-ok rossz helyen | ✅ Igen |
| 10 | 🟡 Közepes | Scanner settings coupling | Cross-domain | ❌ Helyben |
| 11 | 🟡 Közepes | Dict return types | Nincs típusbiztonság | ❌ Helyben |
| 12 | 🟢 Nice-to-do | `user_id = 1` hardcode | Multi-user blocker | ❌ Helyben |
| 13 | 🟢 Nice-to-do | `ImageProcessingService` DI | Nincs dependency injection | ❌ Helyben |
| 14 | 🟢 Nice-to-do | Error handling | Inkonzisztens pattern | ❌ Helyben |
| 15 | 🟢 Nice-to-do | `MetadataMatchRead` bug | Globals() runtime hack | ❌ Helyben |

## Elvégzett DDD Áthelyezések

- ✅ Override schemas (`ItemOverridesUpdate`, `BulkOverridesUpdate`, etc.) → `users/schemas.py`
- ✅ `ListsService` → `app/application/catalog/lists_service.py`
- ✅ `get_people_group()` → `app/domains/people/services/people_library_service.py`

---

## ⚠️ FONTOS / KRITIKUS SZABÁLY (Semmi sem törhet meg!)

### `ImageProcessingService` és `constants.py` Letöltési Logika
* **SZABÁLY:** Az aktuális kép-letöltési, mentési és felbontási logika **SEMMI ESETRE SEM TÖRHET MEG** (at all cost)!
* **Részletek:** A letöltési méreteket és a mentési konfigurációkat szigorúan a `constants.py`-ban definiált `TMDB_DOWNLOAD_SIZES` konstansnak megfelelően kell kezelni a letöltés során. Ezt a logikát később is használni szeretnénk, így refaktorálás vagy módosítás során a meglévő működést meg kell tartani – semmi sem törhet meg a jelenlegi logikában.
