from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ...db import get_session
from ...models import Run, RunStatus, TestCase
from ...workers import run_test_task

router = APIRouter(prefix="/runs", tags=["runs"])


class TriggerRun(BaseModel):
    test_case_id: str
    triggered_by: str = "api"
    branch: str = ""
    commit_sha: str = ""
    platform: str = "web"           # web | mobile_web | mobile_native
    mobile_config: dict = {}        # {"device": "iphone_14"} for mobile_web
    appium_config: dict = {}        # {"desired_caps": {...}} for mobile_native


class RunOut(BaseModel):
    id: str
    test_case_id: str
    status: str
    triggered_by: str
    branch: str
    commit_sha: str
    error_message: str

    class Config:
        from_attributes = True


@router.post("/", response_model=RunOut)
async def trigger_run(body: TriggerRun):
    async with get_session() as session:
        tc_result = await session.execute(
            select(TestCase).options(selectinload(TestCase.project)).where(TestCase.id == body.test_case_id)
        )
        tc = tc_result.scalar_one_or_none()
        if not tc:
            raise HTTPException(404, "Test case not found")

        run = Run(
            test_case_id=body.test_case_id,
            status=RunStatus.queued,
            triggered_by=body.triggered_by,
            branch=body.branch,
            commit_sha=body.commit_sha,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        run_id = run.id

        # Queue the Celery task
        run_test_task.delay(
            run_id=run_id,
            test_case_id=tc.id,
            base_url=tc.project.base_url,
            nl_description=tc.nl_description,
            max_steps=tc.max_steps,
            platform=body.platform,
            mobile_config=body.mobile_config,
            appium_config=body.appium_config,
        )

        return RunOut.model_validate(run)


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: str):
    async with get_session() as session:
        result = await session.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(404, "Run not found")
        return RunOut.model_validate(run)


@router.get("/", response_model=list[RunOut])
async def list_runs(test_case_id: str | None = None, limit: int = 50):
    async with get_session() as session:
        q = select(Run).order_by(Run.created_at.desc()).limit(limit)
        if test_case_id:
            q = q.where(Run.test_case_id == test_case_id)
        result = await session.execute(q)
        return [RunOut.model_validate(r) for r in result.scalars()]
