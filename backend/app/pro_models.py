from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class CycleCount(Base):
    __tablename__ = "cycle_counts"
    id: Mapped[int] = mapped_column(primary_key=True)
    count_no: Mapped[str] = mapped_column(String(60), unique=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    expected_quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    counted_quantity: Mapped[float] = mapped_column(Numeric(14, 3))
    inventory_snapshot: Mapped[str] = mapped_column(String(80))
    hu_snapshot: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SampleSet(Base):
    __tablename__ = 'sample_sets'
    id: Mapped[int] = mapped_column(primary_key=True)
    profile: Mapped[str | None] = mapped_column(String(20))
    manifest: Mapped[str] = mapped_column(Text, default='{}', server_default='{}')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
