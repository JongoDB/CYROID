"""Pre-deployment validation for ranges.

This service validates range configurations before deployment to catch
potential issues early:
- Image availability (Docker images for templates and snapshots)
- Architecture compatibility (ARM64 host running x86 VMs with emulation warning)
- Disk space requirements
- Network configuration (duplicate IPs within same network)
"""

import logging
import os
import platform
import shutil
from typing import List, Optional
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from cyroid.models import Range, VMTemplate
from cyroid.models.vm import VM
from cyroid.models.template import VMType
from cyroid.models.network import Network
from cyroid.models.snapshot import Snapshot
from cyroid.services.docker_service import DockerService
from cyroid.utils.arch import HOST_ARCH, requires_emulation
from cyroid.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    message: str
    severity: str = "error"  # error, warning, info
    vm_id: Optional[str] = None
    details: Optional[dict] = field(default_factory=dict)


@dataclass
class DeploymentValidation:
    """Complete deployment validation result."""
    valid: bool
    results: List[ValidationResult]

    @property
    def errors(self) -> List[ValidationResult]:
        """Get all error-level validation failures."""
        return [r for r in self.results if r.severity == "error" and not r.valid]

    @property
    def warnings(self) -> List[ValidationResult]:
        """Get all warning-level validation issues."""
        return [r for r in self.results if r.severity == "warning"]

    @property
    def info(self) -> List[ValidationResult]:
        """Get all info-level validation notes."""
        return [r for r in self.results if r.severity == "info"]


class DeploymentValidator:
    """Validates range configuration before deployment.

    Performs the following checks:
    1. Image existence: Verifies Docker images exist for all VMs
    2. Architecture compatibility: Checks for cross-architecture emulation needs
    3. Disk space: Verifies sufficient disk space for deployment
    4. Network configuration: Validates no duplicate IPs within networks
    """

    # Minimum disk space buffer (20% of estimated requirement)
    DISK_BUFFER_PERCENT = 0.20

    # Minimum disk space required (in GB) regardless of VMs
    MIN_DISK_GB = 10

    # Docker data directory (default, can be overridden)
    DOCKER_DATA_DIR = "/var/lib/docker"

    def __init__(self, db: Session, docker_service: DockerService):
        """Initialize the deployment validator.

        Args:
            db: SQLAlchemy database session
            docker_service: Docker service instance for image checks
        """
        self.db = db
        self.docker = docker_service

    async def validate_range(self, range_id: UUID) -> DeploymentValidation:
        """Run all validation checks for a range.

        Args:
            range_id: UUID of the range to validate

        Returns:
            DeploymentValidation with all results
        """
        results = []

        # Fetch the range with eager loading of relationships
        db_range = self.db.query(Range).filter(Range.id == range_id).first()
        if not db_range:
            return DeploymentValidation(
                valid=False,
                results=[ValidationResult(False, "Range not found", "error")]
            )

        # Get VMs and networks for this range
        vms = self.db.query(VM).filter(VM.range_id == range_id).all()
        networks = self.db.query(Network).filter(Network.range_id == range_id).all()

        # Run all validators
        results.extend(await self._validate_images_exist(vms))
        results.extend(self._validate_architecture(vms))
        results.extend(self._validate_disk_space(vms))
        results.extend(self._validate_network_config(vms, networks))

        # Determine overall validity - only errors make it invalid
        valid = all(r.valid for r in results if r.severity == "error")

        return DeploymentValidation(valid=valid, results=results)

    async def _validate_images_exist(self, vms: List[VM]) -> List[ValidationResult]:
        """Strictly validate that all required images/ISOs exist before deployment.

        For container VMs: Docker image must be in local cache
        For QEMU VMs (Windows/Linux): boot_source must be set and resources must exist
        For snapshot VMs: Snapshot Docker image must exist

        Args:
            vms: List of VMs to validate

        Returns:
            List of validation results
        """
        results = []
        settings = get_settings()

        if not vms:
            results.append(ValidationResult(
                valid=True,
                message="No VMs to validate",
                severity="info"
            ))
            return results

        for vm in vms:
            # Snapshot-based VM
            if vm.snapshot_id:
                result = self._validate_snapshot_vm(vm)
                results.append(result)
                continue

            # Template-based VM
            if vm.template_id:
                template = self.db.query(VMTemplate).filter(
                    VMTemplate.id == vm.template_id
                ).first()
                if not template:
                    results.append(ValidationResult(
                        valid=False,
                        message=f"VM '{vm.hostname}': Template not found",
                        severity="error",
                        vm_id=str(vm.id)
                    ))
                    continue

                # Validate based on VM type
                vm_type = template.vm_type
                if vm_type == VMType.CONTAINER:
                    result = self._validate_container_vm(vm, template)
                elif vm_type == VMType.WINDOWS_VM:
                    result = self._validate_windows_vm(vm, template, settings)
                elif vm_type == VMType.LINUX_VM:
                    result = self._validate_linux_vm(vm, template, settings)
                else:
                    result = ValidationResult(
                        valid=False,
                        message=f"VM '{vm.hostname}': Unknown VM type '{vm_type}'",
                        severity="error",
                        vm_id=str(vm.id)
                    )
                results.append(result)
            else:
                results.append(ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': No template or snapshot specified",
                    severity="error",
                    vm_id=str(vm.id)
                ))

        return results

    def _check_image_exists(self, image: str) -> bool:
        """Check if a Docker image exists locally.

        Args:
            image: Docker image name/tag/id

        Returns:
            True if image exists, False otherwise
        """
        try:
            self.docker.client.images.get(image)
            return True
        except Exception:
            return False

    def _validate_snapshot_vm(self, vm: VM) -> ValidationResult:
        """Validate a snapshot-based VM."""
        snapshot = self.db.query(Snapshot).filter(
            Snapshot.id == vm.snapshot_id
        ).first()
        if not snapshot:
            return ValidationResult(
                valid=False,
                message=f"VM '{vm.hostname}': Snapshot not found",
                severity="error",
                vm_id=str(vm.id)
            )

        image_tag = snapshot.docker_image_tag or snapshot.docker_image_id
        if image_tag and self._check_image_exists(image_tag):
            return ValidationResult(
                valid=True,
                message=f"VM '{vm.hostname}': Snapshot image '{image_tag}' available",
                severity="info",
                vm_id=str(vm.id)
            )
        else:
            return ValidationResult(
                valid=False,
                message=f"VM '{vm.hostname}': Snapshot image '{image_tag}' not found in Docker cache",
                severity="error",
                vm_id=str(vm.id)
            )

    def _validate_container_vm(self, vm: VM, template: VMTemplate) -> ValidationResult:
        """Validate a container-based VM (must have Docker image cached)."""
        base_image = template.base_image
        if not base_image:
            return ValidationResult(
                valid=False,
                message=f"VM '{vm.hostname}': Template has no base_image configured",
                severity="error",
                vm_id=str(vm.id)
            )

        if self._check_image_exists(base_image):
            return ValidationResult(
                valid=True,
                message=f"VM '{vm.hostname}': Docker image '{base_image}' available",
                severity="info",
                vm_id=str(vm.id)
            )
        else:
            return ValidationResult(
                valid=False,
                message=f"VM '{vm.hostname}': Docker image '{base_image}' not found. Pre-pull via Image Cache page.",
                severity="error",
                vm_id=str(vm.id)
            )

    def _validate_windows_vm(self, vm: VM, template: VMTemplate, settings) -> ValidationResult:
        """Validate Windows VM has required resources based on boot_source."""
        windows_version = vm.windows_version or template.base_image or "11"
        # Extract version if base_image is like "dockur/windows:2022"
        if ":" in windows_version:
            windows_version = windows_version.split(":")[-1]
        if "/" in windows_version:
            windows_version = "11"  # Default if can't parse

        boot_source = vm.boot_source

        # Check what's available
        golden_path = template.golden_image_path
        has_golden = golden_path and os.path.exists(golden_path)

        iso_path = os.path.join(settings.iso_cache_dir, "windows-isos", f"windows-{windows_version}.iso")
        has_custom_iso = vm.iso_path and os.path.isfile(vm.iso_path)
        has_cached_iso = os.path.isfile(iso_path)
        has_iso = has_custom_iso or has_cached_iso

        # If boot_source not specified, return error with suggestions
        if not boot_source:
            available = []
            if has_golden:
                available.append("golden_image")
            if has_iso:
                available.append("fresh_install")

            if available:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': boot_source not specified. Select from: {', '.join(available)}",
                    severity="error",
                    vm_id=str(vm.id),
                    details={"available": available, "vm_type": "windows"}
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': No golden image or ISO found for Windows {windows_version}. Cache via Image Cache page.",
                    severity="error",
                    vm_id=str(vm.id),
                    details={"available": [], "vm_type": "windows"}
                )

        if boot_source == "golden_image":
            if has_golden:
                return ValidationResult(
                    valid=True,
                    message=f"VM '{vm.hostname}': Golden image available at {golden_path}",
                    severity="info",
                    vm_id=str(vm.id)
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': Golden image not found. Create via Image Cache > Snapshots.",
                    severity="error",
                    vm_id=str(vm.id)
                )

        elif boot_source == "fresh_install":
            if has_custom_iso:
                return ValidationResult(
                    valid=True,
                    message=f"VM '{vm.hostname}': Custom ISO available at {vm.iso_path}",
                    severity="info",
                    vm_id=str(vm.id)
                )
            elif has_cached_iso:
                return ValidationResult(
                    valid=True,
                    message=f"VM '{vm.hostname}': Cached ISO available for Windows {windows_version}",
                    severity="info",
                    vm_id=str(vm.id)
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': ISO not found for Windows {windows_version}. Download via Image Cache > Windows ISOs.",
                    severity="error",
                    vm_id=str(vm.id)
                )

        return ValidationResult(
            valid=False,
            message=f"VM '{vm.hostname}': Invalid boot_source '{boot_source}'",
            severity="error",
            vm_id=str(vm.id)
        )

    def _validate_linux_vm(self, vm: VM, template: VMTemplate, settings) -> ValidationResult:
        """Validate Linux VM (qemux/qemu) has required resources based on boot_source."""
        linux_distro = vm.linux_distro or template.linux_distro or "ubuntu"
        boot_source = vm.boot_source

        # Check what's available
        golden_path = template.golden_image_path
        has_golden = golden_path and os.path.exists(golden_path)

        iso_path = os.path.join(settings.iso_cache_dir, "linux-isos", f"{linux_distro}.iso")
        has_custom_iso = vm.iso_path and os.path.isfile(vm.iso_path)
        has_cached_iso = os.path.isfile(iso_path)
        has_iso = has_custom_iso or has_cached_iso

        # If boot_source not specified, return error with suggestions
        if not boot_source:
            available = []
            if has_golden:
                available.append("golden_image")
            if has_iso:
                available.append("fresh_install")

            if available:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': boot_source not specified. Select from: {', '.join(available)}",
                    severity="error",
                    vm_id=str(vm.id),
                    details={"available": available, "vm_type": "linux"}
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': No golden image or ISO found for Linux {linux_distro}. Cache via Image Cache page.",
                    severity="error",
                    vm_id=str(vm.id),
                    details={"available": [], "vm_type": "linux"}
                )

        if boot_source == "golden_image":
            if has_golden:
                return ValidationResult(
                    valid=True,
                    message=f"VM '{vm.hostname}': Golden image available at {golden_path}",
                    severity="info",
                    vm_id=str(vm.id)
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': Golden image not found for {linux_distro}. Create via Image Cache > Snapshots.",
                    severity="error",
                    vm_id=str(vm.id)
                )

        elif boot_source == "fresh_install":
            if has_custom_iso:
                return ValidationResult(
                    valid=True,
                    message=f"VM '{vm.hostname}': Custom ISO available at {vm.iso_path}",
                    severity="info",
                    vm_id=str(vm.id)
                )
            elif has_cached_iso:
                return ValidationResult(
                    valid=True,
                    message=f"VM '{vm.hostname}': Cached ISO available for {linux_distro}",
                    severity="info",
                    vm_id=str(vm.id)
                )
            else:
                return ValidationResult(
                    valid=False,
                    message=f"VM '{vm.hostname}': ISO not found for {linux_distro}. Download via Image Cache > Linux ISOs.",
                    severity="error",
                    vm_id=str(vm.id)
                )

        return ValidationResult(
            valid=False,
            message=f"VM '{vm.hostname}': Invalid boot_source '{boot_source}'",
            severity="error",
            vm_id=str(vm.id)
        )

    def _validate_architecture(self, vms: List[VM]) -> List[ValidationResult]:
        """Check architecture compatibility for VMs.

        ARM64 hosts can run x86_64 VMs through QEMU emulation, but with
        a significant performance penalty. This check warns users about this.

        Args:
            vms: List of VMs to validate

        Returns:
            List of validation results
        """
        results = []

        if not vms:
            return results

        emulated_vms = []

        for vm in vms:
            # Determine target architecture
            target_arch = "x86_64"  # Default

            if vm.template_id:
                template = self.db.query(VMTemplate).filter(
                    VMTemplate.id == vm.template_id
                ).first()
                if template:
                    target_arch = template.native_arch or "x86_64"

            # Check if emulation is required
            if requires_emulation(target_arch):
                emulated_vms.append((vm, target_arch))

        if emulated_vms:
            vm_list = ", ".join([f"'{vm.hostname}'" for vm, _ in emulated_vms])
            results.append(ValidationResult(
                valid=True,  # Still valid, just a warning
                message=f"Architecture emulation required: {len(emulated_vms)} VM(s) targeting x86_64 will run with QEMU emulation on {HOST_ARCH} host ({vm_list}). Expect reduced performance.",
                severity="warning",
                details={
                    "host_arch": HOST_ARCH,
                    "emulated_vms": [str(vm.id) for vm, _ in emulated_vms]
                }
            ))
        else:
            results.append(ValidationResult(
                valid=True,
                message=f"All VMs are compatible with host architecture ({HOST_ARCH})",
                severity="info"
            ))

        return results

    def _validate_disk_space(self, vms: List[VM]) -> List[ValidationResult]:
        """Check available disk space for deployment.

        Calculates estimated disk requirements based on VM disk sizes
        and checks against available space in Docker data directory.

        Args:
            vms: List of VMs to validate

        Returns:
            List of validation results
        """
        results = []

        # Calculate estimated disk requirements
        total_disk_gb = sum(vm.disk_gb for vm in vms)

        # Add 20% buffer
        required_gb = max(
            total_disk_gb * (1 + self.DISK_BUFFER_PERCENT),
            self.MIN_DISK_GB
        )

        # Get available disk space
        try:
            # Try Docker data directory first
            docker_data_path = self.DOCKER_DATA_DIR

            # Check if custom Docker root is configured
            try:
                info = self.docker.client.info()
                docker_root = info.get("DockerRootDir")
                if docker_root:
                    docker_data_path = docker_root
            except Exception:
                pass

            # Get disk usage
            disk_usage = shutil.disk_usage(docker_data_path)
            available_gb = disk_usage.free / (1024 ** 3)
            total_gb = disk_usage.total / (1024 ** 3)

            if available_gb >= required_gb:
                results.append(ValidationResult(
                    valid=True,
                    message=f"Sufficient disk space: {available_gb:.1f} GB available, {required_gb:.1f} GB required (including 20% buffer)",
                    severity="info",
                    details={
                        "available_gb": round(available_gb, 1),
                        "required_gb": round(required_gb, 1),
                        "total_gb": round(total_gb, 1),
                        "docker_path": docker_data_path
                    }
                ))
            else:
                results.append(ValidationResult(
                    valid=False,
                    message=f"Insufficient disk space: {available_gb:.1f} GB available, but {required_gb:.1f} GB required (including 20% buffer)",
                    severity="error",
                    details={
                        "available_gb": round(available_gb, 1),
                        "required_gb": round(required_gb, 1),
                        "total_gb": round(total_gb, 1),
                        "docker_path": docker_data_path
                    }
                ))

        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            results.append(ValidationResult(
                valid=True,  # Don't fail on inability to check
                message=f"Could not verify disk space (estimated {required_gb:.1f} GB required): {str(e)}",
                severity="warning"
            ))

        return results

    def _validate_network_config(
        self,
        vms: List[VM],
        networks: List[Network]
    ) -> List[ValidationResult]:
        """Validate network configuration.

        Checks for:
        - Duplicate IP addresses within the same network
        - Valid IP addresses within network subnet

        Args:
            vms: List of VMs to validate
            networks: List of networks in the range

        Returns:
            List of validation results
        """
        results = []

        if not vms or not networks:
            results.append(ValidationResult(
                valid=True,
                message="No network configuration to validate",
                severity="info"
            ))
            return results

        # Build network lookup
        network_map = {n.id: n for n in networks}

        # Group VMs by network
        vms_by_network = {}
        for vm in vms:
            if vm.network_id not in vms_by_network:
                vms_by_network[vm.network_id] = []
            vms_by_network[vm.network_id].append(vm)

        # Check for duplicate IPs within each network
        for network_id, network_vms in vms_by_network.items():
            network = network_map.get(network_id)
            if not network:
                results.append(ValidationResult(
                    valid=False,
                    message=f"VMs reference unknown network ID {network_id}",
                    severity="error"
                ))
                continue

            # Collect IPs and check for duplicates
            ip_to_vms = {}
            for vm in network_vms:
                ip = vm.ip_address
                if ip in ip_to_vms:
                    ip_to_vms[ip].append(vm)
                else:
                    ip_to_vms[ip] = [vm]

            # Report duplicates
            for ip, vms_with_ip in ip_to_vms.items():
                if len(vms_with_ip) > 1:
                    hostnames = ", ".join([f"'{vm.hostname}'" for vm in vms_with_ip])
                    results.append(ValidationResult(
                        valid=False,
                        message=f"Duplicate IP address {ip} on network '{network.name}': {hostnames}",
                        severity="error",
                        details={
                            "network_id": str(network_id),
                            "network_name": network.name,
                            "ip_address": ip,
                            "vm_ids": [str(vm.id) for vm in vms_with_ip]
                        }
                    ))

            # Validate IPs are within subnet
            try:
                import ipaddress
                network_obj = ipaddress.ip_network(network.subnet, strict=False)

                for vm in network_vms:
                    try:
                        vm_ip = ipaddress.ip_address(vm.ip_address)
                        if vm_ip not in network_obj:
                            results.append(ValidationResult(
                                valid=False,
                                message=f"VM '{vm.hostname}' IP {vm.ip_address} is outside network '{network.name}' subnet {network.subnet}",
                                severity="error",
                                vm_id=str(vm.id)
                            ))
                    except ValueError as e:
                        results.append(ValidationResult(
                            valid=False,
                            message=f"VM '{vm.hostname}' has invalid IP address: {vm.ip_address}",
                            severity="error",
                            vm_id=str(vm.id)
                        ))

            except ValueError as e:
                results.append(ValidationResult(
                    valid=False,
                    message=f"Network '{network.name}' has invalid subnet: {network.subnet}",
                    severity="error"
                ))

        if not any(r.severity == "error" for r in results):
            results.append(ValidationResult(
                valid=True,
                message=f"Network configuration valid: {len(vms)} VMs across {len(networks)} networks",
                severity="info"
            ))

        return results
