# backend/cyroid/models/__init__.py
from cyroid.models.base import Base
from cyroid.models.user import User, UserRole, UserAttribute, AVAILABLE_ROLES
from cyroid.models.resource_tag import ResourceTag
from cyroid.models.template import VMTemplate, OSType
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network
from cyroid.models.vm import VM, VMStatus, BootSource
from cyroid.models.artifact import Artifact, ArtifactPlacement, ArtifactType, MaliciousIndicator, PlacementStatus
from cyroid.models.snapshot import Snapshot
from cyroid.models.event_log import EventLog, EventType
from cyroid.models.connection import Connection, ConnectionProtocol, ConnectionState
from cyroid.models.msel import MSEL
from cyroid.models.inject import Inject, InjectStatus
from cyroid.models.router import RangeRouter, RouterStatus
from cyroid.models.walkthrough_progress import WalkthroughProgress
from cyroid.models.blueprint import RangeBlueprint, RangeInstance
from cyroid.models.content import Content, ContentAsset, ContentType
from cyroid.models.event import TrainingEvent, EventParticipant, EventStatus
# Image Library models
from cyroid.models.base_image import BaseImage, ImageType
from cyroid.models.golden_image import GoldenImage, GoldenImageSource

__all__ = [
    "Base",
    "User", "UserRole", "UserAttribute", "AVAILABLE_ROLES",
    "ResourceTag",
    "VMTemplate", "OSType",
    "Range", "RangeStatus",
    "Network",
    "VM", "VMStatus", "BootSource",
    "Artifact", "ArtifactPlacement", "ArtifactType", "MaliciousIndicator", "PlacementStatus",
    "Snapshot",
    "EventLog", "EventType",
    "Connection", "ConnectionProtocol", "ConnectionState",
    "MSEL",
    "Inject", "InjectStatus",
    "RangeRouter", "RouterStatus",
    "WalkthroughProgress",
    "RangeBlueprint", "RangeInstance",
    "Content", "ContentAsset", "ContentType",
    "TrainingEvent", "EventParticipant", "EventStatus",
    # Image Library
    "BaseImage", "ImageType",
    "GoldenImage", "GoldenImageSource",
]
