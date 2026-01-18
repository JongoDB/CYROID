# backend/cyroid/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cyroid.config import get_settings
from cyroid.api.auth import router as auth_router
from cyroid.api.users import router as users_router
from cyroid.api.templates import router as templates_router
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

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events for startup and shutdown."""
    # Startup
    from cyroid.services.event_broadcaster import get_connection_manager, get_broadcaster
    from cyroid.services.template_seeder import seed_all_templates
    from cyroid.services.scenario_seeder import seed_all_scenarios
    from cyroid.database import get_session_local

    # Seed built-in templates
    logger.info("Checking seed templates...")
    try:
        SessionLocal = get_session_local()
        db = SessionLocal()
        seeded = seed_all_templates(db)
        if seeded:
            logger.info(f"Seeded {len(seeded)} templates")
        db.close()
    except Exception as e:
        logger.warning(f"Template seeding skipped: {e}")

    # Seed built-in scenarios
    logger.info("Checking seed scenarios...")
    try:
        SessionLocal = get_session_local()
        db = SessionLocal()
        seeded = seed_all_scenarios(db)
        if seeded:
            logger.info(f"Seeded {len(seeded)} scenarios")
        db.close()
    except Exception as e:
        logger.warning(f"Scenario seeding skipped: {e}")

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
- **Template**: A predefined VM configuration (OS, resources, base image)

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

- **OpenAPI JSON**: `/openapi.json`
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **AI Context**: `/api/v1/schema/ai-context` (condensed guide for AI assistants)
"""

app = FastAPI(
    title=settings.app_name,
    description=API_DESCRIPTION,
    version=settings.app_version,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Authentication and user management"},
        {"name": "users", "description": "User account management"},
        {"name": "ranges", "description": "Range lifecycle management"},
        {"name": "networks", "description": "Network configuration"},
        {"name": "vms", "description": "Virtual machine management"},
        {"name": "templates", "description": "VM template library"},
        {"name": "artifacts", "description": "File and artifact management"},
        {"name": "snapshots", "description": "VM snapshot management"},
        {"name": "events", "description": "Event logging and monitoring"},
        {"name": "msel", "description": "Master Scenario Events List"},
        {"name": "scenarios", "description": "Training scenarios for cyber exercises"},
        {"name": "walkthrough", "description": "Lab walkthrough and student progress"},
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
app.include_router(templates_router, prefix="/api/v1")
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


@app.get("/health")
async def health_check():
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

## Core Workflow
1. POST /api/v1/ranges - Create range (name, description)
2. POST /api/v1/networks - Add networks to range (name, subnet, gateway, is_isolated)
3. POST /api/v1/vms - Add VMs to range (hostname, template_id, network_id, ip_address)
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
- POST /api/v1/vms - Create VM
  ```json
  {
    "range_id": "uuid",
    "template_id": "uuid",
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

### Templates
- GET /api/v1/templates - List available VM templates
  Returns templates with: id, name, os_type, os_variant, base_image, default_cpu, default_ram_mb

## Network Isolation Modes
- is_isolated=false: Network has internet access via VyOS NAT router
- is_isolated=true: Air-gapped network, no external access

## VM Types (based on template)
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
    {"hostname": "kali", "network": "internet", "template": "Kali Linux"},
    {"hostname": "webserver", "network": "dmz", "template": "Ubuntu Server"},
    {"hostname": "dc01", "network": "internal", "template": "Windows Server 2019"}
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
- Use template names to find template_id from GET /templates
- IP addresses must be within the network's subnet
- VMs can have multiple network interfaces via POST /vms/{id}/networks/{network_id}
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
