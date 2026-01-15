# backend/cyroid/services/export_service.py
"""
Comprehensive range export/import service.

Supports two modes:
- Online: Lightweight export without Docker images (.zip)
- Offline: Complete export with Docker images for air-gapped deployment (.tar.gz)
"""
import hashlib
import io
import json
import logging
import os
import shutil
import tempfile
import zipfile
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID

import docker
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cyroid.config import get_settings
from cyroid.models.artifact import Artifact, ArtifactPlacement
from cyroid.models.inject import Inject
from cyroid.models.msel import MSEL
from cyroid.models.network import Network
from cyroid.models.range import Range
from cyroid.models.snapshot import Snapshot
from cyroid.models.template import VMTemplate
from cyroid.models.user import User
from cyroid.models.vm import VM
from cyroid.schemas.export import (
    ArtifactExportData,
    ArtifactPlacementExportData,
    DockerImageExportData,
    ExportComponents,
    ExportManifest,
    ExportRequest,
    ImportConflicts,
    ImportOptions,
    ImportResult,
    ImportSummary,
    ImportValidationResult,
    InjectExportData,
    MSELExportData,
    NetworkConflict,
    NetworkExportData,
    RangeExportFull,
    RangeExportMetadata,
    SnapshotExportData,
    TemplateConflict,
    TemplateExportData,
    VMExportData,
)
from cyroid.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)


class ExportService:
    """Service for comprehensive range export/import."""

    def __init__(self):
        self.settings = get_settings()
        self._encryption_key: Optional[bytes] = None

    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key for passwords."""
        if self._encryption_key is None:
            # Derive key from JWT secret for consistency
            key_source = self.settings.jwt_secret_key.encode()
            # Use SHA256 to get 32 bytes, then base64 encode for Fernet
            import base64
            key_hash = hashlib.sha256(key_source).digest()
            self._encryption_key = base64.urlsafe_b64encode(key_hash)
        return self._encryption_key

    def _encrypt_password(self, password: Optional[str]) -> Optional[str]:
        """Encrypt a password for export."""
        if not password:
            return None
        fernet = Fernet(self._get_encryption_key())
        return fernet.encrypt(password.encode()).decode()

    def _decrypt_password(self, encrypted: Optional[str]) -> Optional[str]:
        """Decrypt a password from import."""
        if not encrypted:
            return None
        try:
            fernet = Fernet(self._get_encryption_key())
            return fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            # Return as-is if decryption fails (might be plaintext)
            return encrypted

    # =========================================================================
    # Data Collection Methods
    # =========================================================================

    def _collect_network_data(self, network: Network) -> NetworkExportData:
        """Collect full network configuration."""
        return NetworkExportData(
            name=network.name,
            subnet=network.subnet,
            gateway=network.gateway,
            dns_servers=network.dns_servers,
            isolation_level=network.isolation_level.value,
        )

    def _collect_vm_data(
        self, vm: VM, network_map: Dict[UUID, str], template_map: Dict[UUID, str], encrypt: bool = True
    ) -> VMExportData:
        """Collect all VM fields (30+)."""
        return VMExportData(
            hostname=vm.hostname,
            ip_address=vm.ip_address,
            network_name=network_map.get(vm.network_id, "unknown"),
            template_name=template_map.get(vm.template_id, "unknown"),
            # Compute resources
            cpu=vm.cpu,
            ram_mb=vm.ram_mb,
            disk_gb=vm.disk_gb,
            disk2_gb=vm.disk2_gb,
            disk3_gb=vm.disk3_gb,
            # Windows-specific
            windows_version=vm.windows_version,
            windows_username=vm.windows_username,
            windows_password=self._encrypt_password(vm.windows_password) if encrypt else vm.windows_password,
            iso_url=vm.iso_url,
            iso_path=vm.iso_path,
            display_type=vm.display_type,
            # Linux-specific
            linux_distro=vm.linux_distro,
            linux_username=vm.linux_username,
            linux_password=self._encrypt_password(vm.linux_password) if encrypt else vm.linux_password,
            linux_user_sudo=vm.linux_user_sudo,
            boot_mode=vm.boot_mode,
            disk_type=vm.disk_type,
            # Network
            use_dhcp=vm.use_dhcp,
            gateway=vm.gateway,
            dns_servers=vm.dns_servers,
            # Storage
            enable_shared_folder=vm.enable_shared_folder,
            enable_global_shared=vm.enable_global_shared,
            # Localization
            language=vm.language,
            keyboard=vm.keyboard,
            region=vm.region,
            # Installation
            manual_install=vm.manual_install,
            # UI
            position_x=vm.position_x,
            position_y=vm.position_y,
        )

    def _collect_template_data(self, template: VMTemplate) -> TemplateExportData:
        """Collect full template definition."""
        return TemplateExportData(
            name=template.name,
            description=template.description,
            os_type=template.os_type.value,
            os_variant=template.os_variant,
            base_image=template.base_image,
            vm_type=template.vm_type.value,
            linux_distro=template.linux_distro,
            boot_mode=template.boot_mode,
            disk_type=template.disk_type,
            default_cpu=template.default_cpu,
            default_ram_mb=template.default_ram_mb,
            default_disk_gb=template.default_disk_gb,
            config_script=template.config_script,
            tags=template.tags or [],
            golden_image_path=template.golden_image_path,
            cached_iso_path=template.cached_iso_path,
            is_cached=template.is_cached,
        )

    def _collect_msel_data(self, msel: MSEL, vm_id_to_hostname: Dict[str, str]) -> MSELExportData:
        """Collect MSEL with injects, converting VM IDs to hostnames."""
        injects = []
        for inject in msel.injects:
            # Convert target VM IDs to hostnames
            target_hostnames = []
            if inject.target_vm_ids:
                for vm_id in inject.target_vm_ids:
                    hostname = vm_id_to_hostname.get(str(vm_id))
                    if hostname:
                        target_hostnames.append(hostname)

            injects.append(InjectExportData(
                sequence_number=inject.sequence_number,
                inject_time_minutes=inject.inject_time_minutes,
                title=inject.title,
                description=inject.description,
                target_vm_hostnames=target_hostnames,
                actions=inject.actions or [],
                status=inject.status.value,
            ))

        return MSELExportData(
            name=msel.name,
            content=msel.content,
            injects=injects,
        )

    def _collect_artifact_data(
        self, artifact: Artifact, archive_file_path: str
    ) -> ArtifactExportData:
        """Collect artifact metadata."""
        return ArtifactExportData(
            name=artifact.name,
            description=artifact.description,
            sha256_hash=artifact.sha256_hash,
            file_size=artifact.file_size,
            artifact_type=artifact.artifact_type.value,
            malicious_indicator=artifact.malicious_indicator.value,
            ttps=artifact.ttps or [],
            tags=artifact.tags or [],
            file_path_in_archive=archive_file_path,
        )

    def _collect_placement_data(
        self, placement: ArtifactPlacement, vm_id_to_hostname: Dict[str, str], artifact_hash_map: Dict[UUID, str]
    ) -> Optional[ArtifactPlacementExportData]:
        """Collect artifact placement with portable references."""
        hostname = vm_id_to_hostname.get(str(placement.vm_id))
        artifact_hash = artifact_hash_map.get(placement.artifact_id)
        if not hostname or not artifact_hash:
            return None
        return ArtifactPlacementExportData(
            artifact_sha256=artifact_hash,
            vm_hostname=hostname,
            target_path=placement.target_path,
        )

    def _collect_snapshot_data(
        self, snapshot: Snapshot, vm_id_to_hostname: Dict[str, str]
    ) -> Optional[SnapshotExportData]:
        """Collect snapshot metadata."""
        hostname = vm_id_to_hostname.get(str(snapshot.vm_id))
        if not hostname:
            return None
        return SnapshotExportData(
            name=snapshot.name,
            description=snapshot.description,
            vm_hostname=hostname,
            docker_image_id=snapshot.docker_image_id,
        )

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_range_online(
        self,
        range_id: UUID,
        options: ExportRequest,
        user: User,
        db: Session,
    ) -> Tuple[Path, str]:
        """
        Export range as online package (without Docker images).

        Returns:
            Tuple of (archive_path, filename)
        """
        # Load range with all relationships
        stmt = (
            select(Range)
            .where(Range.id == range_id)
            .options(
                selectinload(Range.networks),
                selectinload(Range.vms).selectinload(VM.template),
                selectinload(Range.vms).selectinload(VM.snapshots),
                selectinload(Range.vms).selectinload(VM.artifact_placements).selectinload(ArtifactPlacement.artifact),
                selectinload(Range.msel).selectinload(MSEL.injects),
            )
        )
        result = db.execute(stmt)
        range_obj = result.scalar_one_or_none()

        if not range_obj:
            raise ValueError(f"Range {range_id} not found")

        # Create temporary directory for export
        temp_dir = tempfile.mkdtemp(prefix="cyroid-export-")
        try:
            export_data = self._build_export_data(
                range_obj=range_obj,
                options=options,
                user=user,
                db=db,
                temp_dir=temp_dir,
                include_images=False,
            )

            # Write main export JSON
            export_json_path = os.path.join(temp_dir, "range.json")
            with open(export_json_path, "w") as f:
                json.dump(export_data.model_dump(mode="json"), f, indent=2, default=str)

            # Create zip archive
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in range_obj.name)
            filename = f"range-export-{safe_name}-{timestamp}.zip"
            archive_path = os.path.join(tempfile.gettempdir(), filename)

            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arcname)

            logger.info(f"Created online export: {archive_path}")
            return Path(archive_path), filename

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def export_range_offline(
        self,
        range_id: UUID,
        options: ExportRequest,
        user: User,
        db: Session,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[Path, str]:
        """
        Export range as offline package (with Docker images).

        This is a long-running operation and should be run as a background task.

        Returns:
            Tuple of (archive_path, filename)
        """
        # Load range with all relationships
        stmt = (
            select(Range)
            .where(Range.id == range_id)
            .options(
                selectinload(Range.networks),
                selectinload(Range.vms).selectinload(VM.template),
                selectinload(Range.vms).selectinload(VM.snapshots),
                selectinload(Range.vms).selectinload(VM.artifact_placements).selectinload(ArtifactPlacement.artifact),
                selectinload(Range.msel).selectinload(MSEL.injects),
            )
        )
        result = db.execute(stmt)
        range_obj = result.scalar_one_or_none()

        if not range_obj:
            raise ValueError(f"Range {range_id} not found")

        # Create temporary directory for export
        temp_dir = tempfile.mkdtemp(prefix="cyroid-export-offline-")
        try:
            if progress_callback:
                progress_callback(5, "Collecting range data...")

            export_data = self._build_export_data(
                range_obj=range_obj,
                options=options,
                user=user,
                db=db,
                temp_dir=temp_dir,
                include_images=True,
                progress_callback=progress_callback,
            )

            if progress_callback:
                progress_callback(60, "Writing export manifest...")

            # Write main export JSON
            export_json_path = os.path.join(temp_dir, "range.json")
            with open(export_json_path, "w") as f:
                json.dump(export_data.model_dump(mode="json"), f, indent=2, default=str)

            if progress_callback:
                progress_callback(70, "Creating archive...")

            # Create tar.gz archive
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in range_obj.name)
            filename = f"range-export-{safe_name}-{timestamp}-offline.tar.gz"
            archive_path = os.path.join(tempfile.gettempdir(), filename)

            with tarfile.open(archive_path, "w:gz") as tf:
                tf.add(temp_dir, arcname=".")

            if progress_callback:
                progress_callback(100, "Export complete")

            logger.info(f"Created offline export: {archive_path}")
            return Path(archive_path), filename

        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _build_export_data(
        self,
        range_obj: Range,
        options: ExportRequest,
        user: User,
        db: Session,
        temp_dir: str,
        include_images: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> RangeExportFull:
        """Build the complete export data structure."""
        # Build lookup maps
        network_map: Dict[UUID, str] = {n.id: n.name for n in range_obj.networks}
        vm_id_to_hostname: Dict[str, str] = {str(vm.id): vm.hostname for vm in range_obj.vms}

        # Collect unique templates
        template_ids = {vm.template_id for vm in range_obj.vms}
        templates_by_id: Dict[UUID, VMTemplate] = {}
        if template_ids and options.include_templates:
            stmt = select(VMTemplate).where(VMTemplate.id.in_(template_ids))
            result = db.execute(stmt)
            templates_by_id = {t.id: t for t in result.scalars()}

        template_map: Dict[UUID, str] = {tid: t.name for tid, t in templates_by_id.items()}

        # Collect networks
        networks = [self._collect_network_data(n) for n in range_obj.networks]

        # Collect VMs
        vms = [
            self._collect_vm_data(vm, network_map, template_map, encrypt=options.encrypt_passwords)
            for vm in range_obj.vms
        ]

        # Collect templates
        templates = [self._collect_template_data(t) for t in templates_by_id.values()] if options.include_templates else []

        # Collect MSEL
        msel_data = None
        if options.include_msel and range_obj.msel:
            msel_data = self._collect_msel_data(range_obj.msel, vm_id_to_hostname)

        # Collect artifacts
        artifacts: List[ArtifactExportData] = []
        placements: List[ArtifactPlacementExportData] = []
        artifact_hash_map: Dict[UUID, str] = {}

        if options.include_artifacts:
            if progress_callback:
                progress_callback(20, "Exporting artifacts...")

            artifacts_dir = os.path.join(temp_dir, "artifacts", "files")
            os.makedirs(artifacts_dir, exist_ok=True)

            # Get all artifact placements for this range's VMs
            seen_artifacts: set = set()
            storage = get_storage_service()

            for vm in range_obj.vms:
                for placement in vm.artifact_placements:
                    artifact = placement.artifact
                    artifact_hash_map[artifact.id] = artifact.sha256_hash

                    # Export artifact file (deduplicated by hash)
                    if artifact.sha256_hash not in seen_artifacts:
                        seen_artifacts.add(artifact.sha256_hash)

                        # Download from MinIO
                        file_data = storage.download_file(artifact.file_path)
                        if file_data:
                            # Store in archive
                            hash_prefix = artifact.sha256_hash[:8]
                            artifact_subdir = os.path.join(artifacts_dir, hash_prefix)
                            os.makedirs(artifact_subdir, exist_ok=True)
                            artifact_filename = os.path.basename(artifact.file_path)
                            artifact_path = os.path.join(artifact_subdir, artifact_filename)
                            with open(artifact_path, "wb") as f:
                                f.write(file_data)

                            archive_path = f"artifacts/files/{hash_prefix}/{artifact_filename}"
                            artifacts.append(self._collect_artifact_data(artifact, archive_path))

                    # Collect placement
                    placement_data = self._collect_placement_data(
                        placement, vm_id_to_hostname, artifact_hash_map
                    )
                    if placement_data:
                        placements.append(placement_data)

        # Collect snapshots
        snapshots: List[SnapshotExportData] = []
        if options.include_snapshots:
            for vm in range_obj.vms:
                for snapshot in vm.snapshots:
                    snapshot_data = self._collect_snapshot_data(snapshot, vm_id_to_hostname)
                    if snapshot_data:
                        snapshots.append(snapshot_data)

        # Export Docker images (offline only)
        docker_images: List[DockerImageExportData] = []
        if include_images and options.include_docker_images:
            if progress_callback:
                progress_callback(30, "Exporting Docker images...")

            docker_images = self._export_docker_images(
                templates_by_id.values(),
                temp_dir,
                progress_callback,
            )

        # Build manifest
        manifest = ExportManifest(
            version="2.0",
            export_type="offline" if include_images else "online",
            created_at=datetime.utcnow(),
            created_by=user.username,
            source_range_id=str(range_obj.id),
            source_range_name=range_obj.name,
            components=ExportComponents(
                networks=True,
                vms=True,
                templates=options.include_templates,
                msel=options.include_msel and range_obj.msel is not None,
                artifacts=options.include_artifacts,
                snapshots=options.include_snapshots,
                docker_images=include_images and options.include_docker_images,
            ),
        )

        return RangeExportFull(
            manifest=manifest,
            range=RangeExportMetadata(
                name=range_obj.name,
                description=range_obj.description,
            ),
            networks=networks,
            vms=vms,
            templates=templates,
            msel=msel_data,
            artifacts=artifacts,
            artifact_placements=placements,
            snapshots=snapshots,
            docker_images=docker_images,
        )

    def _export_docker_images(
        self,
        templates: List[VMTemplate],
        temp_dir: str,
        progress_callback: Optional[callable] = None,
    ) -> List[DockerImageExportData]:
        """Export Docker images as tar files."""
        images_dir = os.path.join(temp_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        docker_client = docker.from_env()
        exported_images: List[DockerImageExportData] = []
        seen_images: set = set()

        # Collect unique base images
        base_images = set()
        for template in templates:
            if template.base_image:
                base_images.add(template.base_image)

        # Always include the VM runtime images
        base_images.add("qemux/qemu:latest")
        base_images.add("dockurr/windows:latest")

        total = len(base_images)
        for idx, image_name in enumerate(base_images):
            if image_name in seen_images:
                continue
            seen_images.add(image_name)

            if progress_callback:
                progress = 30 + int((idx / total) * 25)
                progress_callback(progress, f"Exporting image: {image_name}")

            try:
                # Get image
                image = docker_client.images.get(image_name)

                # Create safe filename
                safe_name = image_name.replace("/", "-").replace(":", "-")
                tar_filename = f"{safe_name}.tar"
                tar_path = os.path.join(images_dir, tar_filename)

                # Save image to tar
                logger.info(f"Saving Docker image: {image_name}")
                with open(tar_path, "wb") as f:
                    for chunk in image.save():
                        f.write(chunk)

                file_size = os.path.getsize(tar_path)
                exported_images.append(DockerImageExportData(
                    image_name=image_name,
                    image_id=image.id,
                    tar_path=f"images/{tar_filename}",
                    size_bytes=file_size,
                ))
                logger.info(f"Exported {image_name}: {file_size / (1024**3):.2f} GB")

            except docker.errors.ImageNotFound:
                logger.warning(f"Image not found locally: {image_name}")
            except Exception as e:
                logger.error(f"Failed to export image {image_name}: {e}")

        return exported_images

    # =========================================================================
    # Import Methods
    # =========================================================================

    def validate_import(
        self,
        archive_path: Path,
        db: Session,
    ) -> ImportValidationResult:
        """
        Validate an import archive and detect conflicts.

        Returns:
            ImportValidationResult with validation status and conflicts
        """
        errors: List[str] = []
        warnings: List[str] = []
        conflicts = ImportConflicts()

        try:
            export_data = self._read_archive(archive_path)
        except Exception as e:
            return ImportValidationResult(
                valid=False,
                errors=[f"Failed to read archive: {str(e)}"],
                warnings=[],
                conflicts=ImportConflicts(),
                summary=ImportSummary(range_name="unknown"),
            )

        # Check range name conflict
        stmt = select(Range).where(Range.name == export_data.range.name)
        result = db.execute(stmt)
        if result.scalar_one_or_none():
            conflicts.name_conflict = True
            warnings.append(f"Range name '{export_data.range.name}' already exists - use name_override")

        # Check template conflicts
        template_names = [t.name for t in export_data.templates]
        if template_names:
            stmt = select(VMTemplate).where(VMTemplate.name.in_(template_names))
            result = db.execute(stmt)
            existing_templates = {t.name: t for t in result.scalars()}

            for template in export_data.templates:
                if template.name in existing_templates:
                    conflicts.template_conflicts.append(TemplateConflict(
                        template_name=template.name,
                        existing_template_id=str(existing_templates[template.name].id),
                    ))

        # Check network subnet conflicts
        for network in export_data.networks:
            # Check if subnet overlaps with any existing network
            stmt = select(Network).where(Network.subnet == network.subnet)
            result = db.execute(stmt)
            for existing in result.scalars():
                conflicts.network_conflicts.append(NetworkConflict(
                    network_name=network.name,
                    subnet=network.subnet,
                    overlapping_range_name=existing.range.name if existing.range else "unknown",
                    overlapping_network_name=existing.name,
                ))

        # Build summary
        summary = ImportSummary(
            range_name=export_data.range.name,
            networks_count=len(export_data.networks),
            vms_count=len(export_data.vms),
            templates_to_create=len(export_data.templates) - len(conflicts.template_conflicts),
            templates_existing=len(conflicts.template_conflicts),
            artifacts_count=len(export_data.artifacts),
            artifact_placements_count=len(export_data.artifact_placements),
            injects_count=len(export_data.msel.injects) if export_data.msel else 0,
        )

        # Determine if valid
        is_valid = len(errors) == 0 and not conflicts.name_conflict

        return ImportValidationResult(
            valid=is_valid,
            errors=errors,
            warnings=warnings,
            conflicts=conflicts,
            summary=summary,
        )

    def import_range(
        self,
        archive_path: Path,
        options: ImportOptions,
        user: User,
        db: Session,
    ) -> ImportResult:
        """
        Import a range from an archive.

        Returns:
            ImportResult with success status and created resources
        """
        errors: List[str] = []
        warnings: List[str] = []

        try:
            export_data = self._read_archive(archive_path)
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"Failed to read archive: {str(e)}"],
            )

        if options.dry_run:
            validation = self.validate_import(archive_path, db)
            return ImportResult(
                success=validation.valid,
                errors=validation.errors,
                warnings=validation.warnings,
            )

        try:
            # Determine range name
            range_name = options.name_override or export_data.range.name

            # Check for name conflict
            stmt = select(Range).where(Range.name == range_name)
            if db.execute(stmt).scalar_one_or_none():
                return ImportResult(
                    success=False,
                    errors=[f"Range name '{range_name}' already exists"],
                )

            # Resolve template conflicts and get template mapping
            template_name_to_id = self._resolve_templates(
                export_data.templates,
                options.template_conflict_action,
                user,
                db,
            )

            # Create the range
            new_range = Range(
                name=range_name,
                description=export_data.range.description,
                created_by=user.id,
            )
            db.add(new_range)
            db.flush()

            # Create networks
            network_name_to_id: Dict[str, UUID] = {}
            for net_data in export_data.networks:
                network = Network(
                    range_id=new_range.id,
                    name=net_data.name,
                    subnet=net_data.subnet,
                    gateway=net_data.gateway,
                    dns_servers=net_data.dns_servers,
                    isolation_level=net_data.isolation_level,
                )
                db.add(network)
                db.flush()
                network_name_to_id[net_data.name] = network.id

            # Create VMs
            vm_hostname_to_id: Dict[str, UUID] = {}
            for vm_data in export_data.vms:
                network_id = network_name_to_id.get(vm_data.network_name)
                template_id = template_name_to_id.get(vm_data.template_name)

                if not network_id:
                    warnings.append(f"VM {vm_data.hostname}: network '{vm_data.network_name}' not found")
                    continue
                if not template_id:
                    warnings.append(f"VM {vm_data.hostname}: template '{vm_data.template_name}' not found")
                    continue

                vm = VM(
                    range_id=new_range.id,
                    network_id=network_id,
                    template_id=template_id,
                    hostname=vm_data.hostname,
                    ip_address=vm_data.ip_address,
                    cpu=vm_data.cpu,
                    ram_mb=vm_data.ram_mb,
                    disk_gb=vm_data.disk_gb,
                    disk2_gb=vm_data.disk2_gb,
                    disk3_gb=vm_data.disk3_gb,
                    # Windows
                    windows_version=vm_data.windows_version,
                    windows_username=vm_data.windows_username,
                    windows_password=self._decrypt_password(vm_data.windows_password),
                    iso_url=vm_data.iso_url,
                    iso_path=vm_data.iso_path,
                    display_type=vm_data.display_type,
                    # Linux
                    linux_distro=vm_data.linux_distro,
                    linux_username=vm_data.linux_username,
                    linux_password=self._decrypt_password(vm_data.linux_password),
                    linux_user_sudo=vm_data.linux_user_sudo,
                    boot_mode=vm_data.boot_mode,
                    disk_type=vm_data.disk_type,
                    # Network
                    use_dhcp=vm_data.use_dhcp,
                    gateway=vm_data.gateway,
                    dns_servers=vm_data.dns_servers,
                    # Storage
                    enable_shared_folder=vm_data.enable_shared_folder,
                    enable_global_shared=vm_data.enable_global_shared,
                    # Localization
                    language=vm_data.language,
                    keyboard=vm_data.keyboard,
                    region=vm_data.region,
                    # Installation
                    manual_install=vm_data.manual_install,
                    # UI
                    position_x=vm_data.position_x,
                    position_y=vm_data.position_y,
                )
                db.add(vm)
                db.flush()
                vm_hostname_to_id[vm_data.hostname] = vm.id

            # Import MSEL if present and not skipped
            injects_created = 0
            if export_data.msel and not options.skip_msel:
                msel = MSEL(
                    range_id=new_range.id,
                    name=export_data.msel.name,
                    content=export_data.msel.content,
                )
                db.add(msel)
                db.flush()

                for inject_data in export_data.msel.injects:
                    # Convert hostnames back to VM IDs
                    target_vm_ids = [
                        str(vm_hostname_to_id[hostname])
                        for hostname in inject_data.target_vm_hostnames
                        if hostname in vm_hostname_to_id
                    ]

                    inject = Inject(
                        msel_id=msel.id,
                        sequence_number=inject_data.sequence_number,
                        inject_time_minutes=inject_data.inject_time_minutes,
                        title=inject_data.title,
                        description=inject_data.description,
                        target_vm_ids=target_vm_ids,
                        actions=inject_data.actions,
                        status=inject_data.status,
                    )
                    db.add(inject)
                    injects_created += 1

            # Import artifacts if present and not skipped
            artifacts_imported = 0
            if export_data.artifacts and not options.skip_artifacts:
                artifacts_imported = self._import_artifacts(
                    export_data,
                    archive_path,
                    vm_hostname_to_id,
                    user,
                    db,
                )

            db.commit()

            return ImportResult(
                success=True,
                range_id=new_range.id,
                range_name=new_range.name,
                networks_created=len(network_name_to_id),
                vms_created=len(vm_hostname_to_id),
                templates_created=sum(1 for _ in template_name_to_id.values()),
                artifacts_imported=artifacts_imported,
                warnings=warnings,
            )

        except Exception as e:
            db.rollback()
            logger.exception("Import failed")
            return ImportResult(
                success=False,
                errors=[f"Import failed: {str(e)}"],
                warnings=warnings,
            )

    def _read_archive(self, archive_path: Path) -> RangeExportFull:
        """Read and parse an export archive."""
        temp_dir = tempfile.mkdtemp(prefix="cyroid-import-")
        try:
            # Detect archive type and extract
            if str(archive_path).endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(temp_dir)
            elif str(archive_path).endswith(".tar.gz") or str(archive_path).endswith(".tgz"):
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(temp_dir)
            else:
                raise ValueError(f"Unsupported archive format: {archive_path}")

            # Read the main export JSON
            export_json_path = os.path.join(temp_dir, "range.json")
            if not os.path.exists(export_json_path):
                raise ValueError("Archive missing range.json")

            with open(export_json_path, "r") as f:
                data = json.load(f)

            return RangeExportFull.model_validate(data)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _resolve_templates(
        self,
        templates: List[TemplateExportData],
        conflict_action: str,
        user: User,
        db: Session,
    ) -> Dict[str, UUID]:
        """
        Resolve template conflicts and return name-to-ID mapping.

        Returns:
            Dict mapping template names to their UUIDs
        """
        template_name_to_id: Dict[str, UUID] = {}

        for template_data in templates:
            # Check if template exists
            stmt = select(VMTemplate).where(VMTemplate.name == template_data.name)
            existing = db.execute(stmt).scalar_one_or_none()

            if existing:
                if conflict_action == "use_existing":
                    template_name_to_id[template_data.name] = existing.id
                elif conflict_action == "create_new":
                    # Create with modified name
                    new_name = f"{template_data.name} (imported)"
                    new_template = self._create_template_from_data(template_data, new_name, user, db)
                    template_name_to_id[template_data.name] = new_template.id
                # skip: don't add to mapping
            else:
                # Create new template
                new_template = self._create_template_from_data(template_data, template_data.name, user, db)
                template_name_to_id[template_data.name] = new_template.id

        return template_name_to_id

    def _create_template_from_data(
        self,
        data: TemplateExportData,
        name: str,
        user: User,
        db: Session,
    ) -> VMTemplate:
        """Create a new template from export data."""
        from cyroid.models.template import OSType, VMType

        template = VMTemplate(
            name=name,
            description=data.description,
            os_type=OSType(data.os_type),
            os_variant=data.os_variant,
            base_image=data.base_image,
            vm_type=VMType(data.vm_type),
            linux_distro=data.linux_distro,
            boot_mode=data.boot_mode,
            disk_type=data.disk_type,
            default_cpu=data.default_cpu,
            default_ram_mb=data.default_ram_mb,
            default_disk_gb=data.default_disk_gb,
            config_script=data.config_script,
            tags=data.tags,
            created_by=user.id,
        )
        db.add(template)
        db.flush()
        return template

    def _import_artifacts(
        self,
        export_data: RangeExportFull,
        archive_path: Path,
        vm_hostname_to_id: Dict[str, UUID],
        user: User,
        db: Session,
    ) -> int:
        """
        Import artifacts and placements from archive.

        Returns:
            Number of artifacts imported
        """
        # Extract archive to temp dir
        temp_dir = tempfile.mkdtemp(prefix="cyroid-import-artifacts-")
        try:
            if str(archive_path).endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(temp_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(temp_dir)

            storage = get_storage_service()
            artifact_hash_to_id: Dict[str, UUID] = {}
            imported_count = 0

            for artifact_data in export_data.artifacts:
                # Check if artifact with same hash already exists
                stmt = select(Artifact).where(Artifact.sha256_hash == artifact_data.sha256_hash)
                existing = db.execute(stmt).scalar_one_or_none()

                if existing:
                    artifact_hash_to_id[artifact_data.sha256_hash] = existing.id
                    continue

                # Read artifact file from archive
                artifact_file_path = os.path.join(temp_dir, artifact_data.file_path_in_archive)
                if not os.path.exists(artifact_file_path):
                    logger.warning(f"Artifact file not found in archive: {artifact_data.file_path_in_archive}")
                    continue

                with open(artifact_file_path, "rb") as f:
                    file_data = f.read()

                # Verify hash
                actual_hash = hashlib.sha256(file_data).hexdigest()
                if actual_hash != artifact_data.sha256_hash:
                    logger.warning(f"Artifact hash mismatch: {artifact_data.name}")
                    continue

                # Upload to MinIO
                object_name = f"artifacts/{artifact_data.sha256_hash[:8]}/{os.path.basename(artifact_file_path)}"
                storage.upload_file(
                    io.BytesIO(file_data),
                    object_name,
                )

                # Create artifact record
                from cyroid.models.artifact import ArtifactType, MaliciousIndicator

                artifact = Artifact(
                    name=artifact_data.name,
                    description=artifact_data.description,
                    file_path=object_name,
                    sha256_hash=artifact_data.sha256_hash,
                    file_size=artifact_data.file_size,
                    artifact_type=ArtifactType(artifact_data.artifact_type),
                    malicious_indicator=MaliciousIndicator(artifact_data.malicious_indicator),
                    ttps=artifact_data.ttps,
                    tags=artifact_data.tags,
                    uploaded_by=user.id,
                )
                db.add(artifact)
                db.flush()
                artifact_hash_to_id[artifact_data.sha256_hash] = artifact.id
                imported_count += 1

            # Create placements
            for placement_data in export_data.artifact_placements:
                artifact_id = artifact_hash_to_id.get(placement_data.artifact_sha256)
                vm_id = vm_hostname_to_id.get(placement_data.vm_hostname)

                if not artifact_id or not vm_id:
                    continue

                placement = ArtifactPlacement(
                    artifact_id=artifact_id,
                    vm_id=vm_id,
                    target_path=placement_data.target_path,
                )
                db.add(placement)

            return imported_count

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def load_docker_images(self, archive_path: Path) -> List[str]:
        """
        Load Docker images from an offline export archive.

        Returns:
            List of loaded image names
        """
        temp_dir = tempfile.mkdtemp(prefix="cyroid-import-images-")
        try:
            # Extract archive
            if str(archive_path).endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(temp_dir)
            else:
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(temp_dir)

            # Read export data
            export_json_path = os.path.join(temp_dir, "range.json")
            with open(export_json_path, "r") as f:
                data = json.load(f)
            export_data = RangeExportFull.model_validate(data)

            if not export_data.docker_images:
                return []

            docker_client = docker.from_env()
            loaded_images: List[str] = []

            for image_data in export_data.docker_images:
                tar_path = os.path.join(temp_dir, image_data.tar_path)
                if not os.path.exists(tar_path):
                    logger.warning(f"Image tar not found: {image_data.tar_path}")
                    continue

                logger.info(f"Loading Docker image: {image_data.image_name}")
                with open(tar_path, "rb") as f:
                    images = docker_client.images.load(f)
                    for img in images:
                        loaded_images.extend(img.tags)

            return loaded_images

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# Singleton instance
_export_service: Optional[ExportService] = None


def get_export_service() -> ExportService:
    """Get the export service singleton."""
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
