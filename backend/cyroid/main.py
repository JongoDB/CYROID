# backend/cyroid/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings
from cyroid.api.auth import router as auth_router
from cyroid.api.templates import router as templates_router
from cyroid.api.ranges import router as ranges_router
from cyroid.api.networks import router as networks_router
from cyroid.api.vms import router as vms_router
from cyroid.api.websocket import router as websocket_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Cyber Range Orchestrator In Docker",
    version="0.1.0",
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
app.include_router(templates_router, prefix="/api/v1")
app.include_router(ranges_router, prefix="/api/v1")
app.include_router(networks_router, prefix="/api/v1")
app.include_router(vms_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
