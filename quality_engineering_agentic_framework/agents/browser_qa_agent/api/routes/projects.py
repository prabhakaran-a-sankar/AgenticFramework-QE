from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from ...db import get_session
from ...models import Project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    base_url: str
    description: str = ""
    config: dict = {}


class ProjectOut(BaseModel):
    id: str
    name: str
    base_url: str
    description: str
    config: dict

    class Config:
        from_attributes = True


@router.post("/", response_model=ProjectOut)
async def create_project(body: ProjectCreate):
    async with get_session() as session:
        project = Project(**body.model_dump())
        session.add(project)
        await session.flush()
        await session.refresh(project)
        return ProjectOut.model_validate(project)


@router.get("/", response_model=list[ProjectOut])
async def list_projects():
    async with get_session() as session:
        result = await session.execute(select(Project).order_by(Project.created_at.desc()))
        return [ProjectOut.model_validate(p) for p in result.scalars()]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str):
    async with get_session() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(404, "Project not found")
        return ProjectOut.model_validate(project)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    async with get_session() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(404, "Project not found")
        await session.delete(project)
    return {"deleted": project_id}
