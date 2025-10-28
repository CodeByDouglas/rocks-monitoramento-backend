from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

Base = declarative_base()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    machines: Mapped[list["Machine"]] = relationship(back_populates="owner", cascade="all, delete")


class Machine(Base, TimestampMixin):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mac_address: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(32), default="pc")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    owner: Mapped[User] = relationship(back_populates="machines")
    configuration: Mapped["MachineConfiguration" | None] = relationship(
        back_populates="machine", uselist=False, cascade="all, delete-orphan"
    )
    metrics: Mapped[list["MonitoringData"]] = relationship(
        back_populates="machine", cascade="all, delete-orphan"
    )


class MachineConfiguration(Base, TimestampMixin):
    __tablename__ = "machine_configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), unique=True)
    raw_payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))

    machine: Mapped[Machine] = relationship(back_populates="configuration")


class MonitoringData(Base, TimestampMixin):
    __tablename__ = "monitoring_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    reference_id: Mapped[str] = mapped_column(String(64), default=lambda: uuid.uuid4().hex, unique=True)

    machine: Mapped[Machine] = relationship(back_populates="metrics")
