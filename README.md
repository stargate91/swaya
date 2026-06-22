# Swaya Backend

Swaya is a high-performance, domain-driven media identification, metadata enrichment, and library organization backend. It serves as the refined, next-generation backend engine for the Swaya application, offering clean database schemas, unified variable structures, and optimized asynchronous processing.

## Key Enhancements over Legacy Backend

* **Clean Domain-Driven Design (DDD):** Organized into distinct layers (`core`, `domains`, `infrastructure`) to eliminate circular imports and enforce a strict separation of concerns.
* **Unified Relational Database Schema:** Fully relational SQLite database managed via SQLAlchemy 2.0 and Alembic migrations, utilizing unified identifiers (e.g. mapping legacy namespaces to `tv`, and SFW/NSFW to unified tracking flags).
* **Asynchronous Background Task Manager:** Built-in task queue supporting concurrent execution, progress tracking, and thread-safe abort/cancellation mechanisms.
* **Aggressive API Caching:** Centralized SQLite-based caching layer for external API queries (TMDB, OMDb, StashDB, PornDB, FansDB) with configurable TTL policies and negative cache support.
* **Robust Image Processing:** On-the-fly local download, format verification, aspect-ratio preserved downscaling, and thumbnail generation for media assets.

## Architectural Layers

The backend codebase is organized as follows:

* **`app/core/`**: Core utilities, database sessions, global enums, file system utilities, and the background task coordinator.
* **`app/domains/`**: Domain-specific models, validation schemas, and service layers:
  * `media`: Handles physical files, library definitions, and metadata matching.
  * `people`: Manages cast, crew, performers, and localizations.
  * `users`: Controls user preferences, custom playlists, ratings, and overrides.
  * `history`: Tracks user playback sessions and audit logs for file operations.
  * `settings`: Stores global system and per-user configuration states.
* **`app/infrastructure/`**: Infrastructure integrations, including scrapers and external API normalization layers.

## Technical Stack

* **Web Framework:** FastAPI (Uvicorn)
* **Validation & Serialization:** Pydantic v2
* **ORM & Database:** SQLAlchemy 2.0 (SQLite)
* **Database Migrations:** Alembic
* **Image Manipulation:** Pillow
* **Testing:** PyTest (AnyIO)

## Getting Started

### Prerequisites

* Python 3.10+
* FFmpeg and FFprobe installed and available in the system path.

### Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Initialize the databases and apply migrations:
   ```bash
   python run.py
   ```

### Running the Application

Start the development server using:
```bash
uvicorn app.main:app --reload --port 8000
```

### Running Tests

Execute the unit and integration test suite:
```bash
python -m pytest
```
