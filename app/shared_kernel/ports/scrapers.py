from typing import Any, Optional, Protocol

from app.shared_kernel.enums import MediaType, Provider


class ScraperGatewayPort(Protocol):
    """Domain-facing factory and workflow boundary for external metadata providers."""

    def tmdb(self, db_session: Any) -> Any:
        ...

    def adult(self, provider: Provider, db_session: Any) -> Any:
        ...

    def enrich_mainstream(
        self,
        db_session: Any,
        item: Any,
        language: str,
        *,
        commit: bool = True,
    ) -> None:
        ...

    def normalize_adult_scene(self, provider: Provider, raw_data: dict) -> dict:
        ...

    def persist_adult_scene(
        self,
        db_session: Any,
        provider: Provider,
        external_id: str,
        normalized: dict,
        *,
        media_type: Optional[MediaType] = None,
    ) -> Any:
        ...