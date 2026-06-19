import enum
from datetime import datetime
from sqlalchemy import String, JSON, ForeignKey, DateTime, Enum
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin, new_uuid


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    error = "error"


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    test_case_id: Mapped[str] = mapped_column(String, ForeignKey("test_cases.id"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.queued)
    triggered_by: Mapped[str] = mapped_column(String, default="api")  # api | github | webhook | schedule
    branch: Mapped[str] = mapped_column(String, default="")
    commit_sha: Mapped[str] = mapped_column(String, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(String, default="")

    test_case: Mapped["TestCase"] = relationship(back_populates="runs")
    report: Mapped["Report | None"] = relationship(back_populates="run", uselist=False, cascade="all, delete-orphan")
