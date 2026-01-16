# backend/cyroid/api/system.py
"""
System information API endpoints.

Provides endpoints for retrieving host system information including
architecture details for frontend emulation warnings.
"""
from fastapi import APIRouter

from cyroid.utils.arch import get_system_info, HOST_ARCH, IS_ARM

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
async def system_info():
    """
    Return host system information including architecture.

    Used by frontend to determine if VMs will run natively or emulated.
    No authentication required - this is public system metadata.
    """
    return get_system_info()


@router.get("/health")
async def system_health():
    """
    Detailed health check with architecture info.
    """
    return {
        "status": "healthy",
        "architecture": HOST_ARCH,
        "arm_host": IS_ARM,
    }
