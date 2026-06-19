from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from ...db import get_session
from ...models import Report

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportOut(BaseModel):
    id: str
    run_id: str
    findings: list
    artifact_urls: dict
    html_report_url: str
    video_url: str
    summary: str
    bugs_found: int

    class Config:
        from_attributes = True


@router.get("/{run_id}", response_model=ReportOut)
async def get_report(run_id: str):
    async with get_session() as session:
        result = await session.execute(select(Report).where(Report.run_id == run_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found — run may still be in progress")
        return ReportOut.model_validate(report)
