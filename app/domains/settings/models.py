from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import String, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared_kernel.database import Base


class SystemSetting(Base):
    """
    Global system-wide key-value configuration table for API keys,
    library paths, and server configuration.
    """
    __tablename__ = "system_settings"
    
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON) # Stores strings, ints, or configurations
    description: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class UserSetting(Base):
    """
    Per-user key-value preference table for UI language, autoplay,
    theme choices, and search filters.
    """
    __tablename__ = "user_settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_setting_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=1, index=True)
    key: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[Any] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")
