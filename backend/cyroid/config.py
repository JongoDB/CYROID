# backend/cyroid/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
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
    vyos_image: str = "2stacks/vyos:latest"
    management_network_name: str = "cyroid-management"
    management_network_subnet: str = "10.10.0.0/16"
    management_network_gateway: str = "10.10.0.1"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
