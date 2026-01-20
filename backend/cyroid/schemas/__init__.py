# backend/cyroid/schemas/__init__.py
from cyroid.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse
from cyroid.schemas.auth import LoginRequest, TokenResponse
from cyroid.schemas.template import VMTemplateBase, VMTemplateCreate, VMTemplateUpdate, VMTemplateResponse
from cyroid.schemas.network import NetworkBase, NetworkCreate, NetworkUpdate, NetworkResponse
from cyroid.schemas.vm import VMBase, VMCreate, VMUpdate, VMResponse
from cyroid.schemas.range import RangeBase, RangeCreate, RangeUpdate, RangeResponse, RangeDetailResponse
from cyroid.schemas.event_log import EventLogCreate, EventLogResponse, EventLogList
from cyroid.schemas.blueprint import (
    BlueprintCreate, BlueprintUpdate, BlueprintResponse, BlueprintDetailResponse,
    InstanceDeploy, InstanceResponse, BlueprintConfig, NetworkConfig, VMConfig
)
from cyroid.schemas.snapshot import SnapshotBase, SnapshotCreate, SnapshotUpdate, SnapshotResponse, SnapshotBrief
# Image Library schemas
from cyroid.schemas.base_image import (
    BaseImageBase, BaseImageCreate, BaseImageUpdate, BaseImageResponse, BaseImageBrief
)
from cyroid.schemas.golden_image import (
    GoldenImageBase, GoldenImageCreate, GoldenImageUpdate, GoldenImageResponse,
    GoldenImageBrief, GoldenImageImportRequest
)

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse",
    "LoginRequest", "TokenResponse",
    "VMTemplateBase", "VMTemplateCreate", "VMTemplateUpdate", "VMTemplateResponse",
    "NetworkBase", "NetworkCreate", "NetworkUpdate", "NetworkResponse",
    "VMBase", "VMCreate", "VMUpdate", "VMResponse",
    "RangeBase", "RangeCreate", "RangeUpdate", "RangeResponse", "RangeDetailResponse",
    "EventLogCreate", "EventLogResponse", "EventLogList",
    "BlueprintCreate", "BlueprintUpdate", "BlueprintResponse", "BlueprintDetailResponse",
    "InstanceDeploy", "InstanceResponse", "BlueprintConfig", "NetworkConfig", "VMConfig",
    "SnapshotBase", "SnapshotCreate", "SnapshotUpdate", "SnapshotResponse", "SnapshotBrief",
    # Image Library
    "BaseImageBase", "BaseImageCreate", "BaseImageUpdate", "BaseImageResponse", "BaseImageBrief",
    "GoldenImageBase", "GoldenImageCreate", "GoldenImageUpdate", "GoldenImageResponse",
    "GoldenImageBrief", "GoldenImageImportRequest",
]
