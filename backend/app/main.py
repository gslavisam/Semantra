from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.mapping import router as mapping_router
from app.api.routes.observability import router as observability_router
from app.api.routes.upload import router as upload_router
from app.core.config import settings
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(mapping_router)
app.include_router(observability_router)
app.include_router(evaluation_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "version": settings.app_version, "status": "ok"}