# CYROID Refactor: Docker-in-Docker Range Isolation

## Context

CYROID is a cyber range orchestration platform that deploys Docker-based training environments. We're refactoring from direct Docker deployment to Docker-in-Docker (DinD) isolation to solve IP conflicts between concurrent range instances.

### Current Problem
- Multiple ranges deployed on same Docker host share network namespace
- Ranges with identical IP spaces (e.g., both using 10.0.1.0/24) conflict
- Current workaround of IP offsetting breaks training material consistency

### Solution: Docker-in-Docker
Each range instance runs inside its own DinD container, which provides complete network namespace isolation. The inner Docker daemon manages the actual range VMs/containers with their exact blueprint IPs.

### Why DinD over LXD
- Cross-platform: Works on macOS (Docker Desktop), Linux, and Windows
- Familiar tooling: Standard Docker CLI and API
- No additional runtime: Uses existing Docker installation
- Dev-friendly: Team can develop on any OS

### Trade-offs Accepted
- Requires `privileged: true` for DinD containers
- Slight storage overhead (overlay-on-overlay, mitigated with volumes)
- Additional network hop for range traffic

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Host (macOS Docker Desktop / Linux Docker / Windows Docker)            │
│                                                                         │
│  cyroid-mgmt network: 172.30.0.0/24                                    │
│       │                                                                 │
│       │  ┌───────────────────────────────────────────────────────────┐ │
│       │  │  CYROID Services (Host Docker)                            │ │
│       ├──┤                                                           │ │
│       │  │  ┌─────┐ ┌────┐ ┌─────┐ ┌───────┐ ┌────────┐ ┌───────┐   │ │
│       │  │  │ API │ │ DB │ │Redis│ │ MinIO │ │Traefik │ │Worker │   │ │
│       │  │  │ .10 │ │.11 │ │ .12 │ │  .13  │ │  .14   │ │  .15  │   │ │
│       │  │  └─────┘ └────┘ └─────┘ └───────┘ └────────┘ └───────┘   │ │
│       │  └───────────────────────────────────────────────────────────┘ │
│       │                                                                 │
│  cyroid-ranges network: 172.30.1.0/24                                  │
│       │                                                                 │
│       │  ┌──────────────────────────┐  ┌──────────────────────────┐   │
│       │  │ DinD: cyroid-range-abc12 │  │ DinD: cyroid-range-def34 │   │
│       ├──┤ IP: 172.30.1.10          │  │ IP: 172.30.1.11          │   │
│       │  │ privileged: true         │  │ privileged: true         │   │
│       │  │                          │  │                          │   │
│       │  │ ┌──────────────────────┐ │  │ ┌──────────────────────┐ │   │
│       │  │ │ Inner Docker Daemon  │ │  │ │ Inner Docker Daemon  │ │   │
│       │  │ │                      │ │  │ │                      │ │   │
│       │  │ │ br-lan: 10.0.1.1/24  │ │  │ │ br-lan: 10.0.1.1/24  │ │ ← Same IPs OK!
│       │  │ │ br-dmz: 10.0.2.1/24  │ │  │ │ br-dmz: 10.0.2.1/24  │ │   │
│       │  │ │ br-wan: 10.0.0.1/24  │ │  │ │ br-wan: 10.0.0.1/24  │ │   │
│       │  │ │                      │ │  │ │                      │ │   │
│       │  │ │ ┌────┐ ┌────┐ ┌────┐│ │  │ │ ┌────┐ ┌────┐       │ │   │
│       │  │ │ │web │ │db  │ │mail││ │  │ │ │web │ │db  │       │ │   │
│       │  │ │ │.10 │ │.20 │ │.30 ││ │  │ │ │.10 │ │.20 │       │ │   │
│       │  │ │ └────┘ └────┘ └────┘│ │  │ │ └────┘ └────┘       │ │   │
│       │  │ └──────────────────────┘ │  │ └──────────────────────┘ │   │
│       │  └──────────────────────────┘  └──────────────────────────┘   │
│       │         ↑                              ↑                       │
│       │         └──── Isolated namespaces ─────┘                       │
└───────┴─────────────────────────────────────────────────────────────────┘
```

## Network Design

### Management Networks

**Why two management networks:**
- `cyroid-mgmt` (172.30.0.0/24): CYROID infrastructure services
- `cyroid-ranges` (172.30.1.0/24): Range DinD containers
- Separation allows for network policies and cleaner organization
- Both connected to Traefik for routing

**Why 172.30.x.x:**
- Avoids 192.168.0.0/24, 192.168.1.0/24 (common home/office routers)
- Avoids 10.0.0.0/8 (commonly used in range blueprints)
- Avoids 172.17.0.0/16 (Docker default bridge)
- RFC 1918 private space, unlikely to conflict

### IP Allocation Scheme

```
172.30.0.0/24 - CYROID Infrastructure
├── 172.30.0.1     - Gateway
├── 172.30.0.2-9   - Reserved
├── 172.30.0.10    - API service
├── 172.30.0.11    - PostgreSQL
├── 172.30.0.12    - Redis
├── 172.30.0.13    - MinIO
├── 172.30.0.14    - Traefik
├── 172.30.0.15    - Worker
└── 172.30.0.16-50 - Reserved for future services

172.30.1.0/24 - Range DinD Containers
├── 172.30.1.1     - Gateway
├── 172.30.1.10    - cyroid-range-{uuid-1}
├── 172.30.1.11    - cyroid-range-{uuid-2}
└── ...            - Dynamic allocation (up to ~240 concurrent ranges)
```

### Range Internal Networks

- **No restrictions** - ranges can use any IP space
- Each DinD container has its own network namespace
- Docker networks inside DinD are completely isolated
- Blueprints use original IPs (10.0.1.0/24, 192.168.1.0/24, etc.)
- **No translation layer needed**

### VNC/Console Access Flow

```
User Browser
    → Traefik (172.30.0.14:443)
    → Route based on range ID in path/header
    → DinD container (172.30.1.x:6080)
    → noVNC proxy inside DinD
    → Target VM container
```

---

## Code to Remove / Deprecate

### REMOVE ENTIRELY

#### 1. IP Offset/Translation Logic

Any code that calculates modified subnets based on range ID:

```python
# SEARCH FOR AND DELETE patterns like:

def calculate_network_offset(range_id: int, base_subnet: str) -> str:
    """REMOVE - DinD isolation eliminates need for this."""
    pass

def translate_ip_for_range(range_id: int, logical_ip: str) -> str:
    """REMOVE - No IP translation needed."""
    pass

def get_logical_ip_from_physical(range_id: int, physical_ip: str) -> str:
    """REMOVE - IPs are now 1:1 with blueprints."""
    pass

# Also remove any subnet manipulation like:
# - Modifying octets based on range_id
# - Maintaining "logical" vs "physical" IP mappings
# - Subnet pool allocation/tracking
```

#### 2. Shared Docker Network Creation for Ranges

```python
# DELETE - Range networks are now created inside DinD, not on host

# OLD pattern to REMOVE:
async def create_range_network_on_host(self, network_config: NetworkConfig):
    subnet = self.calculate_offset(network_config.subnet)  # DELETE
    self.docker_client.networks.create(...)  # DELETE for ranges
```

#### 3. Network Conflict Detection/Avoidance

```python
# DELETE completely - conflicts are impossible with DinD isolation

async def check_subnet_conflicts(subnet: str) -> bool:
    """REMOVE - DinD namespaces prevent conflicts."""
    pass

async def find_available_subnet_offset() -> int:
    """REMOVE - No offsetting needed."""
    pass

def get_next_available_network_id() -> int:
    """REMOVE - Not needed with isolation."""
    pass
```

#### 4. Single Docker Client Pattern for Ranges

```python
# MODIFY - Ranges no longer use the host Docker client

# OLD pattern to REMOVE:
class DockerService:
    def __init__(self):
        self.client = docker.from_env()  # Only for host operations now

    async def create_range_vm(self, vm_config):
        # This created VMs on host Docker - REMOVE for ranges
        self.client.containers.run(...)
```

### FILES TO DELETE (if they exist)

```
backend/cyroid/services/network_offset_service.py
backend/cyroid/utils/ip_translation.py
backend/cyroid/utils/subnet_calculator.py
backend/cyroid/utils/network_pool.py
tests/test_ip_translation.py
tests/test_network_offset.py
```

### DATABASE COLUMNS TO REMOVE

```sql
-- Remove in migration after refactor is complete:
ALTER TABLE ranges DROP COLUMN IF EXISTS network_offset;
ALTER TABLE range_networks DROP COLUMN IF EXISTS physical_subnet;
ALTER TABLE vms DROP COLUMN IF EXISTS physical_ip;
-- Any other offset/translation tracking columns
```

### CONFIGURATION TO REMOVE

```bash
# Remove from .env if present:
# NETWORK_OFFSET_BASE=...
# ENABLE_IP_TRANSLATION=...
# SUBNET_POOL_START=...
# SUBNET_POOL_END=...
# NETWORK_OFFSET_ENABLED=...
```

### FRONTEND CODE TO REMOVE

```typescript
// DELETE any IP translation display logic:

// REMOVE patterns like:
const displayIp = translateToLogicalIp(vm.physical_ip, range.offset);
const physicalIp = translateToPhysicalIp(vm.logical_ip, range.offset);

// REPLACE with direct usage:
const displayIp = vm.ip;  // Now always the real IP
```

---

## Implementation Tasks

### Phase 1: DinD Service Layer

Create new service: `backend/cyroid/services/dind_service.py`

```python
"""Docker-in-Docker service for range isolation."""

import asyncio
import docker
from docker.errors import NotFound, APIError
from typing import Optional
from cyroid.config import settings
import logging

logger = logging.getLogger(__name__)


class DinDService:
    """Manages Docker-in-Docker containers for range isolation."""

    DIND_IMAGE = "docker:24-dind"
    DOCKER_PORT = 2375
    STARTUP_TIMEOUT = 60  # seconds

    def __init__(self):
        self.host_client = docker.from_env()
        self._range_clients: dict[str, docker.DockerClient] = {}

    async def create_range_container(
        self,
        range_id: str,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
    ) -> dict:
        """
        Create a DinD container for range isolation.

        Args:
            range_id: Unique identifier for the range
            memory_limit: Memory limit (e.g., "8g", "4096m")
            cpu_limit: CPU limit as float (e.g., 4.0 for 4 cores)

        Returns:
            dict with container_name, container_id, mgmt_ip, docker_url
        """
        container_name = f"cyroid-range-{range_id[:8]}"
        volume_name = f"cyroid-range-{range_id[:8]}-docker"

        # Prepare container configuration
        host_config = {
            "privileged": True,  # Required for DinD
            "publish_all_ports": False,
        }

        # Resource limits
        if memory_limit:
            host_config["mem_limit"] = memory_limit
        if cpu_limit:
            host_config["nano_cpus"] = int(cpu_limit * 1e9)

        # Create volume for Docker data (improves performance)
        try:
            self.host_client.volumes.create(name=volume_name)
        except APIError:
            pass  # Volume may already exist

        # Create the DinD container
        container = self.host_client.containers.run(
            image=self.DIND_IMAGE,
            name=container_name,
            detach=True,
            privileged=True,
            environment={
                "DOCKER_TLS_CERTDIR": "",  # Disable TLS for internal communication
            },
            volumes={
                volume_name: {"bind": "/var/lib/docker", "mode": "rw"}
            },
            network="cyroid-ranges",
            **host_config
        )

        # Get container info including IP
        container.reload()
        networks = container.attrs["NetworkSettings"]["Networks"]
        mgmt_ip = networks.get("cyroid-ranges", {}).get("IPAddress")

        if not mgmt_ip:
            # Fallback: try to get IP from any network
            for net_name, net_info in networks.items():
                if net_info.get("IPAddress"):
                    mgmt_ip = net_info["IPAddress"]
                    break

        if not mgmt_ip:
            raise RuntimeError(f"Failed to get IP for container {container_name}")

        docker_url = f"tcp://{mgmt_ip}:{self.DOCKER_PORT}"

        # Wait for inner Docker daemon to be ready
        await self._wait_for_docker_ready(docker_url)

        return {
            "container_name": container_name,
            "container_id": container.id,
            "mgmt_ip": mgmt_ip,
            "docker_url": docker_url,
            "docker_port": self.DOCKER_PORT,
            "volume_name": volume_name,
        }

    async def delete_range_container(self, range_id: str) -> None:
        """Delete DinD container and associated resources."""
        container_name = f"cyroid-range-{range_id[:8]}"
        volume_name = f"cyroid-range-{range_id[:8]}-docker"

        # Close cached client if exists
        self.close_range_client(range_id)

        # Stop and remove container
        try:
            container = self.host_client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Deleted DinD container: {container_name}")
        except NotFound:
            logger.warning(f"Container not found: {container_name}")
        except Exception as e:
            logger.error(f"Error deleting container {container_name}: {e}")

        # Remove volume
        try:
            volume = self.host_client.volumes.get(volume_name)
            volume.remove(force=True)
            logger.info(f"Deleted volume: {volume_name}")
        except NotFound:
            pass
        except Exception as e:
            logger.warning(f"Error deleting volume {volume_name}: {e}")

    async def get_container_info(self, range_id: str) -> Optional[dict]:
        """Get DinD container status and network info."""
        container_name = f"cyroid-range-{range_id[:8]}"

        try:
            container = self.host_client.containers.get(container_name)
            container.reload()

            networks = container.attrs["NetworkSettings"]["Networks"]
            mgmt_ip = networks.get("cyroid-ranges", {}).get("IPAddress")

            return {
                "container_name": container_name,
                "container_id": container.id,
                "status": container.status,
                "mgmt_ip": mgmt_ip,
                "docker_url": f"tcp://{mgmt_ip}:{self.DOCKER_PORT}" if mgmt_ip else None,
            }
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting container info for {range_id}: {e}")
            return None

    def get_range_client(self, range_id: str, docker_url: str) -> docker.DockerClient:
        """
        Get or create a Docker client for a range's DinD container.

        Args:
            range_id: Range identifier
            docker_url: Docker daemon URL (tcp://ip:port)

        Returns:
            DockerClient connected to the range's Docker daemon
        """
        if range_id not in self._range_clients:
            self._range_clients[range_id] = docker.DockerClient(base_url=docker_url)

        return self._range_clients[range_id]

    def close_range_client(self, range_id: str) -> None:
        """Close and remove cached Docker client for a range."""
        if range_id in self._range_clients:
            try:
                self._range_clients[range_id].close()
            except Exception:
                pass
            del self._range_clients[range_id]

    async def _wait_for_docker_ready(
        self,
        docker_url: str,
        timeout: int = None
    ) -> None:
        """Wait for Docker daemon inside DinD to be ready."""
        timeout = timeout or self.STARTUP_TIMEOUT
        client = docker.DockerClient(base_url=docker_url)

        for i in range(timeout):
            try:
                client.ping()
                logger.info(f"Docker daemon ready at {docker_url}")
                client.close()
                return
            except Exception:
                if i % 10 == 0:
                    logger.debug(f"Waiting for Docker at {docker_url}... ({i}s)")
                await asyncio.sleep(1)

        client.close()
        raise TimeoutError(f"Docker daemon not ready at {docker_url} after {timeout}s")

    async def exec_in_container(
        self,
        range_id: str,
        command: list[str]
    ) -> tuple[int, str]:
        """
        Execute a command inside the DinD container.

        Returns:
            tuple of (exit_code, output)
        """
        container_name = f"cyroid-range-{range_id[:8]}"

        try:
            container = self.host_client.containers.get(container_name)
            result = container.exec_run(command, demux=True)
            stdout = result.output[0].decode() if result.output[0] else ""
            stderr = result.output[1].decode() if result.output[1] else ""
            return result.exit_code, stdout + stderr
        except Exception as e:
            logger.error(f"Error executing command in {container_name}: {e}")
            raise

    async def list_range_containers(self) -> list[dict]:
        """List all CYROID range DinD containers."""
        containers = self.host_client.containers.list(
            all=True,
            filters={"name": "cyroid-range-"}
        )

        result = []
        for container in containers:
            networks = container.attrs["NetworkSettings"]["Networks"]
            mgmt_ip = networks.get("cyroid-ranges", {}).get("IPAddress")

            result.append({
                "container_name": container.name,
                "container_id": container.id,
                "status": container.status,
                "mgmt_ip": mgmt_ip,
                "range_id": container.name.replace("cyroid-range-", ""),
            })

        return result
```

### Phase 2: Refactor Docker Service

Modify: `backend/cyroid/services/docker_service.py`

```python
"""Docker service with DinD support for range isolation."""

import docker
from typing import Optional
from cyroid.services.dind_service import DinDService
from cyroid.schemas.vm import VMConfig, NetworkConfig
import logging

logger = logging.getLogger(__name__)


class DockerService:
    """
    Docker operations service.

    - Host operations: Uses local Docker daemon (for CYROID infrastructure)
    - Range operations: Uses Docker daemon inside range's DinD container
    """

    def __init__(self, dind_service: DinDService):
        self.dind = dind_service
        self._host_client = docker.from_env()

    @property
    def host_client(self) -> docker.DockerClient:
        """Docker client for host operations (CYROID services only)."""
        return self._host_client

    async def get_range_client(self, range_id: str) -> docker.DockerClient:
        """
        Get Docker client for a range's DinD container.

        Retrieves connection info from DinD service and returns cached client.
        """
        container_info = await self.dind.get_container_info(range_id)
        if not container_info or not container_info.get("docker_url"):
            raise ValueError(f"Range {range_id} has no active DinD container")

        return self.dind.get_range_client(range_id, container_info["docker_url"])

    # =========================================================================
    # Range Network Operations (inside DinD)
    # =========================================================================

    async def create_range_network(
        self,
        range_id: str,
        name: str,
        subnet: str,
        gateway: Optional[str] = None,
    ) -> str:
        """
        Create Docker network inside range's DinD container.

        Uses EXACT subnet from blueprint - no translation needed.

        Returns:
            Network ID
        """
        client = await self.get_range_client(range_id)

        ipam_pool = docker.types.IPAMPool(subnet=subnet, gateway=gateway)
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])

        network = client.networks.create(
            name=name,
            driver="bridge",
            ipam=ipam_config,
        )

        logger.info(f"Created network '{name}' ({subnet}) in range {range_id}")
        return network.id

    async def delete_range_network(self, range_id: str, name: str) -> None:
        """Delete Docker network inside range's DinD container."""
        client = await self.get_range_client(range_id)

        try:
            network = client.networks.get(name)
            network.remove()
            logger.info(f"Deleted network '{name}' from range {range_id}")
        except docker.errors.NotFound:
            logger.warning(f"Network '{name}' not found in range {range_id}")

    async def list_range_networks(self, range_id: str) -> list[dict]:
        """List all networks in a range's DinD container."""
        client = await self.get_range_client(range_id)
        networks = client.networks.list()

        return [
            {
                "id": n.id,
                "name": n.name,
                "driver": n.attrs.get("Driver"),
                "subnet": (
                    n.attrs.get("IPAM", {})
                    .get("Config", [{}])[0]
                    .get("Subnet")
                ),
            }
            for n in networks
            if n.name not in ("bridge", "host", "none")  # Skip default networks
        ]

    # =========================================================================
    # Range VM/Container Operations (inside DinD)
    # =========================================================================

    async def create_range_vm(
        self,
        range_id: str,
        vm_config: VMConfig,
    ) -> str:
        """
        Create VM container inside range's DinD container.

        Uses EXACT IPs from blueprint - no translation needed.

        Returns:
            Container ID
        """
        client = await self.get_range_client(range_id)

        # Primary network connection
        primary_nic = vm_config.network_interfaces[0]

        # Create container
        container = client.containers.run(
            image=vm_config.image,
            name=vm_config.name,
            hostname=vm_config.hostname or vm_config.name,
            detach=True,
            network=primary_nic.network,
            environment=vm_config.environment or {},
            ports=vm_config.port_mappings or {},
            volumes=vm_config.volume_mappings or {},
            # Add more config as needed
        )

        # Set IP on primary network
        primary_network = client.networks.get(primary_nic.network)
        primary_network.disconnect(container)
        primary_network.connect(container, ipv4_address=primary_nic.ip_address)

        # Attach additional networks with their IPs
        for nic in vm_config.network_interfaces[1:]:
            network = client.networks.get(nic.network)
            network.connect(container, ipv4_address=nic.ip_address)

        logger.info(
            f"Created VM '{vm_config.name}' in range {range_id} "
            f"with IP {primary_nic.ip_address}"
        )
        return container.id

    async def delete_range_vm(self, range_id: str, vm_name: str) -> None:
        """Delete VM container from range's DinD container."""
        client = await self.get_range_client(range_id)

        try:
            container = client.containers.get(vm_name)
            container.stop(timeout=10)
            container.remove(force=True)
            logger.info(f"Deleted VM '{vm_name}' from range {range_id}")
        except docker.errors.NotFound:
            logger.warning(f"VM '{vm_name}' not found in range {range_id}")

    async def get_range_vm(self, range_id: str, vm_name: str) -> Optional[dict]:
        """Get VM container info from range's DinD container."""
        client = await self.get_range_client(range_id)

        try:
            container = client.containers.get(vm_name)
            container.reload()

            # Extract network info
            networks = {}
            for net_name, net_info in container.attrs["NetworkSettings"]["Networks"].items():
                networks[net_name] = {
                    "ip_address": net_info.get("IPAddress"),
                    "mac_address": net_info.get("MacAddress"),
                    "gateway": net_info.get("Gateway"),
                }

            return {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else None,
                "networks": networks,
            }
        except docker.errors.NotFound:
            return None

    async def list_range_vms(self, range_id: str) -> list[dict]:
        """List all VM containers in a range's DinD container."""
        client = await self.get_range_client(range_id)
        containers = client.containers.list(all=True)

        result = []
        for container in containers:
            networks = {}
            for net_name, net_info in container.attrs["NetworkSettings"]["Networks"].items():
                if net_name not in ("bridge", "host", "none"):
                    networks[net_name] = net_info.get("IPAddress")

            result.append({
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "networks": networks,
            })

        return result

    async def vm_action(
        self,
        range_id: str,
        vm_name: str,
        action: str
    ) -> bool:
        """
        Perform action on VM container (start, stop, restart).

        Returns:
            True if action was successful
        """
        client = await self.get_range_client(range_id)

        try:
            container = client.containers.get(vm_name)

            if action == "start":
                container.start()
            elif action == "stop":
                container.stop(timeout=10)
            elif action == "restart":
                container.restart(timeout=10)
            else:
                raise ValueError(f"Unknown action: {action}")

            logger.info(f"Performed '{action}' on VM '{vm_name}' in range {range_id}")
            return True

        except docker.errors.NotFound:
            logger.warning(f"VM '{vm_name}' not found in range {range_id}")
            return False
        except Exception as e:
            logger.error(f"Error performing '{action}' on VM '{vm_name}': {e}")
            raise

    # =========================================================================
    # Host Operations (CYROID infrastructure only)
    # =========================================================================

    async def get_host_containers(self, filters: dict = None) -> list:
        """List containers on host Docker (CYROID infrastructure)."""
        return self._host_client.containers.list(all=True, filters=filters)

    async def pull_image(self, image: str, range_id: Optional[str] = None) -> None:
        """
        Pull Docker image.

        If range_id is provided, pulls to that range's DinD.
        Otherwise pulls to host Docker.
        """
        if range_id:
            client = await self.get_range_client(range_id)
        else:
            client = self._host_client

        client.images.pull(image)
        logger.info(f"Pulled image '{image}'" + (f" to range {range_id}" if range_id else ""))
```

### Phase 3: Refactor Range Service

Modify: `backend/cyroid/services/range_service.py`

```python
"""Range lifecycle management with DinD isolation."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from cyroid.services.dind_service import DinDService
from cyroid.services.docker_service import DockerService
from cyroid.schemas.range import RangeConfig, RangeDeployment
from cyroid.models.range import Range
import logging

logger = logging.getLogger(__name__)


class RangeService:
    """
    Manages range lifecycle with DinD-based isolation.

    Each range runs in its own Docker-in-Docker container,
    providing complete network namespace isolation.
    """

    def __init__(
        self,
        db: AsyncSession,
        dind_service: DinDService,
        docker_service: DockerService,
    ):
        self.db = db
        self.dind = dind_service
        self.docker = docker_service

    async def deploy_range(
        self,
        range_id: str,
        config: RangeConfig,
    ) -> RangeDeployment:
        """
        Deploy a range instance.

        Steps:
        1. Create DinD container for isolation
        2. Create Docker networks inside DinD (exact blueprint IPs)
        3. Deploy VMs inside DinD (exact blueprint IPs)
        4. Configure external access (Traefik routes)

        Returns:
            RangeDeployment with status and connection info
        """
        logger.info(f"Deploying range {range_id}")

        # 1. Create isolated DinD container
        dind_info = await self.dind.create_range_container(
            range_id=range_id,
            memory_limit=config.resource_limits.memory if config.resource_limits else None,
            cpu_limit=config.resource_limits.cpu if config.resource_limits else None,
        )

        logger.info(
            f"Created DinD container {dind_info['container_name']} "
            f"at {dind_info['mgmt_ip']}"
        )

        # Store DinD info in database
        await self._store_dind_info(range_id, dind_info)

        try:
            # 2. Create networks inside DinD (exact blueprint subnets!)
            for network in config.networks:
                await self.docker.create_range_network(
                    range_id=range_id,
                    name=network.name,
                    subnet=network.subnet,  # Exact subnet from blueprint
                    gateway=network.gateway,
                )

            # 3. Pull required images to DinD (if not cached)
            unique_images = set(vm.image for vm in config.vms)
            for image in unique_images:
                try:
                    await self.docker.pull_image(image, range_id=range_id)
                except Exception as e:
                    logger.warning(f"Could not pull image {image}: {e}")

            # 4. Deploy VMs inside DinD (exact IPs from blueprint!)
            for vm in config.vms:
                await self.docker.create_range_vm(
                    range_id=range_id,
                    vm_config=vm,
                )

            # 5. Configure Traefik for VNC/console access
            await self._configure_traefik_routes(range_id, dind_info["mgmt_ip"])

            # Update range status
            await self._update_range_status(range_id, "deployed")

            return RangeDeployment(
                range_id=range_id,
                status="deployed",
                dind_container=dind_info["container_name"],
                mgmt_ip=dind_info["mgmt_ip"],
                docker_url=dind_info["docker_url"],
            )

        except Exception as e:
            logger.error(f"Failed to deploy range {range_id}: {e}")
            # Cleanup on failure
            await self.destroy_range(range_id)
            raise

    async def destroy_range(self, range_id: str) -> None:
        """
        Destroy a range instance.

        Deleting the DinD container automatically cleans up:
        - All Docker containers inside
        - All Docker networks inside
        - All Docker volumes inside (except the data volume, deleted separately)
        """
        logger.info(f"Destroying range {range_id}")

        # Remove Traefik routes
        await self._remove_traefik_routes(range_id)

        # Delete DinD container (cleans up everything inside)
        await self.dind.delete_range_container(range_id)

        # Update database
        await self._clear_dind_info(range_id)
        await self._update_range_status(range_id, "stopped")

        logger.info(f"Range {range_id} destroyed")

    async def get_range_status(self, range_id: str) -> Optional[dict]:
        """Get current status of a range including DinD container info."""
        dind_info = await self.dind.get_container_info(range_id)

        if not dind_info:
            return {"status": "not_deployed", "dind_container": None}

        # Get VMs if container is running
        vms = []
        if dind_info["status"] == "running":
            try:
                vms = await self.docker.list_range_vms(range_id)
            except Exception as e:
                logger.warning(f"Could not list VMs for range {range_id}: {e}")

        return {
            "status": dind_info["status"],
            "dind_container": dind_info["container_name"],
            "mgmt_ip": dind_info["mgmt_ip"],
            "docker_url": dind_info.get("docker_url"),
            "vms": vms,
        }

    async def _store_dind_info(self, range_id: str, dind_info: dict) -> None:
        """Store DinD container info in database."""
        # Implementation: Update range record with DinD info
        # range.dind_container_id = dind_info["container_id"]
        # range.dind_container_name = dind_info["container_name"]
        # range.dind_mgmt_ip = dind_info["mgmt_ip"]
        # range.dind_docker_url = dind_info["docker_url"]
        pass

    async def _clear_dind_info(self, range_id: str) -> None:
        """Clear DinD container info from database."""
        pass

    async def _update_range_status(self, range_id: str, status: str) -> None:
        """Update range status in database."""
        pass

    async def _configure_traefik_routes(self, range_id: str, mgmt_ip: str) -> None:
        """
        Add Traefik routes for VNC/console access to this range.

        Creates dynamic routing rules so users can access:
        - VNC consoles for each VM
        - Any exposed services from range VMs
        """
        # Implementation: Write to Traefik dynamic config file or use API
        # Route pattern: /range/{range_id}/vm/{vm_name}/vnc -> {mgmt_ip}:6080
        pass

    async def _remove_traefik_routes(self, range_id: str) -> None:
        """Remove Traefik routes for this range."""
        pass
```

### Phase 4: Database Schema Updates

Create migration: `alembic revision -m "add_dind_tracking"`

```python
"""Add DinD container tracking to ranges.

Revision ID: xxxx
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET


def upgrade():
    # Add DinD tracking columns
    op.add_column("ranges", sa.Column("dind_container_id", sa.String(64)))
    op.add_column("ranges", sa.Column("dind_container_name", sa.String(64)))
    op.add_column("ranges", sa.Column("dind_mgmt_ip", INET))
    op.add_column("ranges", sa.Column("dind_docker_url", sa.String(128)))

    # Index for faster lookups
    op.create_index("ix_ranges_dind_container_name", "ranges", ["dind_container_name"])


def downgrade():
    op.drop_index("ix_ranges_dind_container_name")
    op.drop_column("ranges", "dind_docker_url")
    op.drop_column("ranges", "dind_mgmt_ip")
    op.drop_column("ranges", "dind_container_name")
    op.drop_column("ranges", "dind_container_id")
```

Create second migration: `alembic revision -m "remove_deprecated_offset_columns"`

```python
"""Remove deprecated network offset columns.

Revision ID: yyyy
Depends: xxxx
"""

from alembic import op


def upgrade():
    # Remove offset-related columns (check if they exist first)
    # These were used for the IP translation approach - no longer needed

    # Check and drop from ranges table
    try:
        op.drop_column("ranges", "network_offset")
    except Exception:
        pass  # Column may not exist

    # Check and drop from range_networks table
    try:
        op.drop_column("range_networks", "physical_subnet")
    except Exception:
        pass

    # Check and drop from vms table
    try:
        op.drop_column("vms", "physical_ip")
    except Exception:
        pass


def downgrade():
    # One-way migration - don't restore deprecated columns
    pass
```

### Phase 5: Configuration Updates

Update: `backend/cyroid/config.py`

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ... existing settings ...

    # === DinD Configuration ===
    DIND_IMAGE: str = "docker:24-dind"
    DIND_STARTUP_TIMEOUT: int = 60  # seconds to wait for inner Docker
    DIND_DOCKER_PORT: int = 2375

    # === Network Configuration ===
    # Management network for CYROID services
    CYROID_MGMT_NETWORK: str = "cyroid-mgmt"
    CYROID_MGMT_SUBNET: str = "172.30.0.0/24"

    # Network for range DinD containers
    CYROID_RANGES_NETWORK: str = "cyroid-ranges"
    CYROID_RANGES_SUBNET: str = "172.30.1.0/24"

    # === Range Defaults ===
    RANGE_DEFAULT_MEMORY: str = "8g"
    RANGE_DEFAULT_CPU: float = 4.0

    # === DEPRECATED - TO BE REMOVED ===
    # These settings are no longer used with DinD isolation
    # NETWORK_OFFSET_ENABLED: bool = False
    # SUBNET_POOL_START: int = 1
    # SUBNET_POOL_END: int = 255
    # NETWORK_OFFSET_BASE: str = "10.0.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

Update: `.env`

```bash
# === DinD Configuration ===
DIND_IMAGE=docker:24-dind
DIND_STARTUP_TIMEOUT=60
DIND_DOCKER_PORT=2375

# === Network Configuration ===
CYROID_MGMT_NETWORK=cyroid-mgmt
CYROID_MGMT_SUBNET=172.30.0.0/24
CYROID_RANGES_NETWORK=cyroid-ranges
CYROID_RANGES_SUBNET=172.30.1.0/24

# === Range Defaults ===
RANGE_DEFAULT_MEMORY=8g
RANGE_DEFAULT_CPU=4.0

# === REMOVED - No longer needed ===
# NETWORK_OFFSET_ENABLED=false
# SUBNET_POOL_START=1
# SUBNET_POOL_END=255
```

### Phase 6: docker-compose.yml Updates

```yaml
version: "3.8"

networks:
  # Network for CYROID infrastructure services
  cyroid-mgmt:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.0.0/24
          gateway: 172.30.0.1

  # Network for range DinD containers
  # Ranges connect here, internal range networks are inside DinD
  cyroid-ranges:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.1.0/24
          gateway: 172.30.1.1

services:
  # === CYROID Infrastructure ===

  api:
    image: cyroid-api:latest
    container_name: cyroid-api
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.10
      cyroid-ranges:  # Needs access to range DinD containers
    volumes:
      # Mount Docker socket to manage DinD containers on host
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DATABASE_URL=postgresql://cyroid:${DB_PASSWORD}@172.30.0.11:5432/cyroid
      - REDIS_URL=redis://172.30.0.12:6379
      - MINIO_ENDPOINT=172.30.0.13:9000
      - DIND_IMAGE=${DIND_IMAGE:-docker:24-dind}
      - CYROID_RANGES_NETWORK=cyroid-ranges
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    container_name: cyroid-db
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.11
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=cyroid
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=cyroid
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: cyroid-redis
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.12
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    container_name: cyroid-minio
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.13
    volumes:
      - minio_data:/data
    environment:
      - MINIO_ROOT_USER=${MINIO_USER:-cyroid}
      - MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
    command: server /data --console-address ":9001"
    restart: unless-stopped

  traefik:
    image: traefik:v3.0
    container_name: cyroid-traefik
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.14
      cyroid-ranges:  # Needs to route to range DinD containers
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"  # Dashboard
    volumes:
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
      - ./traefik-dynamic:/etc/traefik/dynamic:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped

  worker:
    image: cyroid-worker:latest
    container_name: cyroid-worker
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.15
      cyroid-ranges:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DATABASE_URL=postgresql://cyroid:${DB_PASSWORD}@172.30.0.11:5432/cyroid
      - REDIS_URL=redis://172.30.0.12:6379
    depends_on:
      - db
      - redis
    restart: unless-stopped

  # === Optional: Frontend ===
  frontend:
    image: cyroid-frontend:latest
    container_name: cyroid-frontend
    networks:
      cyroid-mgmt:
        ipv4_address: 172.30.0.20
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=PathPrefix(`/`)"
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### Phase 7: Network Initialization Script

Create: `scripts/init-networks.sh`

```bash
#!/bin/bash
set -euo pipefail

echo "=== Initializing CYROID Networks ==="

# Create management network if not exists
if ! docker network inspect cyroid-mgmt &>/dev/null; then
    echo "Creating cyroid-mgmt network..."
    docker network create \
        --driver bridge \
        --subnet 172.30.0.0/24 \
        --gateway 172.30.0.1 \
        cyroid-mgmt
    echo "Created cyroid-mgmt (172.30.0.0/24)"
else
    echo "cyroid-mgmt network already exists"
fi

# Create ranges network if not exists
if ! docker network inspect cyroid-ranges &>/dev/null; then
    echo "Creating cyroid-ranges network..."
    docker network create \
        --driver bridge \
        --subnet 172.30.1.0/24 \
        --gateway 172.30.1.1 \
        cyroid-ranges
    echo "Created cyroid-ranges (172.30.1.0/24)"
else
    echo "cyroid-ranges network already exists"
fi

echo "=== Networks initialized ==="
docker network ls | grep cyroid
```

### Phase 8: Custom DinD Base Image (Optional)

Create: `docker/Dockerfile.dind-base`

```dockerfile
# Custom DinD image with optimizations for CYROID ranges
FROM docker:24-dind

# Install useful utilities
RUN apk add --no-cache \
    curl \
    jq \
    bash

# Configure Docker daemon for range use
RUN mkdir -p /etc/docker
COPY daemon.json /etc/docker/daemon.json

# Pre-create common directories
RUN mkdir -p /var/lib/docker

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s \
    CMD docker info > /dev/null 2>&1 || exit 1

EXPOSE 2375
```

Create: `docker/daemon.json`

```json
{
    "hosts": ["unix:///var/run/docker.sock", "tcp://0.0.0.0:2375"],
    "storage-driver": "overlay2",
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "live-restore": true
}
```

Build script: `scripts/build-dind-image.sh`

```bash
#!/bin/bash
set -euo pipefail

echo "Building custom CYROID DinD image..."

docker build \
    -t cyroid-dind:latest \
    -f docker/Dockerfile.dind-base \
    docker/

echo "Image built: cyroid-dind:latest"
echo "Update DIND_IMAGE in .env to use: cyroid-dind:latest"
```

---

## Summary of Changes

### New Files
- `backend/cyroid/services/dind_service.py` - DinD container management
- `scripts/init-networks.sh` - Network initialization
- `scripts/build-dind-image.sh` - Custom DinD image build
- `docker/Dockerfile.dind-base` - Custom DinD image
- `docker/daemon.json` - Docker daemon config for DinD

### Modified Files
- `backend/cyroid/services/docker_service.py` - Multi-client DinD support
- `backend/cyroid/services/range_service.py` - DinD lifecycle integration
- `backend/cyroid/config.py` - DinD and network settings
- `docker-compose.yml` - Dual network setup, socket mounts
- `.env` - New configuration variables

### Removed/Deprecated
- All IP offset/translation logic
- Network conflict detection code
- Single Docker client pattern for ranges
- `network_offset`, `physical_subnet`, `physical_ip` database columns
- Related environment variables and configuration

### Database Migrations
1. Add DinD tracking columns to ranges table
2. Remove deprecated offset-related columns

---

## Testing Checklist

### Unit Tests
- [ ] DinDService creates containers correctly
- [ ] DinDService deletes containers and volumes
- [ ] DockerService connects to correct DinD for each range
- [ ] DockerService creates networks with exact subnets
- [ ] DockerService creates VMs with exact IPs

### Integration Tests
- [ ] Two ranges with identical 10.0.1.0/24 networks deploy successfully
- [ ] VMs in each range get their exact specified IPs
- [ ] Ranges are completely network-isolated (can't ping across ranges)
- [ ] VNC console routes through Traefik to correct DinD
- [ ] Range deletion fully cleans up DinD container and volume

### End-to-End Tests
- [ ] Deploy range from blueprint with multiple networks
- [ ] Access VM console through web UI
- [ ] Stop/start/restart individual VMs
- [ ] Destroy range and verify cleanup
- [ ] Deploy same blueprint twice simultaneously

### Platform Tests
- [ ] Works on macOS with Docker Desktop
- [ ] Works on Linux with Docker Engine
- [ ] Works on Windows with Docker Desktop (if needed)

---

## Verification Commands

Quick test that isolation works:

```bash
# Create two test DinD containers
docker run -d --name test-range-1 --privileged --network cyroid-ranges docker:24-dind
docker run -d --name test-range-2 --privileged --network cyroid-ranges docker:24-dind

# Wait for Docker daemons
sleep 15

# Create identical networks in each
docker exec test-range-1 docker network create --subnet=10.0.1.0/24 internal
docker exec test-range-2 docker network create --subnet=10.0.1.0/24 internal

# Create containers with same IPs
docker exec test-range-1 docker run -d --net internal --ip 10.0.1.100 --name web alpine sleep infinity
docker exec test-range-2 docker run -d --net internal --ip 10.0.1.100 --name web alpine sleep infinity

# Verify IPs (both should show 10.0.1.100)
docker exec test-range-1 docker inspect web -f '{{.NetworkSettings.Networks.internal.IPAddress}}'
docker exec test-range-2 docker inspect web -f '{{.NetworkSettings.Networks.internal.IPAddress}}'

# Cleanup
docker rm -f test-range-1 test-range-2
```

---

## Rollback Plan

If issues arise, rollback steps:

1. Stop new range deployments
2. Keep existing DinD ranges running (they still work)
3. Revert code to previous version
4. Existing ranges continue to function
5. New ranges deploy with old method (if code supports both)

The DinD approach is additive - existing infrastructure isn't affected.
