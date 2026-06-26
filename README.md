# Swaya

Swaya is a media library management application consisting of an Electron + React frontend and a FastAPI backend, both hosted in this repository.

The application scans local directories, identifies media files, resolves metadata from external services, and tracks playback state.

## Repository structure

- **frontend/**: React + Electron client application
- **app/**: FastAPI backend engine (business logic, DB adapters, scrapers)

---

## Backend

The backend follows a DDD (Domain-Driven Design) layered structure:

```
app/
  application/       -- HTTP layer: routes, Pydantic schemas, validation
    catalog/           organizer/discovery API
    history/           watch history queries
    library/           library endpoints (listing, filtering, details)
    media/             media playback and preview
    metadata/          metadata queries (TMDB search, details)
    organizer/         organizer page API (discovery, override, rename)
    people/            people (actors, directors) endpoints
    recommendations/   recommendation API
    settings/          application settings
    tasks/             background task control and status
    users/             user management, overrides, custom lists

  domains/            -- business logic: models, domain services
    history/           watch and audit log models
    library/           library, media item, extra file models; scanner, renamer, formatter
    media/             media access and playback logic
    media_assets/      image processing (download, crop, thumbnails)
    metadata/          metadata match models
    people/            person models, enrichment logic
    recommendations/   recommendation algorithm
    settings/          system settings models
    tasks/             background task manager (manager, worker, queue)
    users/             user, UserOverride, custom lists, tags

  infrastructure/     -- external system integrations
    cache/             SQLite-based API cache (TTL, negative cache)
    filesystem/        file system operations, watchdog
    media/             DB adapters, resolver, media item port implementation
    playback/          playback monitoring (player detector, monitor)
    repositories/      generic repository pattern
    scrapers/          API providers (TMDB, OMDb, StashDB, PornDB, FansDB),
                       resolve pipelines, enrichment and parser modules
    settings/          settings persistence
    tasks/             task-specific adapters (image download)

  shared_kernel/      -- shared elements: enums, constants, DB session, ports
```

### Tech stack

| Category            | Tool                      |
|---------------------|---------------------------|
| Web framework       | FastAPI + Uvicorn          |
| Validation          | Pydantic v2                |
| ORM                 | SQLAlchemy 2.0             |
| Database            | SQLite                     |
| Migrations          | Alembic                    |
| Image processing    | Pillow                     |
| File identification | guessit                    |
| File watching       | watchdog                   |
| Testing             | pytest + anyio             |
| Platform            | Windows (pywin32)          |

### Prerequisites

- Python 3.10+
- FFmpeg and FFprobe available on PATH

### Setup and running

Install dependencies:
```bash
pip install -r requirements.txt
```

Start the server:
```bash
python run.py
```

Or directly via Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```

Databases and directories are created automatically on first run.

### Migrations

Managing Alembic migrations:
```bash
# Apply current schema
alembic upgrade head

# Generate a new migration after model changes
alembic revision --autogenerate -m "description"
```

### Tests

```bash
python -m pytest
```

---

## Frontend

The frontend is built with React 19, Vite, and runs inside Electron.

### Tech stack

| Category            | Tool                      |
|---------------------|---------------------------|
| Shell/Runtime       | Electron                  |
| Bundler/Dev server  | Vite                      |
| UI Library          | React 19                  |
| State management    | Zustand                   |
| Data fetching       | TanStack Query (v5)       |
| Routing             | React Router 7            |

### Setup and running

Go to the frontend directory:
```bash
cd frontend
```

Install dependencies:
```bash
npm install
```

Start in development mode (launches Vite dev server and Electron window):
```bash
npm run dev
```

Build and package instructions are defined in the `package.json` scripts.
