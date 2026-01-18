# backend/cyroid/api/templates.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_

from cyroid.api.deps import DBSession, CurrentUser, filter_by_visibility, check_resource_access
from cyroid.models.template import VMTemplate
from cyroid.models.resource_tag import ResourceTag
from cyroid.schemas.template import VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse
from cyroid.schemas.user import ResourceTagCreate, ResourceTagsResponse

router = APIRouter(prefix="/templates", tags=["VM Templates"])


@router.get("", response_model=List[VMTemplateResponse])
def list_templates(db: DBSession, current_user: CurrentUser):
    """
    List templates visible to the current user.

    Visibility rules:
    - Admins see ALL templates
    - Users see templates they own
    - Users see seed templates (built-in templates shipped with CYROID)
    - Users see templates with matching tags (if they have tags)
    - Users see untagged templates (public)
    """
    if current_user.is_admin:
        return db.query(VMTemplate).all()

    # Non-admins: own templates + visibility-filtered shared templates + seed templates
    # Seed templates (is_seed=True) are always visible to all users
    shared_query = db.query(VMTemplate).filter(VMTemplate.created_by != current_user.id)
    shared_query = filter_by_visibility(shared_query, 'template', current_user, db, VMTemplate)

    query = db.query(VMTemplate).filter(
        or_(
            VMTemplate.created_by == current_user.id,  # Own templates
            VMTemplate.is_seed == True,  # Seed templates always visible
            VMTemplate.id.in_(shared_query.with_entities(VMTemplate.id).subquery())  # Shared templates
        )
    )
    return query.all()


@router.post("", response_model=VMTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(template_data: VMTemplateCreate, db: DBSession, current_user: CurrentUser):
    template = VMTemplate(
        **template_data.model_dump(),
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=VMTemplateResponse)
def get_template(template_id: UUID, db: DBSession, current_user: CurrentUser):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    check_resource_access('template', template_id, current_user, db, template.created_by)
    return template


@router.put("/{template_id}", response_model=VMTemplateResponse)
def update_template(
    template_id: UUID,
    template_data: VMTemplateUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Only owner or admin can update
    if template.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or admin can update this template",
        )

    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID, db: DBSession, current_user: CurrentUser):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Only owner or admin can delete
    if template.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or admin can delete this template",
        )

    # Also delete any associated resource tags
    db.query(ResourceTag).filter(
        ResourceTag.resource_type == 'template',
        ResourceTag.resource_id == template_id
    ).delete()

    db.delete(template)
    db.commit()


@router.post("/{template_id}/clone", response_model=VMTemplateResponse, status_code=status.HTTP_201_CREATED)
def clone_template(template_id: UUID, db: DBSession, current_user: CurrentUser):
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Anyone who can view the template can clone it
    check_resource_access('template', template_id, current_user, db, template.created_by)

    cloned = VMTemplate(
        name=f"{template.name} (Copy)",
        description=template.description,
        os_type=template.os_type,
        os_variant=template.os_variant,
        base_image=template.base_image,
        default_cpu=template.default_cpu,
        default_ram_mb=template.default_ram_mb,
        default_disk_gb=template.default_disk_gb,
        config_script=template.config_script,
        tags=template.tags.copy() if template.tags else [],
        created_by=current_user.id,
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    return cloned


# ============================================================================
# Visibility Tag Management Endpoints
# ============================================================================

@router.get("/{template_id}/tags", response_model=ResourceTagsResponse)
def get_template_tags(template_id: UUID, db: DBSession, current_user: CurrentUser):
    """Get visibility tags for a template."""
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    check_resource_access('template', template_id, current_user, db, template.created_by)

    tags = db.query(ResourceTag.tag).filter(
        ResourceTag.resource_type == 'template',
        ResourceTag.resource_id == template_id
    ).all()

    return ResourceTagsResponse(
        resource_type='template',
        resource_id=template_id,
        tags=[t[0] for t in tags]
    )


@router.post("/{template_id}/tags", status_code=status.HTTP_201_CREATED)
def add_template_tag(
    template_id: UUID,
    tag_data: ResourceTagCreate,
    db: DBSession,
    current_user: CurrentUser
):
    """Add a visibility tag to a template."""
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Only owner or admin can add tags
    if template.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or admin can add tags",
        )

    # Check if tag already exists
    existing = db.query(ResourceTag).filter(
        ResourceTag.resource_type == 'template',
        ResourceTag.resource_id == template_id,
        ResourceTag.tag == tag_data.tag
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag already exists on this template",
        )

    tag = ResourceTag(
        resource_type='template',
        resource_id=template_id,
        tag=tag_data.tag
    )
    db.add(tag)
    db.commit()

    return {"message": f"Tag '{tag_data.tag}' added to template"}


@router.delete("/{template_id}/tags/{tag}")
def remove_template_tag(
    template_id: UUID,
    tag: str,
    db: DBSession,
    current_user: CurrentUser
):
    """Remove a visibility tag from a template."""
    template = db.query(VMTemplate).filter(VMTemplate.id == template_id).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Only owner or admin can remove tags
    if template.created_by != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or admin can remove tags",
        )

    tag_obj = db.query(ResourceTag).filter(
        ResourceTag.resource_type == 'template',
        ResourceTag.resource_id == template_id,
        ResourceTag.tag == tag
    ).first()
    if not tag_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found on this template",
        )

    db.delete(tag_obj)
    db.commit()

    return {"message": f"Tag '{tag}' removed from template"}
