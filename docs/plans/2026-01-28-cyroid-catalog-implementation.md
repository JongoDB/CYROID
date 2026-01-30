# CYROID Catalog Backend Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable CYROID to consume training content from external catalog repositories (git or HTTP) via new backend models, service layer, and API endpoints.

**Architecture:** Add a `CatalogSource` model (points at a git/HTTP/local catalog repo) and a `CatalogInstalledItem` model (tracks what's been installed). A `CatalogService` handles git clone/pull, index.json parsing, and orchestrates installs by feeding content into the existing blueprint import pipeline. API endpoints expose source CRUD, catalog browsing, and install actions.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic, GitPython (for git operations), httpx (for HTTP fetches), existing blueprint import service.

**Design doc:** `docs/plans/2026-01-28-cyroid-catalog-design.md`

---

## Task 1: Add `catalog_storage_dir` to Settings

**Files:**
- Modify: `backend/cyroid/config.py`

**Step 1: Add the setting**

In `config.py`, add to the `Settings` class after `global_shared_dir`:

```python
# Catalog
catalog_storage_dir: str = os.path.join(_get_default_data_dir(), "catalogs")
```

**Step 2: Add volume mount to docker-compose.dev.yml**

In `docker-compose.dev.yml`, under the `api` and `worker` services' `volumes` section, add:

```yaml
- ./data/cyroid/catalogs:/data/cyroid/catalogs
```

**Step 3: Commit**

```bash
git add backend/cyroid/config.py docker-compose.dev.yml
git commit -m "feat(catalog): add catalog_storage_dir config setting"
```

---

## Task 2: Create Catalog Models

**Files:**
- Create: `backend/cyroid/models/catalog.py`
- Modify: `backend/cyroid/models/__init__.py`

**Step 1: Create the model file**

Create `backend/cyroid/models/catalog.py`:

```python
# backend/cyroid/models/catalog.py
import enum
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Text, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class CatalogSourceType(str, enum.Enum):
    git = "git"
    http = "http"
    local = "local"


class CatalogSyncStatus(str, enum.Enum):
    idle = "idle"
    syncing = "syncing"
    error = "error"


class CatalogItemType(str, enum.Enum):
    blueprint = "blueprint"
    scenario = "scenario"
    image = "image"
    base_image = "base_image"
    content = "content"


class CatalogSource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "catalog_sources"

    name: Mapped[str] = mapped_column(String(200), index=True)
    source_type: Mapped[CatalogSourceType] = mapped_column(
        SAEnum(CatalogSourceType), default=CatalogSourceType.git
    )
    url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(100), default="main")
    enabled: Mapped[bool] = mapped_column(default=True)
    sync_status: Mapped[CatalogSyncStatus] = mapped_column(
        SAEnum(CatalogSyncStatus), default=CatalogSyncStatus.idle
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    installed_items: Mapped[List["CatalogInstalledItem"]] = relationship(
        "CatalogInstalledItem", back_populates="source", cascade="all, delete-orphan"
    )


class CatalogInstalledItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "catalog_installed_items"

    catalog_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="CASCADE")
    )
    catalog_item_id: Mapped[str] = mapped_column(String(200), index=True)
    item_type: Mapped[CatalogItemType] = mapped_column(SAEnum(CatalogItemType))
    item_name: Mapped[str] = mapped_column(String(200))
    installed_version: Mapped[str] = mapped_column(String(100))
    installed_checksum: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    local_resource_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    installed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Relationships
    source: Mapped["CatalogSource"] = relationship(
        "CatalogSource", back_populates="installed_items"
    )
```

**Step 2: Register models in `__init__.py`**

Add to `backend/cyroid/models/__init__.py`:

Import line (after the last import):
```python
from cyroid.models.catalog import CatalogSource, CatalogInstalledItem, CatalogSourceType, CatalogSyncStatus, CatalogItemType
```

Add to `__all__` list:
```python
    # Catalog
    "CatalogSource", "CatalogInstalledItem", "CatalogSourceType", "CatalogSyncStatus", "CatalogItemType",
```

**Step 3: Generate and apply migration**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic revision --autogenerate -m "Add catalog source and installed item models"
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic upgrade head
```

**Step 4: Commit**

```bash
git add backend/cyroid/models/catalog.py backend/cyroid/models/__init__.py backend/alembic/versions/
git commit -m "feat(catalog): add CatalogSource and CatalogInstalledItem models"
```

---

## Task 3: Create Pydantic Schemas

**Files:**
- Create: `backend/cyroid/schemas/catalog.py`

**Step 1: Create the schema file**

Create `backend/cyroid/schemas/catalog.py`:

```python
# backend/cyroid/schemas/catalog.py
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from cyroid.models.catalog import CatalogSourceType, CatalogSyncStatus, CatalogItemType


# === Catalog Source Schemas ===

class CatalogSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_type: CatalogSourceType = CatalogSourceType.git
    url: str = Field(..., min_length=1, max_length=500)
    branch: str = Field(default="main", max_length=100)
    enabled: bool = True


class CatalogSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    branch: Optional[str] = Field(None, max_length=100)
    enabled: Optional[bool] = None


class CatalogSourceResponse(BaseModel):
    id: UUID
    name: str
    source_type: CatalogSourceType
    url: str
    branch: str
    enabled: bool
    sync_status: CatalogSyncStatus
    error_message: Optional[str] = None
    item_count: int = 0
    last_synced: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# === Catalog Item Schemas (from index.json — not DB-backed) ===

class CatalogItemSummary(BaseModel):
    """An item from the catalog index."""
    id: str
    type: CatalogItemType
    name: str
    description: str = ""
    tags: List[str] = []
    version: str = "1.0"
    path: str = ""
    checksum: str = ""
    # Blueprint-specific
    requires_images: List[str] = []
    includes_msel: bool = False
    includes_content: bool = False
    # Image-specific
    arch: Optional[str] = None
    docker_tag: Optional[str] = None
    # Install status (populated at query time)
    installed: bool = False
    installed_version: Optional[str] = None
    update_available: bool = False


class CatalogItemDetail(CatalogItemSummary):
    """Full item detail including README content."""
    readme: Optional[str] = None
    source_id: Optional[UUID] = None


# === Installed Item Schemas ===

class CatalogInstalledItemResponse(BaseModel):
    id: UUID
    catalog_source_id: UUID
    catalog_item_id: str
    item_type: CatalogItemType
    item_name: str
    installed_version: str
    installed_checksum: Optional[str] = None
    local_resource_id: Optional[UUID] = None
    installed_by: Optional[UUID] = None
    installed_at: datetime
    update_available: bool = False

    class Config:
        from_attributes = True


# === Install Request ===

class CatalogInstallRequest(BaseModel):
    source_id: UUID
    build_images: bool = False


# === Catalog Index (from index.json) ===

class CatalogIndex(BaseModel):
    catalog: dict = {}
    items: List[CatalogItemSummary] = []
```

**Step 2: Commit**

```bash
git add backend/cyroid/schemas/catalog.py
git commit -m "feat(catalog): add Pydantic schemas for catalog API"
```

---

## Task 4: Create Catalog Service

**Files:**
- Create: `backend/cyroid/services/catalog_service.py`

**Step 1: Create the service**

Create `backend/cyroid/services/catalog_service.py`:

```python
# backend/cyroid/services/catalog_service.py
"""
Service for managing catalog sources and installing catalog content.

Handles:
- Git clone/pull of catalog repos
- HTTP fetch of catalog index
- Reading local catalog directories
- Parsing index.json
- Installing blueprints, scenarios, images, base_images from catalog
"""
import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict
from uuid import UUID

import yaml
from sqlalchemy.orm import Session

from cyroid.config import get_settings
from cyroid.models.catalog import (
    CatalogSource,
    CatalogInstalledItem,
    CatalogSourceType,
    CatalogSyncStatus,
    CatalogItemType,
)
from cyroid.schemas.catalog import CatalogItemSummary, CatalogItemDetail

logger = logging.getLogger(__name__)


class CatalogService:
    """Service for catalog source management and content installation."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.storage_dir = Path(self.settings.catalog_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    # ========================
    # Source Management
    # ========================

    def get_source_dir(self, source: CatalogSource) -> Path:
        """Get the local directory for a catalog source."""
        return self.storage_dir / str(source.id)

    def sync_source(self, source: CatalogSource) -> int:
        """
        Sync a catalog source. Returns the number of items found.

        For git: clone or pull the repo.
        For http: fetch index.json.
        For local: just verify the path exists.
        """
        source.sync_status = CatalogSyncStatus.syncing
        source.error_message = None
        self.db.commit()

        try:
            if source.source_type == CatalogSourceType.git:
                self._sync_git(source)
            elif source.source_type == CatalogSourceType.http:
                self._sync_http(source)
            elif source.source_type == CatalogSourceType.local:
                self._sync_local(source)

            # Parse the index to count items
            index = self._load_index(source)
            item_count = len(index.get("items", []))

            source.sync_status = CatalogSyncStatus.idle
            source.item_count = item_count
            source.updated_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(f"Synced catalog source '{source.name}': {item_count} items")
            return item_count

        except Exception as e:
            source.sync_status = CatalogSyncStatus.error
            source.error_message = str(e)[:500]
            self.db.commit()
            logger.error(f"Failed to sync catalog source '{source.name}': {e}")
            raise

    def _sync_git(self, source: CatalogSource):
        """Clone or pull a git catalog repo."""
        repo_dir = self.get_source_dir(source)

        if (repo_dir / ".git").exists():
            # Pull
            logger.info(f"Pulling catalog repo: {source.url}")
            result = subprocess.run(
                ["git", "pull", "origin", source.branch],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git pull failed: {result.stderr.strip()}")
        else:
            # Clone
            logger.info(f"Cloning catalog repo: {source.url}")
            repo_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    "git", "clone",
                    "--branch", source.branch,
                    "--depth", "1",
                    source.url,
                    str(repo_dir),
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

    def _sync_http(self, source: CatalogSource):
        """Fetch index.json from an HTTP catalog source."""
        import httpx

        repo_dir = self.get_source_dir(source)
        repo_dir.mkdir(parents=True, exist_ok=True)

        index_url = source.url.rstrip("/") + "/index.json"
        logger.info(f"Fetching catalog index: {index_url}")

        response = httpx.get(index_url, timeout=30, follow_redirects=True)
        response.raise_for_status()

        index_file = repo_dir / "index.json"
        index_file.write_text(response.text)

        # Also fetch catalog.yaml if available
        try:
            catalog_url = source.url.rstrip("/") + "/catalog.yaml"
            resp = httpx.get(catalog_url, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                (repo_dir / "catalog.yaml").write_text(resp.text)
        except Exception:
            pass

    def _sync_local(self, source: CatalogSource):
        """Verify a local catalog directory exists."""
        local_path = Path(source.url)
        if not local_path.exists():
            raise RuntimeError(f"Local catalog path does not exist: {source.url}")
        if not (local_path / "index.json").exists() and not (local_path / "catalog.yaml").exists():
            raise RuntimeError(f"Not a valid catalog directory: {source.url} (no index.json or catalog.yaml)")

    def delete_source_data(self, source: CatalogSource):
        """Delete the local clone/cache for a catalog source."""
        repo_dir = self.get_source_dir(source)
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)

    # ========================
    # Index & Item Browsing
    # ========================

    def _get_catalog_root(self, source: CatalogSource) -> Path:
        """Get the root directory for reading catalog content."""
        if source.source_type == CatalogSourceType.local:
            return Path(source.url)
        return self.get_source_dir(source)

    def _load_index(self, source: CatalogSource) -> dict:
        """Load the index.json from a synced catalog source."""
        catalog_root = self._get_catalog_root(source)
        index_file = catalog_root / "index.json"

        if not index_file.exists():
            raise RuntimeError(
                f"Catalog index not found at {index_file}. Sync the source first."
            )

        with open(index_file) as f:
            return json.load(f)

    def list_items(
        self,
        source: CatalogSource,
        item_type: Optional[CatalogItemType] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[CatalogItemSummary]:
        """List items from a catalog source with optional filters."""
        index = self._load_index(source)
        items = []

        # Get installed items for this source to mark status
        installed = {
            item.catalog_item_id: item
            for item in self.db.query(CatalogInstalledItem)
            .filter(CatalogInstalledItem.catalog_source_id == source.id)
            .all()
        }

        for raw_item in index.get("items", []):
            # Type filter
            if item_type and raw_item.get("type") != item_type.value:
                continue

            # Search filter
            if search:
                search_lower = search.lower()
                name_match = search_lower in raw_item.get("name", "").lower()
                desc_match = search_lower in raw_item.get("description", "").lower()
                tag_match = any(search_lower in t.lower() for t in raw_item.get("tags", []))
                if not (name_match or desc_match or tag_match):
                    continue

            # Tag filter
            if tags:
                item_tags = set(raw_item.get("tags", []))
                if not item_tags.intersection(set(tags)):
                    continue

            # Build summary with install status
            item = CatalogItemSummary(**raw_item)
            if raw_item["id"] in installed:
                inst = installed[raw_item["id"]]
                item.installed = True
                item.installed_version = inst.installed_version
                item.update_available = (
                    inst.installed_checksum != raw_item.get("checksum", "")
                )

            items.append(item)

        return items

    def get_item_detail(
        self, source: CatalogSource, item_id: str
    ) -> Optional[CatalogItemDetail]:
        """Get full detail for a catalog item including README."""
        index = self._load_index(source)
        catalog_root = self._get_catalog_root(source)

        for raw_item in index.get("items", []):
            if raw_item["id"] != item_id:
                continue

            # Read README if it exists
            readme = None
            item_path = catalog_root / raw_item.get("path", "")
            readme_file = item_path / "README.md"
            if readme_file.exists():
                readme = readme_file.read_text()

            # Check install status
            installed_item = (
                self.db.query(CatalogInstalledItem)
                .filter(
                    CatalogInstalledItem.catalog_source_id == source.id,
                    CatalogInstalledItem.catalog_item_id == item_id,
                )
                .first()
            )

            detail = CatalogItemDetail(
                **raw_item,
                readme=readme,
                source_id=source.id,
            )
            if installed_item:
                detail.installed = True
                detail.installed_version = installed_item.installed_version
                detail.update_available = (
                    installed_item.installed_checksum != raw_item.get("checksum", "")
                )

            return detail

        return None

    # ========================
    # Installation
    # ========================

    def install_item(
        self,
        source: CatalogSource,
        item_id: str,
        user_id: Optional[UUID] = None,
        build_images: bool = False,
    ) -> CatalogInstalledItem:
        """Install a catalog item into the CYROID instance."""
        detail = self.get_item_detail(source, item_id)
        if not detail:
            raise ValueError(f"Item '{item_id}' not found in catalog")

        catalog_root = self._get_catalog_root(source)
        item_path = catalog_root / detail.path

        # Check if already installed
        existing = (
            self.db.query(CatalogInstalledItem)
            .filter(
                CatalogInstalledItem.catalog_source_id == source.id,
                CatalogInstalledItem.catalog_item_id == item_id,
            )
            .first()
        )
        if existing:
            raise ValueError(f"Item '{item_id}' is already installed")

        local_resource_id = None

        if detail.type == CatalogItemType.blueprint:
            local_resource_id = self._install_blueprint(
                item_path, detail, user_id, build_images
            )
        elif detail.type == CatalogItemType.scenario:
            self._install_scenario(item_path, detail)
        elif detail.type == CatalogItemType.image:
            self._install_image(item_path, detail, build_images)
        elif detail.type == CatalogItemType.base_image:
            self._install_base_image(item_path, detail)

        # Record the installation
        installed = CatalogInstalledItem(
            catalog_source_id=source.id,
            catalog_item_id=item_id,
            item_type=detail.type,
            item_name=detail.name,
            installed_version=detail.version,
            installed_checksum=detail.checksum,
            local_resource_id=local_resource_id,
            installed_by=user_id,
        )
        self.db.add(installed)
        self.db.commit()
        self.db.refresh(installed)

        logger.info(f"Installed catalog item: {detail.name} ({detail.type})")
        return installed

    def _install_blueprint(
        self,
        item_path: Path,
        detail: CatalogItemDetail,
        user_id: Optional[UUID],
        build_images: bool,
    ) -> Optional[UUID]:
        """Install a blueprint from the catalog."""
        from cyroid.models.blueprint import RangeBlueprint

        blueprint_file = item_path / "blueprint.yaml"
        if not blueprint_file.exists():
            raise RuntimeError(f"Blueprint file not found: {blueprint_file}")

        with open(blueprint_file) as f:
            bp_config = yaml.safe_load(f)

        # Install required images first
        catalog_root = item_path.parent.parent  # blueprints/<name> -> catalog root
        for image_name in detail.requires_images:
            image_dir = catalog_root / "images" / image_name
            if image_dir.exists():
                self._install_image_from_path(image_dir, image_name, build_images)

        # Extract walkthrough/content data
        walkthrough = bp_config.pop("walkthrough", None)
        events = bp_config.pop("events", None)
        content_ids = []

        # Create content library item from walkthrough if present
        if walkthrough:
            from cyroid.models.content import Content, ContentType

            content = Content(
                title=walkthrough.get("title", detail.name),
                description=walkthrough.get("description", ""),
                content_type=ContentType.STUDENT_GUIDE,
                walkthrough_data=walkthrough,
                version=walkthrough.get("version", "1.0"),
                tags=walkthrough.get("tags", []),
                is_published=True,
                created_by_id=user_id,
            )
            self.db.add(content)
            self.db.flush()
            content_ids.append(str(content.id))

        # Build MSEL content string from events
        msel_content = None
        if events:
            msel_lines = []
            for event in events:
                mins = event.get("delay_minutes", 0)
                hours = mins // 60
                remainder = mins % 60
                msel_lines.append(f"## T+{hours:02d}:{remainder:02d} - {event['title']}")
                msel_lines.append("")
                msel_lines.append(event.get("description", ""))
                msel_lines.append("")
            msel_content = "\n".join(msel_lines)

        # Also check for standalone msel.md
        msel_file = item_path / "msel.md"
        if msel_file.exists():
            msel_content = msel_file.read_text()

        # Build the blueprint config (matching RangeBlueprint.config format)
        config = {
            "networks": bp_config.get("networks", []),
            "vms": bp_config.get("vms", []),
            "router": bp_config.get("router", {}),
            "base_subnet_prefix": bp_config.get("base_subnet_prefix", "172.16"),
        }
        if msel_content:
            config["msel"] = {
                "content": msel_content,
                "format": "markdown",
            }

        blueprint = RangeBlueprint(
            name=bp_config.get("name", detail.name),
            description=bp_config.get("description", detail.description),
            config=config,
            content_ids=content_ids,
            created_by=user_id,
            is_seed=False,
        )
        self.db.add(blueprint)
        self.db.flush()

        return blueprint.id

    def _install_scenario(self, item_path: Path, detail: CatalogItemDetail):
        """Install a scenario YAML to the scenarios directory."""
        from cyroid.services.scenario_filesystem import get_scenarios_dir

        scenarios_dir = get_scenarios_dir()
        scenarios_dir.mkdir(parents=True, exist_ok=True)

        # item_path is like "scenarios/ransomware-attack.yaml" relative
        # but for the full path we need the actual file
        if item_path.is_file():
            src = item_path
        else:
            # item_path might be a directory for some layouts
            src = item_path
            for f in item_path.glob("*.yaml"):
                if f.name != "manifest.yaml":
                    src = f
                    break

        dest = scenarios_dir / f"{detail.id}.yaml"
        shutil.copy2(str(src), str(dest))
        logger.info(f"Installed scenario: {dest}")

    def _install_image(
        self, item_path: Path, detail: CatalogItemDetail, build_images: bool
    ):
        """Install a Docker image project (Dockerfile) from catalog."""
        self._install_image_from_path(item_path, detail.id, build_images)

    def _install_image_from_path(
        self, src_dir: Path, project_name: str, build_images: bool
    ):
        """Copy a Dockerfile project to /data/images/ and optionally build."""
        if not src_dir.exists():
            logger.warning(f"Image source not found: {src_dir}")
            return

        # Copy to data/images/<project_name>/
        dest_dir = Path("/data/images") / project_name
        if dest_dir.exists():
            logger.info(f"Image project already exists: {dest_dir}, skipping copy")
            return

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(src_dir), str(dest_dir), dirs_exist_ok=True)
        logger.info(f"Installed image project: {dest_dir}")

        # Read image.yaml for tag info
        image_yaml = dest_dir / "image.yaml"
        if image_yaml.exists():
            with open(image_yaml) as f:
                image_meta = yaml.safe_load(f)
            tag = image_meta.get("tag", f"cyroid/{project_name}:latest")

            # Register as BaseImage
            from cyroid.models.base_image import BaseImage, ImageType

            existing = (
                self.db.query(BaseImage)
                .filter(BaseImage.docker_image_tag == tag)
                .first()
            )
            if not existing:
                base_image = BaseImage(
                    name=image_meta.get("name", project_name),
                    docker_image_tag=tag,
                    image_type=ImageType.CONTAINER,
                    image_project_name=project_name,
                    description=image_meta.get("description", ""),
                )
                self.db.add(base_image)
                self.db.flush()
                logger.info(f"Registered BaseImage: {tag}")

    def _install_base_image(self, item_path: Path, detail: CatalogItemDetail):
        """Install a VM base image definition."""
        # Base images are metadata — read the YAML and register as a BaseImage
        # if not already present. The base image YAML defines the image source.
        if not item_path.exists():
            logger.warning(f"Template file not found: {item_path}")
            return

        if item_path.is_dir():
            # Find the YAML file
            yaml_files = list(item_path.glob("*.yaml"))
            if not yaml_files:
                return
            item_path = yaml_files[0]

        with open(item_path) as f:
            tmpl = yaml.safe_load(f)

        from cyroid.models.base_image import BaseImage

        base_tag = tmpl.get("base_image", "")
        if not base_tag:
            return

        existing = (
            self.db.query(BaseImage)
            .filter(BaseImage.docker_image_tag == base_tag)
            .first()
        )
        if existing:
            logger.info(f"Template image already registered: {base_tag}")
            return

        # Determine image type from template
        from cyroid.models.base_image import ImageType

        vm_type = tmpl.get("vm_type", "container")
        if vm_type == "windows_vm":
            image_type = ImageType.WINDOWS_VM
        elif vm_type == "linux_vm":
            image_type = ImageType.LINUX_VM
        elif base_tag.startswith("iso:"):
            image_type = ImageType.ISO
        else:
            image_type = ImageType.CONTAINER

        base_image = BaseImage(
            name=tmpl.get("name", detail.name),
            docker_image_tag=base_tag,
            image_type=image_type,
            description=tmpl.get("description", ""),
            os_type=tmpl.get("os_type"),
            os_family=tmpl.get("os_family"),
            os_version=tmpl.get("os_version"),
            default_cpu=tmpl.get("default_cpu"),
            default_ram_mb=tmpl.get("default_ram_mb"),
            default_disk_gb=tmpl.get("default_disk_gb"),
        )
        self.db.add(base_image)
        self.db.flush()
        logger.info(f"Registered base_image as BaseImage: {base_tag}")

    # ========================
    # Uninstall
    # ========================

    def uninstall_item(self, installed_item: CatalogInstalledItem):
        """Remove an installed catalog item."""
        # For blueprints, delete the blueprint record
        if installed_item.item_type == CatalogItemType.blueprint and installed_item.local_resource_id:
            from cyroid.models.blueprint import RangeBlueprint

            bp = (
                self.db.query(RangeBlueprint)
                .filter(RangeBlueprint.id == installed_item.local_resource_id)
                .first()
            )
            if bp:
                self.db.delete(bp)

        # For scenarios, delete the file
        if installed_item.item_type == CatalogItemType.scenario:
            from cyroid.services.scenario_filesystem import get_scenarios_dir

            scenario_file = get_scenarios_dir() / f"{installed_item.catalog_item_id}.yaml"
            if scenario_file.exists():
                scenario_file.unlink()

        self.db.delete(installed_item)
        self.db.commit()
        logger.info(f"Uninstalled catalog item: {installed_item.item_name}")
```

**Step 2: Commit**

```bash
git add backend/cyroid/services/catalog_service.py
git commit -m "feat(catalog): add CatalogService for sync, browse, and install"
```

---

## Task 5: Create API Endpoints

**Files:**
- Create: `backend/cyroid/api/catalog.py`
- Modify: `backend/cyroid/main.py`

**Step 1: Create the API file**

Create `backend/cyroid/api/catalog.py`:

```python
# backend/cyroid/api/catalog.py
"""
Catalog API endpoints for managing catalog sources, browsing items,
and installing content from external catalog repositories.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from cyroid.api.deps import DBSession, CurrentUser, AdminUser
from cyroid.models.catalog import (
    CatalogSource,
    CatalogInstalledItem,
    CatalogItemType,
)
from cyroid.schemas.catalog import (
    CatalogSourceCreate,
    CatalogSourceUpdate,
    CatalogSourceResponse,
    CatalogItemSummary,
    CatalogItemDetail,
    CatalogInstalledItemResponse,
    CatalogInstallRequest,
)
from cyroid.services.catalog_service import CatalogService

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _get_service(db) -> CatalogService:
    return CatalogService(db)


def _source_to_response(source: CatalogSource) -> CatalogSourceResponse:
    return CatalogSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        branch=source.branch,
        enabled=source.enabled,
        sync_status=source.sync_status,
        error_message=source.error_message,
        item_count=source.item_count,
        last_synced=source.updated_at,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _get_source_or_404(source_id: UUID, db) -> CatalogSource:
    source = db.query(CatalogSource).filter(CatalogSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Catalog source not found")
    return source


# ========================
# Catalog Sources (Admin)
# ========================


@router.get("/sources", response_model=List[CatalogSourceResponse])
def list_sources(db: DBSession, current_user: CurrentUser):
    """List all catalog sources."""
    sources = db.query(CatalogSource).order_by(CatalogSource.name).all()
    return [_source_to_response(s) for s in sources]


@router.post(
    "/sources",
    response_model=CatalogSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    data: CatalogSourceCreate, db: DBSession, current_user: AdminUser
):
    """Add a new catalog source. Admin only."""
    source = CatalogSource(
        name=data.name,
        source_type=data.source_type,
        url=data.url,
        branch=data.branch,
        enabled=data.enabled,
        created_by=current_user.id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _source_to_response(source)


@router.put("/sources/{source_id}", response_model=CatalogSourceResponse)
def update_source(
    source_id: UUID,
    data: CatalogSourceUpdate,
    db: DBSession,
    current_user: AdminUser,
):
    """Update a catalog source. Admin only."""
    source = _get_source_or_404(source_id, db)

    if data.name is not None:
        source.name = data.name
    if data.url is not None:
        source.url = data.url
    if data.branch is not None:
        source.branch = data.branch
    if data.enabled is not None:
        source.enabled = data.enabled

    db.commit()
    db.refresh(source)
    return _source_to_response(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: UUID, db: DBSession, current_user: AdminUser):
    """Delete a catalog source and its local cache. Admin only."""
    source = _get_source_or_404(source_id, db)
    service = _get_service(db)
    service.delete_source_data(source)
    db.delete(source)
    db.commit()


@router.post("/sources/{source_id}/sync", response_model=CatalogSourceResponse)
def sync_source(source_id: UUID, db: DBSession, current_user: AdminUser):
    """Trigger a sync for a catalog source. Admin only."""
    source = _get_source_or_404(source_id, db)
    service = _get_service(db)

    try:
        service.sync_source(source)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}",
        )

    db.refresh(source)
    return _source_to_response(source)


# ========================
# Catalog Browsing
# ========================


@router.get("/items", response_model=List[CatalogItemSummary])
def list_items(
    db: DBSession,
    current_user: CurrentUser,
    source_id: Optional[UUID] = Query(None, description="Filter by source"),
    item_type: Optional[CatalogItemType] = Query(None, description="Filter by type"),
    search: Optional[str] = Query(None, description="Search name/description/tags"),
    tags: Optional[str] = Query(None, description="Comma-separated tag filter"),
):
    """Browse catalog items across all synced sources."""
    service = _get_service(db)

    # Get sources to query
    query = db.query(CatalogSource).filter(CatalogSource.enabled == True)
    if source_id:
        query = query.filter(CatalogSource.id == source_id)
    sources = query.all()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    all_items = []
    for source in sources:
        try:
            items = service.list_items(
                source, item_type=item_type, search=search, tags=tag_list
            )
            all_items.extend(items)
        except Exception as e:
            # Skip sources that haven't been synced yet
            logger.warning(f"Could not read catalog source '{source.name}': {e}")
            continue

    return all_items


@router.get("/items/{source_id}/{item_id}", response_model=CatalogItemDetail)
def get_item_detail(
    source_id: UUID,
    item_id: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get full detail for a catalog item including README."""
    source = _get_source_or_404(source_id, db)
    service = _get_service(db)

    detail = service.get_item_detail(source, item_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    return detail


# ========================
# Installation
# ========================


@router.post("/items/{item_id}/install", response_model=CatalogInstalledItemResponse)
def install_item(
    item_id: str,
    data: CatalogInstallRequest,
    db: DBSession,
    current_user: AdminUser,
):
    """Install a catalog item. Admin only."""
    source = _get_source_or_404(data.source_id, db)
    service = _get_service(db)

    try:
        installed = service.install_item(
            source,
            item_id,
            user_id=current_user.id,
            build_images=data.build_images,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Install failed: {str(e)}")

    return CatalogInstalledItemResponse(
        id=installed.id,
        catalog_source_id=installed.catalog_source_id,
        catalog_item_id=installed.catalog_item_id,
        item_type=installed.item_type,
        item_name=installed.item_name,
        installed_version=installed.installed_version,
        installed_checksum=installed.installed_checksum,
        local_resource_id=installed.local_resource_id,
        installed_by=installed.installed_by,
        installed_at=installed.created_at,
    )


@router.get("/installed", response_model=List[CatalogInstalledItemResponse])
def list_installed(db: DBSession, current_user: CurrentUser):
    """List all installed catalog items."""
    items = (
        db.query(CatalogInstalledItem)
        .order_by(CatalogInstalledItem.created_at.desc())
        .all()
    )
    return [
        CatalogInstalledItemResponse(
            id=item.id,
            catalog_source_id=item.catalog_source_id,
            catalog_item_id=item.catalog_item_id,
            item_type=item.item_type,
            item_name=item.item_name,
            installed_version=item.installed_version,
            installed_checksum=item.installed_checksum,
            local_resource_id=item.local_resource_id,
            installed_by=item.installed_by,
            installed_at=item.created_at,
        )
        for item in items
    ]


@router.delete(
    "/installed/{installed_id}", status_code=status.HTTP_204_NO_CONTENT
)
def uninstall_item(
    installed_id: UUID, db: DBSession, current_user: AdminUser
):
    """Uninstall a catalog item. Admin only."""
    installed = (
        db.query(CatalogInstalledItem)
        .filter(CatalogInstalledItem.id == installed_id)
        .first()
    )
    if not installed:
        raise HTTPException(status_code=404, detail="Installed item not found")

    service = _get_service(db)
    service.uninstall_item(installed)


# Need logger import at module level
import logging

logger = logging.getLogger(__name__)
```

**Step 2: Register the router in main.py**

In `backend/cyroid/main.py`, add the import after the existing router imports:

```python
from cyroid.api.catalog import router as catalog_router
```

Add the openapi tag in the `openapi_tags` list:

```python
{"name": "catalog", "description": "Content catalog browsing and installation"},
```

Add the router include after the existing `app.include_router` lines:

```python
app.include_router(catalog_router, prefix="/api/v1")
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/catalog.py backend/cyroid/main.py
git commit -m "feat(catalog): add catalog API endpoints for sources, browsing, and install"
```

---

## Task 6: Add `httpx` and `pyyaml` Dependencies

**Files:**
- Modify: `backend/requirements.txt` (or `pyproject.toml` / `setup.cfg` depending on project)

**Step 1: Check current dependency file format**

```bash
ls backend/requirements*.txt backend/pyproject.toml backend/setup.cfg 2>/dev/null
```

**Step 2: Add dependencies if not already present**

Add `httpx` (for HTTP catalog sources) and `pyyaml` (for YAML parsing) to the dependencies file. `pyyaml` is likely already present since the codebase uses YAML elsewhere.

```
httpx>=0.27.0
pyyaml>=6.0
```

**Step 3: Rebuild**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build api
```

**Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(catalog): add httpx dependency for HTTP catalog sources"
```

---

## Task 7: Verify End-to-End

**Step 1: Rebuild and restart**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

**Step 2: Verify migration applied**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic current
```

**Step 3: Test via curl — create a catalog source**

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=<password>" | jq -r .access_token)

# Create catalog source pointing at the real repo
curl -s -X POST http://localhost:8000/api/v1/catalog/sources \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Official CYROID Catalog",
    "source_type": "git",
    "url": "https://github.com/JongoDB/cyroid-catalog.git",
    "branch": "main"
  }' | jq .
```

**Step 4: Test sync**

```bash
SOURCE_ID=<id-from-step-3>
curl -s -X POST "http://localhost:8000/api/v1/catalog/sources/$SOURCE_ID/sync" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Step 5: Test browsing**

```bash
# List all items
curl -s "http://localhost:8000/api/v1/catalog/items" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {id, type, name}'

# Filter by type
curl -s "http://localhost:8000/api/v1/catalog/items?item_type=blueprint" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Search
curl -s "http://localhost:8000/api/v1/catalog/items?search=red+team" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Step 6: Test install**

```bash
curl -s -X POST "http://localhost:8000/api/v1/catalog/items/red-team-training-lab/install" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"source_id\": \"$SOURCE_ID\"}" | jq .
```

**Step 7: Final commit**

```bash
git add -A
git commit -m "feat(catalog): complete backend catalog integration"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Config setting | `config.py`, `docker-compose.dev.yml` |
| 2 | DB models | `models/catalog.py`, `models/__init__.py`, migration |
| 3 | Pydantic schemas | `schemas/catalog.py` |
| 4 | Service layer | `services/catalog_service.py` |
| 5 | API endpoints | `api/catalog.py`, `main.py` |
| 6 | Dependencies | `requirements.txt` |
| 7 | E2E verification | curl tests |

All tasks follow the existing CYROID patterns: UUIDMixin + TimestampMixin for models, `DBSession`/`CurrentUser`/`AdminUser` deps for API routes, `CatalogService(db)` for business logic, and Pydantic schemas for request/response contracts.
