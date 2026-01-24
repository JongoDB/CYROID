# backend/cyroid/api/blueprints.py
import os
import tempfile
from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models import Range, RangeBlueprint, RangeInstance
from cyroid.schemas.blueprint import (
    BlueprintCreate, BlueprintUpdate, BlueprintResponse, BlueprintDetailResponse,
    InstanceDeploy, InstanceResponse, BlueprintConfig
)
from cyroid.schemas.blueprint_export import (
    BlueprintImportValidation,
    BlueprintImportOptions,
    BlueprintImportResult,
    BlueprintExportOptions,
)
from cyroid.services.blueprint_service import (
    extract_config_from_range, extract_subnet_prefix, create_range_from_blueprint
)
from cyroid.services.blueprint_export_service import get_blueprint_export_service
from cyroid.tasks.deployment import deploy_range_task

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


@router.post("", response_model=BlueprintDetailResponse, status_code=status.HTTP_201_CREATED)
def create_blueprint(data: BlueprintCreate, db: DBSession, current_user: CurrentUser):
    """Create a new blueprint from an existing range."""
    # Verify range exists
    range_obj = db.query(Range).filter(Range.id == data.range_id).first()
    if not range_obj:
        raise HTTPException(status_code=404, detail="Range not found")

    # Extract config from range
    config = extract_config_from_range(db, data.range_id)

    # Create blueprint
    blueprint = RangeBlueprint(
        name=data.name,
        description=data.description,
        config=config.model_dump(),
        base_subnet_prefix=data.base_subnet_prefix,
        created_by=current_user.id,
        version=1,
        next_offset=0,
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)

    return _blueprint_to_detail_response(blueprint, config, current_user.username)


@router.get("", response_model=List[BlueprintResponse])
def list_blueprints(db: DBSession, current_user: CurrentUser):
    """List all blueprints."""
    blueprints = db.query(RangeBlueprint).all()
    return [_blueprint_to_response(b, db) for b in blueprints]


@router.get("/{blueprint_id}", response_model=BlueprintDetailResponse)
def get_blueprint(blueprint_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get blueprint details."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    config = BlueprintConfig.model_validate(blueprint.config)

    # Get creator username
    from cyroid.models import User
    creator = db.query(User).filter(User.id == blueprint.created_by).first()
    username = creator.username if creator else None

    return _blueprint_to_detail_response(blueprint, config, username)


@router.put("/{blueprint_id}", response_model=BlueprintDetailResponse)
def update_blueprint(
    blueprint_id: UUID, data: BlueprintUpdate, db: DBSession, current_user: CurrentUser
):
    """Update blueprint metadata. Increments version if config changes."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    if data.name is not None:
        blueprint.name = data.name
    if data.description is not None:
        blueprint.description = data.description

    db.commit()
    db.refresh(blueprint)

    config = BlueprintConfig.model_validate(blueprint.config)
    return _blueprint_to_detail_response(blueprint, config, current_user.username)


@router.delete("/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_blueprint(blueprint_id: UUID, db: DBSession, current_user: CurrentUser):
    """Delete a blueprint. Fails if instances exist."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    # Check for instances
    instance_count = db.query(RangeInstance).filter(
        RangeInstance.blueprint_id == blueprint_id
    ).count()
    if instance_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete blueprint with {instance_count} active instances"
        )

    db.delete(blueprint)
    db.commit()


@router.post("/{blueprint_id}/deploy", response_model=InstanceResponse, status_code=status.HTTP_201_CREATED)
def deploy_instance(
    blueprint_id: UUID, data: InstanceDeploy, db: DBSession, current_user: CurrentUser
):
    """Deploy a new instance from a blueprint."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    config = BlueprintConfig.model_validate(blueprint.config)

    # Get next offset and increment
    offset = blueprint.next_offset
    blueprint.next_offset += 1

    # Create range from blueprint with offset
    range_obj = create_range_from_blueprint(
        db=db,
        config=config,
        range_name=data.name,
        base_prefix=blueprint.base_subnet_prefix,
        offset=offset,
        created_by=current_user.id,
    )

    # Create instance record
    instance = RangeInstance(
        name=data.name,
        blueprint_id=blueprint.id,
        blueprint_version=blueprint.version,
        subnet_offset=offset,
        instructor_id=current_user.id,
        range_id=range_obj.id,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)

    # Auto-deploy if requested (queue async task)
    if data.auto_deploy:
        deploy_range_task.send(str(range_obj.id))

    return _instance_to_response(instance, db)


@router.get("/{blueprint_id}/instances", response_model=List[InstanceResponse])
def list_instances(blueprint_id: UUID, db: DBSession, current_user: CurrentUser):
    """List all instances of a blueprint."""
    blueprint = db.query(RangeBlueprint).filter(RangeBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    instances = db.query(RangeInstance).filter(
        RangeInstance.blueprint_id == blueprint_id
    ).all()

    return [_instance_to_response(i, db) for i in instances]


# ============ Export/Import Endpoints ============

@router.get("/{blueprint_id}/export")
def export_blueprint(
    blueprint_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    include_dockerfiles: bool = Query(
        default=True,
        description="Include Dockerfiles from /data/images/ for referenced images"
    ),
    include_docker_images: bool = Query(
        default=False,
        description="Include Docker image tarballs (large, but enables fully offline deployment)"
    ),
    include_content: bool = Query(
        default=True,
        description="Include Content Library items (student guides, etc.)"
    ),
    content_id: str = Query(
        default=None,
        description="Specific Content Library ID to include (UUID)"
    ),
):
    """
    Export a blueprint as a portable ZIP package (v3.0).

    The package includes:
    - Blueprint configuration (networks, VMs, MSEL)
    - Dockerfiles from /data/images/ for referenced images
    - Content Library items (student guides, etc.)
    - Manifest with checksums

    Options:
    - include_dockerfiles: Include Dockerfile projects for custom images
    - include_docker_images: Include Docker image tarballs (very large)
    - include_content: Include Content Library items
    - content_id: Specific Content ID to include
    """
    export_service = get_blueprint_export_service()

    try:
        options = BlueprintExportOptions(
            include_dockerfiles=include_dockerfiles,
            include_docker_images=include_docker_images,
            include_content=include_content,
        )

        # Parse content_id if provided
        parsed_content_id = None
        if content_id:
            try:
                parsed_content_id = UUID(content_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid content_id UUID format")

        archive_path, filename = export_service.export_blueprint(
            blueprint_id=blueprint_id,
            user=current_user,
            db=db,
            options=options,
            content_id=parsed_content_id,
        )

        return FileResponse(
            path=str(archive_path),
            filename=filename,
            media_type="application/zip",
            background=None,  # Don't delete file immediately
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/import/validate", response_model=BlueprintImportValidation)
async def validate_blueprint_import(
    file: UploadFile = File(...),
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """
    Validate a blueprint import package (dry-run) - v3.0.

    Checks for:
    - Blueprint name conflicts
    - Dockerfile project conflicts
    - Missing Docker images that need to be built
    - Content Library conflicts
    - VM image source availability
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")

    # Save uploaded file temporarily
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        export_service = get_blueprint_export_service()
        result = export_service.validate_import(
            archive_path=temp_file.name,
            db=db,
        )
        return result
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass


@router.post("/import", response_model=BlueprintImportResult)
async def import_blueprint(
    file: UploadFile = File(...),
    template_conflict_strategy: str = Query(
        default="skip",
        description="(Deprecated) How to handle template conflicts: skip, update, or error"
    ),
    new_name: str = Query(
        default=None,
        description="Rename blueprint on import to avoid name conflicts"
    ),
    dockerfile_conflict_strategy: str = Query(
        default="skip",
        description="How to handle Dockerfile conflicts: skip (use existing), overwrite, or error"
    ),
    content_conflict_strategy: str = Query(
        default="skip",
        description="How to handle Content Library conflicts: skip, rename, or use_existing"
    ),
    build_images: bool = Query(
        default=True,
        description="Automatically build Docker images from included Dockerfiles"
    ),
    db: DBSession = None,
    current_user: CurrentUser = None,
):
    """
    Import a blueprint from a ZIP package (v3.0).

    Creates:
    - Extracted Dockerfiles to /data/images/
    - Built Docker images and BaseImage records
    - Imported Content Library items
    - The blueprint with proper references

    Options:
    - new_name: Rename the blueprint to avoid conflicts
    - dockerfile_conflict_strategy: skip (use existing), overwrite, error
    - content_conflict_strategy: skip, rename, use_existing
    - build_images: Auto-build Docker images from Dockerfiles
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a ZIP archive")

    # Save uploaded file temporarily
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        options = BlueprintImportOptions(
            template_conflict_strategy=template_conflict_strategy,
            new_name=new_name,
            dockerfile_conflict_strategy=dockerfile_conflict_strategy,
            content_conflict_strategy=content_conflict_strategy,
            build_images=build_images,
        )

        export_service = get_blueprint_export_service()
        result = export_service.import_blueprint(
            archive_path=temp_file.name,
            options=options,
            user=current_user,
            db=db,
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.errors[0] if result.errors else "Import failed")

        return result
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass


# ============ Helper Functions ============

def _blueprint_to_response(blueprint: RangeBlueprint, db: Session) -> BlueprintResponse:
    config = blueprint.config
    return BlueprintResponse(
        id=blueprint.id,
        name=blueprint.name,
        description=blueprint.description,
        version=blueprint.version,
        base_subnet_prefix=blueprint.base_subnet_prefix,
        next_offset=blueprint.next_offset,
        created_by=blueprint.created_by,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        network_count=len(config.get("networks", [])),
        vm_count=len(config.get("vms", [])),
        instance_count=len(blueprint.instances),
        is_seed=blueprint.is_seed if hasattr(blueprint, 'is_seed') else False,
    )


def _blueprint_to_detail_response(
    blueprint: RangeBlueprint, config: BlueprintConfig, username: str = None
) -> BlueprintDetailResponse:
    return BlueprintDetailResponse(
        id=blueprint.id,
        name=blueprint.name,
        description=blueprint.description,
        version=blueprint.version,
        base_subnet_prefix=blueprint.base_subnet_prefix,
        next_offset=blueprint.next_offset,
        created_by=blueprint.created_by,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        network_count=len(config.networks),
        vm_count=len(config.vms),
        instance_count=len(blueprint.instances) if hasattr(blueprint, 'instances') else 0,
        config=config,
        created_by_username=username if username else ("CYROID" if (hasattr(blueprint, 'is_seed') and blueprint.is_seed) else None),
        is_seed=blueprint.is_seed if hasattr(blueprint, 'is_seed') else False,
    )


def _instance_to_response(instance: RangeInstance, db: Session) -> InstanceResponse:
    from cyroid.models import User

    range_obj = instance.range
    instructor = db.query(User).filter(User.id == instance.instructor_id).first()

    return InstanceResponse(
        id=instance.id,
        name=instance.name,
        blueprint_id=instance.blueprint_id,
        blueprint_version=instance.blueprint_version,
        subnet_offset=instance.subnet_offset,
        instructor_id=instance.instructor_id,
        range_id=instance.range_id,
        created_at=instance.created_at,
        range_name=range_obj.name if range_obj else None,
        range_status=range_obj.status.value if range_obj else None,
        instructor_username=instructor.username if instructor else None,
    )
