# backend/cyroid/services/image_import_service.py
"""Service for importing VM images (OVA, QCOW2, VMDK, VDI) as GoldenImages."""
import asyncio
import logging
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from cyroid.config import get_settings
from cyroid.models.golden_image import GoldenImage

logger = logging.getLogger(__name__)
settings = get_settings()


class ImageImportService:
    """Service for importing VM disk images as GoldenImages."""

    SUPPORTED_FORMATS = {'.ova', '.qcow2', '.vmdk', '.vdi'}
    GOLDEN_IMAGES_DIR = Path(os.environ.get('TEMPLATE_STORAGE_DIR', '/data/cyroid/template-storage')) / 'golden-images'

    def __init__(self):
        """Initialize the import service."""
        self.GOLDEN_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    async def import_vm_image(
        self,
        file: UploadFile,
        name: str,
        description: Optional[str],
        os_type: str,
        vm_type: str,
        native_arch: str,
        default_cpu: int,
        default_ram_mb: int,
        default_disk_gb: int,
        user_id: UUID,
        db: Session,
    ) -> GoldenImage:
        """Import a VM image file as a GoldenImage.

        Supports OVA, QCOW2, VMDK, and VDI formats.
        All formats are converted to QCOW2 for use with QEMU.

        Args:
            file: Uploaded file
            name: Name for the golden image
            description: Optional description
            os_type: windows, linux, network, custom
            vm_type: container, linux_vm, windows_vm
            native_arch: x86_64 or arm64
            default_cpu: Default CPU cores
            default_ram_mb: Default RAM in MB
            default_disk_gb: Default disk size in GB
            user_id: ID of user importing the image
            db: Database session

        Returns:
            Created GoldenImage record
        """
        filename = file.filename.lower()
        ext = None
        for e in self.SUPPORTED_FORMATS:
            if filename.endswith(e):
                ext = e
                break

        if not ext:
            raise ValueError(f"Unsupported format. Supported: {', '.join(self.SUPPORTED_FORMATS)}")

        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Save uploaded file
            upload_path = temp_path / f"upload{ext}"
            with open(upload_path, 'wb') as f:
                content = await file.read()
                f.write(content)

            logger.info(f"Uploaded {file.filename} ({len(content)} bytes) to {upload_path}")

            # Convert to qcow2 if needed
            if ext == '.ova':
                qcow2_path = await self._convert_ova(upload_path, temp_path)
            elif ext == '.vmdk':
                qcow2_path = await self._convert_vmdk(upload_path, temp_path)
            elif ext == '.vdi':
                qcow2_path = await self._convert_vdi(upload_path, temp_path)
            else:  # Already qcow2
                qcow2_path = upload_path

            # Generate safe filename
            safe_name = name.lower().replace(' ', '-').replace('_', '-')
            safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '-')
            final_filename = f"{safe_name}.qcow2"

            # Move to golden images storage
            storage_path = self._move_to_storage(qcow2_path, final_filename)

            # Get file size
            size_bytes = storage_path.stat().st_size

            logger.info(f"Imported image stored at {storage_path} ({size_bytes} bytes)")

            # Create GoldenImage record
            golden = GoldenImage(
                name=name,
                description=description,
                source="import",
                disk_image_path=str(storage_path),
                import_format=ext[1:],  # Remove leading dot
                os_type=os_type,
                vm_type=vm_type,
                native_arch=native_arch,
                default_cpu=default_cpu,
                default_ram_mb=default_ram_mb,
                default_disk_gb=default_disk_gb,
                size_bytes=size_bytes,
                created_by=user_id,
            )
            db.add(golden)
            db.commit()
            db.refresh(golden)

            return golden

    async def _convert_ova(self, ova_path: Path, temp_dir: Path) -> Path:
        """Convert OVA to QCOW2.

        OVA is a tar archive containing OVF descriptor and VMDK disk(s).

        Args:
            ova_path: Path to OVA file
            temp_dir: Temporary directory for extraction

        Returns:
            Path to converted QCOW2 file
        """
        logger.info(f"Extracting OVA: {ova_path}")

        # Extract OVA (it's a tar file)
        extract_dir = temp_dir / "ova_contents"
        extract_dir.mkdir()

        with tarfile.open(ova_path, 'r') as tar:
            tar.extractall(extract_dir)

        # Find VMDK file(s)
        vmdk_files = list(extract_dir.glob('*.vmdk'))
        if not vmdk_files:
            raise ValueError("No VMDK disk found in OVA archive")

        # Use the largest VMDK (main disk)
        vmdk_path = max(vmdk_files, key=lambda p: p.stat().st_size)
        logger.info(f"Found VMDK: {vmdk_path}")

        # Convert VMDK to QCOW2
        return await self._convert_vmdk(vmdk_path, temp_dir)

    async def _convert_vmdk(self, vmdk_path: Path, temp_dir: Path) -> Path:
        """Convert VMDK to QCOW2 using qemu-img.

        Uses asyncio.create_subprocess_exec for safe command execution
        (no shell interpolation).

        Args:
            vmdk_path: Path to VMDK file
            temp_dir: Temporary directory for output

        Returns:
            Path to converted QCOW2 file
        """
        logger.info(f"Converting VMDK to QCOW2: {vmdk_path}")

        qcow2_path = temp_dir / "converted.qcow2"

        # Using create_subprocess_exec is safe - no shell interpolation
        proc = await asyncio.create_subprocess_exec(
            'qemu-img', 'convert',
            '-f', 'vmdk',
            '-O', 'qcow2',
            '-p',  # Progress
            str(vmdk_path),
            str(qcow2_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode() if stderr else 'Unknown error'
            raise RuntimeError(f"qemu-img convert failed: {error}")

        logger.info(f"Converted to QCOW2: {qcow2_path}")
        return qcow2_path

    async def _convert_vdi(self, vdi_path: Path, temp_dir: Path) -> Path:
        """Convert VDI to QCOW2 using qemu-img.

        Uses asyncio.create_subprocess_exec for safe command execution
        (no shell interpolation).

        Args:
            vdi_path: Path to VDI file
            temp_dir: Temporary directory for output

        Returns:
            Path to converted QCOW2 file
        """
        logger.info(f"Converting VDI to QCOW2: {vdi_path}")

        qcow2_path = temp_dir / "converted.qcow2"

        # Using create_subprocess_exec is safe - no shell interpolation
        proc = await asyncio.create_subprocess_exec(
            'qemu-img', 'convert',
            '-f', 'vdi',
            '-O', 'qcow2',
            '-p',
            str(vdi_path),
            str(qcow2_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode() if stderr else 'Unknown error'
            raise RuntimeError(f"qemu-img convert failed: {error}")

        logger.info(f"Converted to QCOW2: {qcow2_path}")
        return qcow2_path

    def _move_to_storage(self, source_path: Path, filename: str) -> Path:
        """Move a file to the golden images storage directory.

        Args:
            source_path: Current path of the file
            filename: Desired filename in storage

        Returns:
            Path to the stored file
        """
        dest_path = self.GOLDEN_IMAGES_DIR / filename

        # Handle filename collision by adding suffix
        counter = 1
        while dest_path.exists():
            stem = filename.rsplit('.', 1)[0]
            ext = filename.rsplit('.', 1)[1] if '.' in filename else ''
            dest_path = self.GOLDEN_IMAGES_DIR / f"{stem}-{counter}.{ext}"
            counter += 1

        shutil.move(str(source_path), str(dest_path))
        return dest_path
