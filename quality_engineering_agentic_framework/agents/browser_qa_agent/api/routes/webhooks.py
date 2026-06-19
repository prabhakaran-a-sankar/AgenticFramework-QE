import json
from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ...db import get_session
from ...models import Run, RunStatus, TestCase
from ...workers import run_test_task
from ...integrations.github import GitHubIntegration

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
github = GitHubIntegration()


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    body = await request.body()

    if not github.verify_webhook_signature(body, x_hub_signature_256):
        raise HTTPException(401, "Invalid signature")

    if x_github_event not in ("pull_request",):
        return {"status": "ignored"}

    payload = json.loads(body)
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored"}

    installation_id = payload["installation"]["id"]
    repo = payload["repository"]
    owner = repo["owner"]["login"]
    repo_name = repo["name"]
    head_sha = payload["pull_request"]["head"]["sha"]
    branch = payload["pull_request"]["head"]["ref"]

    # Find projects whose base_url matches this repo (by convention store repo full_name in config)
    async with get_session() as session:
        from ...models import Project
        result = await session.execute(select(Project))
        projects = result.scalars().all()
        matched = [p for p in projects if p.config.get("github_repo") == f"{owner}/{repo_name}"]

    queued = []
    for project in matched:
        async with get_session() as session:
            tc_result = await session.execute(
                select(TestCase).options(selectinload(TestCase.project)).where(TestCase.project_id == project.id)
            )
            test_cases = tc_result.scalars().all()

        for tc in test_cases:
            # Create check run
            check_run_id = await github.create_check_run(installation_id, owner, repo_name, head_sha, name=tc.title)

            async with get_session() as session:
                run = Run(
                    test_case_id=tc.id,
                    status=RunStatus.queued,
                    triggered_by="github",
                    branch=branch,
                    commit_sha=head_sha,
                )
                session.add(run)
                await session.flush()
                run_id = run.id

            run_test_task.delay(
                run_id=run_id,
                test_case_id=tc.id,
                base_url=project.base_url,
                nl_description=tc.nl_description,
                max_steps=tc.max_steps,
            )
            queued.append({"run_id": run_id, "test": tc.title, "check_run_id": check_run_id})

    return {"queued": queued}


@router.post("/trigger")
async def generic_trigger(request: Request):
    """Generic inbound webhook to trigger all tests for a project."""
    payload = await request.json()
    project_id = payload.get("project_id")
    if not project_id:
        raise HTTPException(400, "project_id required")

    async with get_session() as session:
        tc_result = await session.execute(
            select(TestCase).options(selectinload(TestCase.project)).where(TestCase.project_id == project_id)
        )
        test_cases = tc_result.scalars().all()

    queued = []
    for tc in test_cases:
        async with get_session() as session:
            run = Run(test_case_id=tc.id, status=RunStatus.queued, triggered_by="webhook")
            session.add(run)
            await session.flush()
            run_id = run.id

        run_test_task.delay(
            run_id=run_id,
            test_case_id=tc.id,
            base_url=tc.project.base_url,
            nl_description=tc.nl_description,
            max_steps=tc.max_steps,
        )
        queued.append(run_id)

    return {"queued": queued}
