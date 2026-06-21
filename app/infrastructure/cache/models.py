from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import String, Integer, Enum as SQLEnum, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.shared_kernel.database import Base
from app.shared_kernel.enums import Provider, MediaType, CacheStatus


class APICache(Base):
    """
    Unified cache table for all external API queries.
    Prevents redundant HTTP calls and speeds up response times.
    Supports negative caching (e.g., storing failed/404 responses).
    """
    __tablename__ = "api_caches"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[Provider] = mapped_column(SQLEnum(Provider), index=True)
    cache_key: Mapped[str] = mapped_column(String, unique=True, index=True) # e.g. "tmdb/movie/550" or "stashdb/scene/uuid"
    external_id: Mapped[Optional[str]] = mapped_column(String, index=True) # Target entity ID (e.g. TMDB Movie ID or StashDB Scene UUID)
    media_type: Mapped[Optional[MediaType]] = mapped_column(SQLEnum(MediaType), nullable=True, index=True) # Target entity type (e.g. Movie, Scene, Person)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status_code: Mapped[Optional[int]] = mapped_column(Integer) # e.g. 200, 404, 500
    status: Mapped[CacheStatus] = mapped_column(SQLEnum(CacheStatus), default=CacheStatus.VALID, index=True) # Cache state lifecycle
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
