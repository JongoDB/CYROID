# backend/cyroid/api/templates.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from cyroid.api.deps import DBSession, CurrentUser
from cyroid.models.template import VMTemplate
from cyroid.schemas.template import VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse

router = APIRouter(prefix="/templates", tags=["VM Templates"])


@router.get("", response_model=List[VMTemplateResponse])
def list_templates(db: DBSession, current_user: CurrentUser):
    templates = db.query(VMTemplate).all()
    return templates


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
