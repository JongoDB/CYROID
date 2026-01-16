# backend/cyroid/utils/arch.py
"""
Architecture detection utilities for multi-platform support.

Provides detection of host CPU architecture and emulation requirements
for running x86 VMs on ARM hosts and vice versa.
"""
import platform
from typing import Literal

# Detect host architecture
_machine = platform.machine().lower()

IS_ARM: bool = _machine in ('arm64', 'aarch64')
IS_X86: bool = _machine in ('x86_64', 'amd64', 'x86')
HOST_ARCH: Literal['arm64', 'x86_64'] = 'arm64' if IS_ARM else 'x86_64'


def requires_emulation(target_arch: str) -> bool:
    """
    Check if running a target architecture requires emulation on this host.

    Args:
        target_arch: Target architecture ('x86_64', 'arm64', etc.)

    Returns:
        True if emulation is required, False if native execution
    """
    target = target_arch.lower()
    if target in ('x86_64', 'amd64', 'x86'):
        return IS_ARM
    if target in ('arm64', 'aarch64'):
        return IS_X86
    # Unknown architecture, assume no emulation needed
    return False


def get_system_info() -> dict:
    """
    Return system architecture information for API responses.

    Returns:
        Dictionary with host architecture details
    """
    return {
        "host_arch": HOST_ARCH,
        "is_arm": IS_ARM,
        "is_x86": IS_X86,
        "emulation_available": True,  # QEMU available via Docker
        "platform": platform.system().lower(),
        "machine": platform.machine(),
    }
