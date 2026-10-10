import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_ORIGIN, ROOT_DIR
from .api import health_router, ingest_router, playlists_router, chat_router
from .services.manifest_service import ManifestService
from .services.qdrant_service import QdrantService
from .utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing YT Reviser Backend Services...")
    # Initialize singleton instances
    ManifestService.get_instance()
    QdrantService.get_instance()
    logger.info("YT Reviser Backend is ready and listening.")
    yield
    logger.info("Shutting down YT Reviser Backend...")

app = FastAPI(
    title="YT Reviser API",
    description="AI-powered YouTube Lecture Revision and Incremental RAG API",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(playlists_router)
app.include_router(chat_router)

# Mount Frontend static files
frontend_dir = ROOT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

