# cyroid/schemas/artifact.py
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class ArtifactBase(BaseModel):
    name: str
    description: Optional[str] = None
    artifact_type: str = "other"
    malicious_indicator: str = "safe"
    ttps: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ArtifactCreate(ArtifactBase):
    pass


class ArtifactUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    artifact_type: Optional[str] = None
    malicious_indicator: Optional[str] = None
    ttps: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ArtifactResponse(ArtifactBase):
    id: UUID
    file_path: str
    sha256_hash: str
    file_size: int
    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArtifactPlacementBase(BaseModel):
    artifact_id: UUID
    vm_id: UUID
    target_path: str


class ArtifactPlacementCreate(ArtifactPlacementBase):
    pass


class ArtifactPlacementResponse(ArtifactPlacementBase):
    id: UUID
    status: str
    placement_time: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
