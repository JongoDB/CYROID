# backend/cyroid/models/vm_enums.py
"""
VM type and OS type enums.

VMs are created from:
- BaseImage (containers or ISOs from VM Library)
- GoldenImage (pre-configured snapshots or imports)
- Snapshot (point-in-time forks)
"""
from enum import Enum


class OSType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"  # macOS via dockur/macos
    NETWORK = "network"  # For network devices (VyOS, OPNsense, pfSense, etc.)
    CUSTOM = "custom"  # For custom ISOs


class VMType(str, Enum):
    """Type of VM/container implementation."""
    CONTAINER = "container"      # Basic Docker container (lightweight Linux)
    LINUX_VM = "linux_vm"        # Full Linux VM via qemux/qemu
    WINDOWS_VM = "windows_vm"    # Full Windows VM via dockur/windows
    MACOS_VM = "macos_vm"        # Full macOS VM via dockur/macos


class LinuxDistro(str, Enum):
    """Supported Linux distributions for qemux/qemu VMs.

    These are auto-downloaded by qemux/qemu when specified in the BOOT env var.
    See: https://github.com/qemux/qemu
    """
    # Popular desktop distributions
    UBUNTU = "ubuntu"            # ~2.5 GB
    DEBIAN = "debian"            # ~600 MB
    FEDORA = "fedora"            # ~2.0 GB
    ALPINE = "alpine"            # ~60 MB (minimal)
    ARCH = "arch"                # ~800 MB
    MANJARO = "manjaro"          # ~2.5 GB
    OPENSUSE = "opensuse"        # ~800 MB
    MINT = "mint"                # ~2.5 GB
    ZORIN = "zorin"              # ~4.5 GB
    ELEMENTARY = "elementary"    # ~2.5 GB
    POPOS = "popos"              # ~2.5 GB

    # Security-focused distributions (for cyber range training)
    KALI = "kali"                # ~3.5 GB - Penetration testing
    PARROT = "parrot"            # ~5.0 GB - Security/forensics
    TAILS = "tails"              # ~1.3 GB - Privacy-focused

    # Enterprise/server distributions
    ROCKY = "rocky"              # ~1.5 GB - RHEL compatible
    ALMA = "alma"                # ~1.5 GB - RHEL compatible

    # Custom ISO (use iso_url instead)
    CUSTOM = "custom"
