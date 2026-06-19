from contextlib import asynccontextmanager
from fastapi import FastAPI
from .routes import projects_router, tests_router, runs_router, reports_router, webhooks_router
from ..db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="QA Browser Agent",
    description="AI-powered QA testing agent — open source alternative to Tester Army",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(projects_router, prefix="/api/v1")
app.include_router(tests_router, prefix="/api/v1")
app.include_router(runs_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
