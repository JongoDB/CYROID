# backend/cyroid/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings

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


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
