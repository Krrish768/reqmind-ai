"""Create the FastAPI app: API routes under /api and the web page at /.

Run from the repo root:
    uvicorn backend.app.main:app --reload --port 8000
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import (
    analysis,
    auth,
    chat,
    documents,
    export,
    graph,
    health,
    projects,
    requirements,
)
from backend.app.config import FRONTEND_DIR, settings
from backend.app.database import create_tables

ROUTERS = [health, auth, projects, documents, requirements, export, analysis, graph, chat]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create missing tables when the server starts."""
    create_tables()
    yield


def create_app() -> FastAPI:
    """Build the app with all routers and, if present, the frontend."""
    app = FastAPI(title="ReqMind AI", lifespan=lifespan)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])
    for module in ROUTERS:
        app.include_router(module.router, prefix="/api")
    if (FRONTEND_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()
