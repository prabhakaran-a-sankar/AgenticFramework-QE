from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from .base import Base, TimestampMixin, new_uuid


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    nl_description: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    max_steps: Mapped[int] = mapped_column(default=30)

    project: Mapped["Project"] = relationship(back_populates="test_cases")
    runs: Mapped[list["Run"]] = relationship(back_populates="test_case", cascade="all, delete-orphan")
