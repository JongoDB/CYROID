# backend/cyroid/config.py
import os
import subprocess
from pydantic_settings import BaseSettings
from functools import lru_cache


def _get_version() -> str:
    """Get version from VERSION file, env var, git tag, or fallback to 'dev'."""
    # First check environment variable (for Docker builds)
    if version := os.environ.get("APP_VERSION"):
        return version

    # Try VERSION file (works in Docker with volume mounts)
    version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    try:
        with open(version_file) as f:
            if version := f.read().strip():
                return version
    except (FileNotFoundError, IOError):
        pass

    # Try git tag (works in local dev without Docker)
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
    # Application version (from VERSION file, APP_VERSION env, git tag, or "dev")
    app_version: str = _get_version()
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

    # === DinD (Docker-in-Docker) Configuration ===
    # Each range runs in its own DinD container for network isolation
    dind_image: str = "docker:24-dind"
    dind_startup_timeout: int = 60  # Seconds to wait for inner Docker daemon
    dind_docker_port: int = 2375  # Docker daemon port inside DinD

    # === Network Configuration ===
    # Management network for CYROID infrastructure services
    cyroid_mgmt_network: str = "cyroid-mgmt"
    cyroid_mgmt_subnet: str = "172.30.0.0/24"

    # Network for range DinD containers (ranges connect here)
    cyroid_ranges_network: str = "cyroid-ranges"
    cyroid_ranges_subnet: str = "172.30.1.0/24"

    # === Range Defaults ===
    range_default_memory: str = "8g"  # Default memory limit for range DinD
    range_default_cpu: float = 4.0  # Default CPU limit for range DinD

    # === DinD Isolation ===
    # All ranges deploy inside DinD containers for complete IP isolation
    # This allows multiple ranges to use identical IP spaces without conflicts

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
