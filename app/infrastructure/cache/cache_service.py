from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from sqlalchemy.orm import Session

from app.shared_kernel.database import CacheSessionLocal
from app.shared_kernel.enums import Provider, MediaType, CacheStatus
from app.infrastructure.cache.models import APICache
from app.shared_kernel.constants import DEFAULT_TTLS


class CacheService:
    """
    Manages API query caching in cache.db to optimize requests and enforce cache policies.
    Supports user-triggered refreshes and event-based cache invalidations.
    """

    @staticmethod
    def get_ttl_for_key(cache_key: str, media_type: Optional[MediaType] = None) -> Optional[int]:
        """Determines the TTL based on the cache key or media type."""
        # Search queries
        if "/search/" in cache_key or cache_key.endswith("/search"):
            return DEFAULT_TTLS["search"]
        
        # Dynamic data (recommendations, credits, popular/trending, rating)
        if (
            "/credits" in cache_key 
            or "/recommendations" in cache_key 
            or "/trending" in cache_key
            or "/popular" in cache_key
            or "/rating" in cache_key
        ):
            return DEFAULT_TTLS["dynamic"]

        # Default static data (details)
        return DEFAULT_TTLS["static"]

    def __init__(self, session_factory=CacheSessionLocal):
        self.session_factory = session_factory

    def get(self, provider: Provider, cache_key: str, force_refresh: bool = False) -> Optional[dict[str, Any]]:
        """
        Retrieves valid cached data from cache.db.
        If force_refresh is True, the entry is invalidated and None is returned.
        If cache is expired or not found, returns None.
        """
        if force_refresh:
            self.invalidate(provider, cache_key)
            return None

        with self.session_factory() as db:
            cache = db.query(APICache).filter(
                APICache.provider == provider,
                APICache.cache_key == cache_key
            ).first()

            if not cache:
                return None

            # SQLite may return timezone-aware columns as naive datetimes.
            expires_at = cache.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at and datetime.now(timezone.utc) > expires_at:
                cache.status = CacheStatus.EXPIRED
                db.commit()
                return None

            if cache.status in (CacheStatus.FAILED, CacheStatus.NOT_FOUND):
                # Negative cache hit (e.g. 404 cached)
                return {"status_code": cache.status_code, "raw_data": cache.raw_data, "cached_error": True}

            return cache.raw_data

    def set(
        self,
        provider: Provider,
        cache_key: str,
        raw_data: dict[str, Any],
        status_code: int = 200,
        media_type: Optional[MediaType] = None,
        external_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Stores API response in cache.db. Supports negative caching for failures.
        """
        # Determine TTL
        if ttl_seconds is None:
            if status_code >= 400 or not raw_data:
                ttl_seconds = DEFAULT_TTLS["failed"]
            else:
                ttl_seconds = self.get_ttl_for_key(cache_key, media_type)

        expires_at = None
        if ttl_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        # Determine Cache Status
        if status_code == 404:
            status = CacheStatus.NOT_FOUND
        elif status_code >= 400:
            status = CacheStatus.FAILED
        else:
            status = CacheStatus.VALID

        with self.session_factory() as db:
            cache = db.query(APICache).filter(
                APICache.provider == provider,
                APICache.cache_key == cache_key
            ).first()

            if cache:
                cache.raw_data = raw_data
                cache.status_code = status_code
                cache.status = status
                cache.external_id = external_id
                cache.media_type = media_type
                cache.expires_at = expires_at
                cache.updated_at = datetime.now(timezone.utc)
            else:
                cache = APICache(
                    provider=provider,
                    cache_key=cache_key,
                    external_id=external_id,
                    media_type=media_type,
                    raw_data=raw_data,
                    status_code=status_code,
                    status=status,
                    expires_at=expires_at
                )
                db.add(cache)
            db.commit()

    def invalidate(self, provider: Provider, cache_key: str) -> None:
        """Removes a specific cache key entry."""
        with self.session_factory() as db:
            db.query(APICache).filter(
                APICache.provider == provider,
                APICache.cache_key == cache_key
            ).delete(synchronize_session=False)
            db.commit()

    def invalidate_by_prefix(self, provider: Provider, key_prefix: str) -> None:
        """Invalidates all cache entries matching key_prefix (starts with)."""
        with self.session_factory() as db:
            db.query(APICache).filter(
                APICache.provider == provider,
                APICache.cache_key.like(f"{key_prefix}%")
            ).delete(synchronize_session=False)
            db.commit()

    def cleanup_expired(self) -> int:
        """
        Deletes all expired cache entries from cache.db.
        Returns the number of deleted records.
        """
        with self.session_factory() as db:
            deleted_count = db.query(APICache).filter(
                APICache.expires_at.is_not(None),
                APICache.expires_at < datetime.now(timezone.utc)
            ).delete(synchronize_session=False)
            db.commit()
            return deleted_count

    def clear_all(self) -> None:
        """Fully clears the api_caches table, emptying the cache."""
        with self.session_factory() as db:
            db.query(APICache).delete(synchronize_session=False)
            db.commit()

    def get_stats(self) -> dict[str, int]:
        """
        Returns stats about the cached entries.
        Keys: 'total', 'valid', 'expired'
        """
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            total = db.query(APICache).count()
            expired = db.query(APICache).filter(
                APICache.expires_at.is_not(None),
                APICache.expires_at < now
            ).count()
            valid = total - expired
            return {
                "total": total,
                "valid": valid,
                "expired": expired
            }
