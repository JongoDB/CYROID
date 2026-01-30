# backend/cyroid/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings
from cyroid.api.auth import router as auth_router
from cyroid.api.users import router as users_router
from cyroid.api.ranges import router as ranges_router
from cyroid.api.networks import router as networks_router
from cyroid.api.vms import router as vms_router
from cyroid.api.websocket import router as websocket_router
from cyroid.api.artifacts import router as artifacts_router
from cyroid.api.snapshots import router as snapshots_router
from cyroid.api.events import router as events_router
from cyroid.api.connections import router as connections_router
from cyroid.api.msel import router as msel_router
from cyroid.api.walkthrough import router as walkthrough_router
from cyroid.api.cache import router as cache_router
from cyroid.api.system import router as system_router
from cyroid.api.blueprints import router as blueprints_router
from cyroid.api.instances import router as instances_router
from cyroid.api.scenarios import router as scenarios_router
from cyroid.api.admin import router as admin_router
from cyroid.api.files import router as files_router
from cyroid.api.content import router as content_router
from cyroid.api.training_events import router as training_events_router
from cyroid.api.images import router as images_router
from cyroid.api.notifications import router as notifications_router
from cyroid.api.catalog import router as catalog_router
from cyroid.api.registry import router as registry_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events for startup and shutdown."""
    # Startup
    from cyroid.services.event_broadcaster import get_connection_manager, get_broadcaster
    from cyroid.services.scenario_filesystem import get_scenarios_dir

    # Log scenarios directory (filesystem-based, populated via catalog install)
    scenarios_dir = get_scenarios_dir()
    logger.info(f"Scenarios directory: {scenarios_dir} (exists: {scenarios_dir.exists()})")

    logger.info("Starting real-time event services...")
    connection_manager = get_connection_manager()
    await connection_manager.start()

    broadcaster = get_broadcaster()
    await broadcaster.connect()

    logger.info("Real-time event services started")

    yield

    # Shutdown
    logger.info("Stopping real-time event services...")
    await connection_manager.stop()
    await broadcaster.disconnect()
    logger.info("Real-time event services stopped")


API_DESCRIPTION = """
# CYROID - Cyber Range Orchestrator In Docker

CYROID is a platform for creating and managing cyber training ranges using Docker containers and VMs.

## Concepts

- **Range**: A complete training environment containing networks and VMs
- **Network**: An isolated network segment (e.g., 172.16.0.0/24) for VM communication
- **VM**: A virtual machine (container or QEMU VM) running in the range
- **Image Library**: Three-tier image management (Base Images, Golden Images, Snapshots)

## Quick Start

1. **Create a range**: `POST /api/v1/ranges`
2. **Add networks**: `POST /api/v1/networks`
3. **Add VMs**: `POST /api/v1/vms`
4. **Deploy**: `POST /api/v1/ranges/{id}/deploy`
5. **Access consoles**: Use the WebSocket endpoints or UI

## Authentication

All endpoints (except `/health` and `/api/v1/auth/*`) require a JWT token.
Include it in the `Authorization` header: `Bearer <token>`

## API Documentation

- **Swagger UI**: `/docs` (interactive API explorer)
- **ReDoc**: `/redoc` (alternative documentation view)
- **OpenAPI JSON**: `/openapi.json` (machine-readable schema)
- **AI Context**: `/api/v1/schema/ai-context` (condensed guide for AI assistants)

## Health Checks

- `/health` - Basic health check
- `/api/health` - API health check (alias)
- `/api/v1/health` - Versioned health check (alias)
"""

app = FastAPI(
    title=settings.app_name,
    description=API_DESCRIPTION,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "auth", "description": "Authentication and user management"},
        {"name": "users", "description": "User account management"},
        {"name": "ranges", "description": "Range lifecycle management"},
        {"name": "networks", "description": "Network configuration"},
        {"name": "vms", "description": "Virtual machine management"},
        {"name": "artifacts", "description": "File and artifact management"},
        {"name": "snapshots", "description": "VM snapshot management"},
        {"name": "events", "description": "Event logging and monitoring"},
        {"name": "msel", "description": "Master Scenario Events List"},
        {"name": "scenarios", "description": "Training scenarios for cyber exercises"},
        {"name": "walkthrough", "description": "Lab walkthrough and student progress"},
        {"name": "content", "description": "Training content and materials"},
        {"name": "training-events", "description": "Training event scheduling and management"},
        {"name": "Notifications", "description": "User-scoped notifications and alerts"},
        {"name": "catalog", "description": "Content catalog browsing and installation"},
        {"name": "system", "description": "System configuration and status"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(ranges_router, prefix="/api/v1")
app.include_router(networks_router, prefix="/api/v1")
app.include_router(vms_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")
app.include_router(artifacts_router, prefix="/api/v1")
app.include_router(snapshots_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(msel_router, prefix="/api/v1")
app.include_router(walkthrough_router, prefix="/api/v1")
app.include_router(cache_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(blueprints_router, prefix="/api/v1")
app.include_router(instances_router, prefix="/api/v1")
app.include_router(scenarios_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(content_router, prefix="/api/v1")
app.include_router(training_events_router, prefix="/api/v1")
app.include_router(images_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(registry_router, prefix="/api/v1")


@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/api/v1/version")
async def get_version():
    """Return application version information."""
    return {
        "version": settings.app_version,
        "commit": settings.git_commit,
        "build_date": settings.build_date,
        "api_version": "v1",
        "app_name": settings.app_name,
    }


AI_CONTEXT = """# CYROID API Quick Reference (for AI Assistants)

## Overview
CYROID creates Docker-based cyber training ranges with isolated networks and VMs.
Uses a three-tier Image Library: Base Images (containers/ISOs), Golden Images (configured VMs), Snapshots (forks).

## Core Workflow
1. POST /api/v1/ranges - Create range (name, description)
2. POST /api/v1/networks - Add networks to range (name, subnet, gateway, is_isolated)
3. POST /api/v1/vms - Add VMs to range (hostname, base_image_id, network_id, ip_address)
4. POST /api/v1/ranges/{id}/deploy - Deploy the range
5. POST /api/v1/ranges/{id}/start - Start a stopped range
6. POST /api/v1/ranges/{id}/stop - Stop a running range
7. POST /api/v1/ranges/{id}/teardown - Destroy and reset to draft

## Key Endpoints

### Ranges
- GET /api/v1/ranges - List all ranges
- POST /api/v1/ranges - Create range {"name": "string", "description": "string"}
- GET /api/v1/ranges/{id} - Get range details
- DELETE /api/v1/ranges/{id} - Delete range

### Networks
- GET /api/v1/networks?range_id={id} - List networks in range
- POST /api/v1/networks - Create network
  ```json
  {
    "range_id": "uuid",
    "name": "internal",
    "subnet": "172.16.1.0/24",
    "gateway": "172.16.1.1",
    "is_isolated": true
  }
  ```

### VMs
- GET /api/v1/vms?range_id={id} - List VMs in range
- POST /api/v1/vms - Create VM (use base_image_id, golden_image_id, or snapshot_id)
  ```json
  {
    "range_id": "uuid",
    "base_image_id": "uuid",
    "network_id": "uuid",
    "hostname": "webserver",
    "ip_address": "172.16.1.10",
    "cpu": 2,
    "ram_mb": 2048
  }
  ```
- POST /api/v1/vms/{id}/start - Start VM
- POST /api/v1/vms/{id}/stop - Stop VM
- POST /api/v1/vms/{id}/networks/{network_id}?ip_address=x.x.x.x - Add network interface

### Image Library (VM Library)
- GET /api/v1/cache/base-images - List base images (containers, ISOs)
- GET /api/v1/cache/golden-images - List golden images (configured VMs)
- GET /api/v1/cache/snapshots - List snapshots (VM forks)
- POST /api/v1/cache/pull - Pull Docker image to cache
- POST /api/v1/cache/build/{project} - Build Dockerfile from /data/images/{project}/

### Blueprints (Reusable Range Templates)
- GET /api/v1/blueprints - List all blueprints
- POST /api/v1/blueprints - Create blueprint from existing range
- POST /api/v1/blueprints/{id}/deploy - Deploy new instance from blueprint
- GET /api/v1/blueprints/{id}/export - Export blueprint (with Dockerfiles, MSEL, content)
- POST /api/v1/blueprints/import - Import blueprint from export file

## Network Isolation Modes
- is_isolated=false: Network has internet access via VyOS NAT router
- is_isolated=true: Air-gapped network, no external access

## VM Types (based on image)
- Linux containers (KasmVNC for GUI, Docker exec for terminal)
- Windows VMs (via dockur/windows, VNC console)
- Linux VMs (via QEMU ISO boot, VNC console)

## Common Patterns

### Red Team Lab
```json
{
  "networks": [
    {"name": "internet", "subnet": "172.16.0.0/24", "is_isolated": false},
    {"name": "dmz", "subnet": "172.16.1.0/24", "is_isolated": true},
    {"name": "internal", "subnet": "172.16.2.0/24", "is_isolated": true}
  ],
  "vms": [
    {"hostname": "kali", "network": "internet", "base_image_tag": "cyroid/kali-attack:latest"},
    {"hostname": "webserver", "network": "dmz", "base_image_tag": "cyroid/redteam-lab-wordpress:latest"},
    {"hostname": "dc01", "network": "internal", "base_image_tag": "cyroid/samba-dc:latest"}
  ]
}
```

## Authentication
All API calls require: `Authorization: Bearer <jwt_token>`
Get token via: POST /api/v1/auth/login {"username": "x", "password": "y"}

## Status Values
- Range: draft, deploying, running, stopped, error
- VM: pending, creating, running, stopped, error
- Network: pending, provisioned

## Tips
- Always deploy range after adding all networks and VMs
- Use base_image_id (UUID) or base_image_tag (docker tag) to specify VM image
- IP addresses must be within the network's subnet
- VMs can have multiple network interfaces via POST /vms/{id}/networks/{network_id}
- Use Blueprints for reusable range configurations
"""


@app.get("/api/v1/schema/ai-context", tags=["system"])
async def get_ai_context():
    """
    Get a condensed API guide optimized for AI assistants.

    This endpoint returns a markdown document that provides AI coding assistants
    (Claude, GPT, Copilot, etc.) with the context needed to generate valid
    CYROID API calls without access to source code.
    """
    return {
        "content": AI_CONTEXT,
        "format": "markdown",
        "version": settings.app_version,
    }
