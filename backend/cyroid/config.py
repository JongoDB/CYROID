# backend/cyroid/config.py
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application version
    app_version: str = "0.7.0"
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
