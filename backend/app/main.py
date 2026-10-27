from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    achievements,
    api_keys,
    challenges,
    classrooms,
    documents,
    leaderboard,
    orgs,
    projects,
    security,
    teams,
    webhooks,
)
from app.core.config import settings
from app.db.session import close_pool
from app.middleware.security_logging import SecurityLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()


app = FastAPI(
    title="AEGIS API",
    description="Multi-tenant SaaS platform API. OpenAPI docs at /docs.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityLoggingMiddleware)

app.include_router(orgs.router)
app.include_router(projects.router)
app.include_router(api_keys.router)
app.include_router(challenges.router)
app.include_router(teams.router)
app.include_router(leaderboard.router)
app.include_router(achievements.router)
app.include_router(classrooms.router)
app.include_router(security.router)
app.include_router(documents.router)
app.include_router(webhooks.router)


@app.get("/healthz", tags=["meta"])
async def healthz():
    return {"status": "ok", "environment": settings.environment}
