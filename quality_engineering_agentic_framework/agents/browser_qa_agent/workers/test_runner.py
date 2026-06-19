import asyncio
from datetime import datetime
from .celery_app import celery_app
from ..planner import QAPlanner
from ..llm import LLMClient
from ..reporter import Reporter
from ..storage import get_storage
from ..config import get_settings


async def _run_test(run_id: str, test_case_id: str, base_url: str, nl_description: str, max_steps: int, platform: str = "web", mobile_config: dict = {}, appium_config: dict = {}):
    settings = get_settings()
    storage = get_storage()
    llm = LLMClient()
    planner = QAPlanner(llm=llm, storage=storage, max_steps=max_steps, platform=platform, mobile_config=mobile_config, appium_config=appium_config)
    reporter = Reporter(storage=storage)

    result = await planner.run(run_id=run_id, base_url=base_url, nl_description=nl_description)
    report_data = await reporter.generate(run_id=run_id, result=result)

    # Persist to DB
    from ..db import get_session
    from ..models import Run, RunStatus, Report
    from sqlalchemy import select

    async with get_session() as session:
        run_result = await session.execute(select(Run).where(Run.id == run_id))
        run = run_result.scalar_one_or_none()
        if run:
            run.status = RunStatus(result.status if result.status in ("passed", "failed") else "error")
            run.finished_at = datetime.utcnow()
            run.error_message = result.summary if result.status == "error" else ""

            report = Report(
                run_id=run_id,
                findings=report_data["findings"],
                artifact_urls=report_data["artifact_urls"],
                html_report_url=report_data["html_report_url"],
                video_url=report_data["video_url"],
                summary=report_data["summary"],
                bugs_found=report_data["bugs_found"],
            )
            session.add(report)

    return {
        "run_id": run_id,
        "status": result.status,
        "bugs_found": report_data["bugs_found"],
        "html_report_url": report_data["html_report_url"],
    }


@celery_app.task(name="qa_agent.run_test", bind=True, max_retries=1)
def run_test_task(self, run_id: str, test_case_id: str, base_url: str, nl_description: str, max_steps: int = 30, platform: str = "web", mobile_config: dict = {}, appium_config: dict = {}):
    """Celery task that runs a QA test and persists results."""
    # Update run status to running
    async def _set_running():
        from ..db import get_session
        from ..models import Run, RunStatus
        from sqlalchemy import select
        async with get_session() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = RunStatus.running
                run.started_at = datetime.utcnow()

    asyncio.run(_set_running())

    try:
        result = asyncio.run(
            _run_test(run_id, test_case_id, base_url, nl_description, max_steps, platform, mobile_config, appium_config)
        )
        return result
    except Exception as exc:
        # Mark run as error in DB
        async def _set_error():
            from ..db import get_session
            from ..models import Run, RunStatus
            from sqlalchemy import select
            async with get_session() as session:
                res = await session.execute(select(Run).where(Run.id == run_id))
                run = res.scalar_one_or_none()
                if run:
                    run.status = RunStatus.error
                    run.finished_at = datetime.utcnow()
                    run.error_message = str(exc)
        asyncio.run(_set_error())
        raise
