# DDD Refactoring Analysis — Swaya Backend

## Jelenlegi struktúra

```
app/
├── core/             ← Shared kernel + Infra szivárgások
├── domains/
│   ├── media/        ← Filesystem + Metadata + Library + Scanner + Formatter
│   ├── people/       ← Person aggregate
│   ├── users/        ← User + Overrides + Tags + Lists
│   ├── settings/     ← SystemSetting + UserSetting
│   ├── history/      ← PlaybackLog + ActionLog
│   └── shared/ports/ ← ScraperGatewayPort
├── application/      ← Félig üres, csak 3 use-case
└── infrastructure/   ← Scrapers
```

---

## 🔴 Kritikus problémák (DDD szabálysértések)

### 1. `core/` God Package — domain logika infra-ba keverve

| Fájl | Probléma | Javasolt hely |
|------|----------|---------------|
| `core/images.py` | Domain service (kép-kiválasztás, thumbnail, TMDB URL resolve) — nem infra | `domains/media_assets/services/image_service.py` |
| `core/image_selectors.py` | Domain logika (logo/backdrop scoring, brightness analysis) | `domains/media_assets/services/image_selectors.py` |
| `core/cache.py` | `CacheService` importálja `domains.media.models.metadata.APICache` → **körkörös domain→core→domain dependency** | `infrastructure/cache/cache_service.py` |
| `core/language.py` | Domain service (locale resolution, localization picking) | `shared_kernel/language.py` |
| `core/fs_utils.py` | Infra utility (Windows long paths, trash, hash) | `infrastructure/filesystem/fs_utils.py` |
| `core/constants.py` | Kevert: TMDB URL-ek (infra) + domain szabályok (image limits, scanner subtypes) | Szétszedni domain/infra konstansokra |
| `core/dating_enums.py` | Teljesen másik domain (dating) enum-jai a core-ban — nincs hozzá domain | Törölni, vagy létrehozni `domains/dating/` |

### 2. `core/tasks/` — Teljes bounded context a core-ban

A `core/tasks` csomag (manager, worker, models, routes, schemas) **saját domain**, nem shared kernel.

> **Javaslat:** `domains/tasks/` vagy `application/tasks/`

### 3. `domains/media/models/__init__.py` — Isten-modul

A `models/__init__.py` **minden domain modelljét** re-exportálja (User, Person, Tag, Setting, PlaybackLog, BackgroundTask). Ez megtöri a bounded context határokat: a `database.py`-ban `import app.domains.media.models` tölti be az összes modelt.

> **Javaslat:** Minden domain saját `__init__.py`-ből exportáljon. A `database.py` init explicit importáljon minden domainből.

---

## 🟡 Közepes problémák

### 4. `domains/media/` — Túl nagy aggregate

A `media` domain jelenleg **3-4 bounded contextet** tartalmaz:

| Jelenlegi | Javasolt bounded context |
|-----------|------------------------|
| `models/filesystem.py` (Library, MediaItem, ExtraFile) | `domains/library/` |
| `models/metadata.py` (MetadataMatch, Studio, Collection, APICache) | `domains/metadata/` |
| `services/scanner/`, `services/formatter/` | `domains/library/services/` |
| `services/library_service.py`, `library_detail_service.py` | `domains/library/services/` |
| `services/recommendations_service.py` | `domains/discovery/` vagy `application/recommendations/` |
| `services/overrides_service.py` | `domains/users/services/` (user-owned data) |
| `services/metadata_service.py` | `domains/metadata/services/` |

### 5. `routes.py` fájlok — Több domain logikát kevernek

A `media/routes.py` (490 sor) importál:
- `application/media/playback_service.py` → history domain
- `application/media/scanner_service.py` → library domain
- `infrastructure/scrapers/gateway.py` → közvetlen infra import route-ban

> **Javaslat:** Routereket bounded context-enként szétszedni + a scraper gateway-t DI-vel injektálni.

### 6. `application/` layer félig üres

Jelenlegi tartalom:
- `application/media/` → scanner_service, scanner_manager, playback_service, renamer_engine
- `application/people/` → enrich_worker
- `application/maintenance/` → database_maintenance_service

A legtöbb use-case viszont `domains/*/services/`-ben van (pl. `LibraryService`, `OverridesService`, `PeopleDetailService`). Nincs konzisztens elválasztás domain service vs application service közt.

---

## 🟢 Kisebb / kozmetikai problémák

### 7. `infrastructure/scrapers/` — Jól strukturált, de a gateway direkt importálva van

A `scraper_gateway` singleton-ként van importálva mindenhol (`from app.infrastructure.scrapers.gateway import scraper_gateway`). DDD-ben a domain/application layernek a `ScraperGatewayPort` protocol-on keresztül kellene kapnia — ez a port már létezik, de nincs használva.

### 8. `domains/shared/` — Csak ports, üres domain

Jelenleg csak a `ports/scrapers.py` van benne. Ha marad, inkább `shared_kernel/`-re nevezni át.

---

## Javasolt célstruktúra

```
app/
├── shared_kernel/           ← Enumok, Base, DB engine, logging
│   ├── database.py
│   ├── enums.py
│   ├── logging.py
│   └── ports/               ← Interfacek (ScraperGatewayPort)
│
├── domains/
│   ├── library/             ← Library, MediaItem, ExtraFile, Scanner, Formatter
│   │   ├── models.py
│   │   ├── services/
│   │   └── routes.py
│   │
│   ├── metadata/            ← MetadataMatch, Studio, Collection, Localization
│   │   ├── models.py
│   │   ├── services/
│   │   └── routes.py
│   │
│   ├── media_assets/        ← ImageProcessingService, image_selectors, download worker
│   │   ├── services/
│   │   └── constants.py
│   │
│   ├── people/              ← (marad, jól van)
│   ├── users/               ← User, Override, Tag, CustomList
│   ├── history/             ← PlaybackLog, ActionLog
│   ├── settings/            ← (marad)
│   └── tasks/               ← BackgroundTask, Manager, Worker
│
├── application/             ← Use-case orchestration (cross-domain)
│   ├── scan_orchestrator.py
│   ├── enrichment_orchestrator.py
│   ├── playback_orchestrator.py
│   └── recommendations/
│
└── infrastructure/
    ├── scrapers/            ← (marad, + gateway impl)
    ├── cache/               ← CacheService + APICache model
    └── filesystem/          ← fs_utils, Windows long-path
```

---

## Megjegyzések

- **Alembic migrációk**: A model-fájlok mozgatása nem töri el a DB-t (a `__tablename__` marad), de az Alembic `env.py` import path-okat frissíteni kell.
- **`dating_enums.py`**: Ha nincs terv dating feature-re, törölhető. Ha igen, saját `domains/dating/` kell neki.

## Verification Plan

### Automated Tests
- `pytest` futtatás a refactoring után
- Import chain ellenőrzés: `python -c "from app.main import app"` — ha elindul, az importok rendben vannak

### Manual Verification
- FastAPI Swagger UI betöltése (`/docs`) — minden route elérhető marad
- Egy scan + enrich workflow végigfuttatása
