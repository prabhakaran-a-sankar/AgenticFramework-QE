from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from ...db import get_session
from ...models import TestCase, Project

router = APIRouter(prefix="/projects/{project_id}/tests", tags=["tests"])


class TestCaseCreate(BaseModel):
    title: str
    nl_description: str
    tags: list[str] = []
    max_steps: int = 30


class TestCaseOut(BaseModel):
    id: str
    project_id: str
    title: str
    nl_description: str
    tags: list
    max_steps: int

    class Config:
        from_attributes = True


@router.post("/", response_model=TestCaseOut)
async def create_test(project_id: str, body: TestCaseCreate):
    async with get_session() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        if not result.scalar_one_or_none():
            raise HTTPException(404, "Project not found")
        tc = TestCase(project_id=project_id, **body.model_dump())
        session.add(tc)
        await session.flush()
        await session.refresh(tc)
        return TestCaseOut.model_validate(tc)


@router.get("/", response_model=list[TestCaseOut])
async def list_tests(project_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(TestCase).where(TestCase.project_id == project_id).order_by(TestCase.created_at.desc())
        )
        return [TestCaseOut.model_validate(tc) for tc in result.scalars()]


@router.get("/{test_id}", response_model=TestCaseOut)
async def get_test(project_id: str, test_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(TestCase).where(TestCase.id == test_id, TestCase.project_id == project_id)
        )
        tc = result.scalar_one_or_none()
        if not tc:
            raise HTTPException(404, "Test case not found")
        return TestCaseOut.model_validate(tc)


@router.delete("/{test_id}")
async def delete_test(project_id: str, test_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(TestCase).where(TestCase.id == test_id, TestCase.project_id == project_id)
        )
        tc = result.scalar_one_or_none()
        if not tc:
            raise HTTPException(404, "Test case not found")
        await session.delete(tc)
    return {"deleted": test_id}
