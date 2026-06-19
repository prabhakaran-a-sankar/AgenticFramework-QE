from dataclasses import dataclass
from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin, new_uuid


@dataclass
class Finding:
    severity: str  # critical | high | medium | low | info
    title: str
    description: str
    step_index: int
    screenshot_url: str = ""
    expected: str = ""
    actual: str = ""


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("runs.id"), nullable=False, unique=True)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    artifact_urls: Mapped[dict] = mapped_column(JSON, default=dict)
    html_report_url: Mapped[str] = mapped_column(String, default="")
    video_url: Mapped[str] = mapped_column(String, default="")
    summary: Mapped[str] = mapped_column(String, default="")
    bugs_found: Mapped[int] = mapped_column(default=0)

    run: Mapped["Run"] = relationship(back_populates="report")
