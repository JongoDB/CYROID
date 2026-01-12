# cyroid/api/artifacts.py
"""API endpoints for artifact management."""
from typing import List
from uuid import UUID, uuid4
import logging

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import io

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.artifact import Artifact, ArtifactPlacement, ArtifactType, MaliciousIndicator, PlacementStatus
from cyroid.models.vm import VM
from cyroid.schemas.artifact import (
    ArtifactCreate, ArtifactUpdate, ArtifactResponse,
    ArtifactPlacementCreate, ArtifactPlacementResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


def get_storage_service():
    """Lazy import storage service."""
    from cyroid.services.storage_service import get_storage_service as _get_storage
    return _get_storage()


def get_docker_service():
    """Lazy import docker service."""
    from cyroid.services.docker_service import get_docker_service as _get_docker
    return _get_docker()


@router.get("", response_model=List[ArtifactResponse])
def list_artifacts(db: DBSession, current_user: CurrentUser):
    """List all artifacts."""
    artifacts = db.query(Artifact).all()
    return artifacts


@router.post("/upload", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    db: DBSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(None),
    artifact_type: str = Form("other"),
    malicious_indicator: str = Form("safe"),
    ttps: str = Form(None),
    tags: str = Form(None),
):
    """Upload a new artifact."""
    storage = get_storage_service()

    # Generate unique file path
    artifact_id = uuid4()
    file_extension = file.filename.split(".")[-1] if "." in file.filename else ""
    object_name = f"artifacts/{artifact_id}/{file.filename}"

    # Upload to MinIO
    sha256_hash, file_size = storage.upload_file(
        file.file,
        object_name,
        content_type=file.content_type or "application/octet-stream",
    )

    # Parse list fields
    ttps_list = [t.strip() for t in ttps.split(",")] if ttps else []
    tags_list = [t.strip() for t in tags.split(",")] if tags else []

    # Create database record
    artifact = Artifact(
        id=artifact_id,
        name=name,
        description=description,
        file_path=object_name,
        sha256_hash=sha256_hash,
        file_size=file_size,
        artifact_type=ArtifactType(artifact_type),
        malicious_indicator=MaliciousIndicator(malicious_indicator),
        ttps=ttps_list,
        tags=tags_list,
        uploaded_by=current_user.id,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return artifact


@router.get("/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(artifact_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get artifact details."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )
    return artifact


@router.put("/{artifact_id}", response_model=ArtifactResponse)
def update_artifact(
    artifact_id: UUID,
    artifact_data: ArtifactUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update artifact metadata."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    update_data = artifact_data.model_dump(exclude_unset=True)

    # Handle enum fields
    if "artifact_type" in update_data:
        update_data["artifact_type"] = ArtifactType(update_data["artifact_type"])
    if "malicious_indicator" in update_data:
        update_data["malicious_indicator"] = MaliciousIndicator(update_data["malicious_indicator"])

    for field, value in update_data.items():
        setattr(artifact, field, value)

    db.commit()
    db.refresh(artifact)
    return artifact


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artifact(artifact_id: UUID, db: DBSession, current_user: CurrentUser):
    """Delete an artifact."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    # Delete from storage
    storage = get_storage_service()
    storage.delete_file(artifact.file_path)

    # Delete placements
    db.query(ArtifactPlacement).filter(ArtifactPlacement.artifact_id == artifact_id).delete()

    db.delete(artifact)
    db.commit()


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: UUID, db: DBSession, current_user: CurrentUser):
    """Download an artifact file."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    storage = get_storage_service()
    file_data = storage.download_file(artifact.file_path)
    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage",
        )

    filename = artifact.file_path.split("/")[-1]
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# Artifact Placement endpoints

@router.post("/placements", response_model=ArtifactPlacementResponse, status_code=status.HTTP_201_CREATED)
def create_placement(
    placement_data: ArtifactPlacementCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create an artifact placement."""
    # Verify artifact exists
    artifact = db.query(Artifact).filter(Artifact.id == placement_data.artifact_id).first()
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    # Verify VM exists
    vm = db.query(VM).filter(VM.id == placement_data.vm_id).first()
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VM not found",
        )

    placement = ArtifactPlacement(**placement_data.model_dump())
    db.add(placement)
    db.commit()
    db.refresh(placement)
    return placement


@router.get("/placements", response_model=List[ArtifactPlacementResponse])
def list_placements(
    vm_id: UUID = None,
    artifact_id: UUID = None,
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """List artifact placements."""
    query = db.query(ArtifactPlacement)
    if vm_id:
        query = query.filter(ArtifactPlacement.vm_id == vm_id)
    if artifact_id:
        query = query.filter(ArtifactPlacement.artifact_id == artifact_id)
    return query.all()


@router.post("/placements/{placement_id}/execute", response_model=ArtifactPlacementResponse)
def execute_placement(
    placement_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Execute an artifact placement (copy file to VM)."""
    placement = db.query(ArtifactPlacement).filter(ArtifactPlacement.id == placement_id).first()
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement not found",
        )

    if placement.status != PlacementStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute placement in {placement.status} status",
        )

    artifact = db.query(Artifact).filter(Artifact.id == placement.artifact_id).first()
    vm = db.query(VM).filter(VM.id == placement.vm_id).first()

    if not artifact or not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact or VM not found",
        )

    if not vm.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VM has no running container",
        )

    placement.status = PlacementStatus.IN_PROGRESS
    db.commit()

    try:
        # Download from storage
        storage = get_storage_service()
        file_data = storage.download_file(artifact.file_path)
        if not file_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage",
            )

        # Save to temp file and copy to container
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_data)
            tmp_path = tmp.name

        try:
            docker = get_docker_service()
            target_dir = os.path.dirname(placement.target_path)
            docker.copy_to_container(vm.container_id, tmp_path, target_dir)

            from datetime import datetime
            placement.status = PlacementStatus.PLACED
            placement.placement_time = datetime.utcnow()
            db.commit()
            db.refresh(placement)

        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Failed to execute placement {placement_id}: {e}")
        placement.status = PlacementStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to place artifact: {str(e)}",
        )

    return placement


@router.delete("/placements/{placement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_placement(
    placement_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete an artifact placement."""
    placement = db.query(ArtifactPlacement).filter(ArtifactPlacement.id == placement_id).first()
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Placement not found",
        )

    db.delete(placement)
    db.commit()
