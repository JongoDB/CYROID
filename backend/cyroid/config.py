# backend/cyroid/config.py
import os
import subprocess
from pydantic_settings import BaseSettings
from functools import lru_cache


def _get_version_from_git() -> str:
    """Get version from git tag, env var, or fallback to 'dev'."""
    # First check environment variable (for Docker builds)
    if version := os.environ.get("APP_VERSION"):
        return version

    # Try to get from git tag
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            tag = result.stdout.strip()
            # Strip 'v' prefix if present (v0.9.0 -> 0.9.0)
            return tag.lstrip("v")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return "dev"


class Settings(BaseSettings):
    # Application version (from git tag, APP_VERSION env, or "dev")
    app_version: str = _get_version_from_git()
    git_commit: str = os.environ.get("GIT_COMMIT", "dev")
    build_date: str = os.environ.get("BUILD_DATE", "")

    # Database
    database_url: str = "postgresql://cyroid:cyroid@db:5432/cyroid"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "cyroid"
    minio_secret_key: str = "cyroid123"
    minio_bucket: str = "cyroid-artifacts"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # App
    app_name: str = "CYROID"
    debug: bool = True

    # Image/ISO Cache
    iso_cache_dir: str = "/data/cyroid/iso-cache"
    template_storage_dir: str = "/data/cyroid/template-storage"

    # VM Storage
    vm_storage_dir: str = "/data/cyroid/vm-storage"
    global_shared_dir: str = "/data/cyroid/shared"

    # VyOS Router Configuration
    vyos_image: str = "2stacks/vyos:1.2.0-rc11"
    management_network_name: str = "cyroid-management"
    management_network_subnet: str = "10.0.0.0/16"
    management_network_gateway: str = "10.0.0.1"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
