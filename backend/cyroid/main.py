# backend/cyroid/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings
from cyroid.api.auth import router as auth_router
from cyroid.api.users import router as users_router
from cyroid.api.templates import router as templates_router
from cyroid.api.ranges import router as ranges_router
from cyroid.api.networks import router as networks_router
from cyroid.api.vms import router as vms_router
from cyroid.api.websocket import router as websocket_router
from cyroid.api.artifacts import router as artifacts_router
from cyroid.api.snapshots import router as snapshots_router
from cyroid.api.events import router as events_router
from cyroid.api.connections import router as connections_router
from cyroid.api.msel import router as msel_router
from cyroid.api.cache import router as cache_router
from cyroid.api.system import router as system_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Cyber Range Orchestrator In Docker",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(ranges_router, prefix="/api/v1")
app.include_router(networks_router, prefix="/api/v1")
app.include_router(vms_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")
app.include_router(artifacts_router, prefix="/api/v1")
app.include_router(snapshots_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(msel_router, prefix="/api/v1")
app.include_router(cache_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}


@app.get("/api/v1/version")
async def get_version():
    """Return application version information."""
    return {
        "version": settings.app_version,
        "commit": settings.git_commit,
        "build_date": settings.build_date,
        "api_version": "v1",
        "app_name": settings.app_name,
    }
