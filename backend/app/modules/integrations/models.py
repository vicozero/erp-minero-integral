from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSON_DICT


class ExternalSystem(Base):
    __tablename__ = "external_system"
    __table_args__ = {"schema": "intg"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    official_inventory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    __table_args__ = (
        Index("ix_outbox_pending", "status", "available_at"),
        {"schema": "intg"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    aggregate_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_DICT, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    available_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class InboxEvent(Base):
    __tablename__ = "inbox_event"
    __table_args__ = {"schema": "intg"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    source_system_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSON_DICT, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED", nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
