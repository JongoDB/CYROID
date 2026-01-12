# cyroid/schemas/snapshot.py
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class SnapshotBase(BaseModel):
    name: str
    description: Optional[str] = None


class SnapshotCreate(SnapshotBase):
    vm_id: UUID


class SnapshotResponse(SnapshotBase):
    id: UUID
    vm_id: UUID
    docker_image_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
