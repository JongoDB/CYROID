# VM Library & DinD Isolation Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor VM Templates into VM Library with snapshot support, complete DinD isolation with working console access, and implement full range lifecycle management.

**Architecture:** Two interleaved tracks: (1) DinD enhancements for network isolation and console routing via a proxy container inside each DinD, (2) VM Library refactor allowing VMs to reference either base templates OR preconfigured snapshots. Both tracks share the enhanced image transfer mechanism.

**Tech Stack:** Python/FastAPI, SQLAlchemy/Alembic, React/TypeScript, Docker SDK, Traefik, pytest

---

## Phase 1: DinD Foundation Enhancements

### Task 1.1: Enhance Image Transfer with Progress Reporting

**Files:**
- Modify: `backend/cyroid/services/docker_service.py:2598-2680`
- Create: `backend/cyroid/schemas/docker.py` (new file for transfer schemas)
- Test: `backend/tests/services/test_docker_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_docker_service.py
import pytest
from unittest.mock import Mock, MagicMock, patch
from cyroid.services.docker_service import DockerService

class TestImageTransfer:
    """Tests for enhanced image transfer functionality."""

    @pytest.fixture
    def docker_service(self):
        with patch('cyroid.services.docker_service.docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            service = DockerService()
            return service, mock_client

    @pytest.mark.asyncio
    async def test_transfer_image_with_progress_callback(self, docker_service):
        """Transfer should report progress via callback."""
        service, mock_client = docker_service

        # Mock image with known size
        mock_image = MagicMock()
        mock_image.attrs = {'Size': 1024 * 1024 * 100}  # 100MB
        mock_client.images.get.return_value = mock_image

        # Track progress calls
        progress_updates = []
        def progress_callback(transferred: int, total: int, status: str):
            progress_updates.append({'transferred': transferred, 'total': total, 'status': status})

        # Mock range client
        mock_range_client = MagicMock()
        service._range_clients['test-range'] = mock_range_client
        mock_range_client.images.get.side_effect = Exception("not found")
        mock_range_client.images.load.return_value = [mock_image]

        # Execute transfer
        result = await service.transfer_image_to_dind(
            range_id='test-range',
            docker_url='tcp://172.30.1.1:2375',
            image='ubuntu:22.04',
            progress_callback=progress_callback
        )

        assert result is True
        assert len(progress_updates) >= 2  # At least start and complete
        assert progress_updates[0]['status'] == 'starting'
        assert progress_updates[-1]['status'] == 'complete'
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/services/test_docker_service.py::TestImageTransfer::test_transfer_image_with_progress_callback -v`
Expected: FAIL with "progress_callback" not recognized

**Step 3: Write minimal implementation**

```python
# backend/cyroid/services/docker_service.py
# Replace the transfer_image_to_dind method (around line 2598)

    async def transfer_image_to_dind(
        self,
        range_id: str,
        docker_url: str,
        image: str,
        pull_if_missing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> bool:
        """
        Transfer a Docker image from host to a DinD container with progress reporting.

        Args:
            range_id: Range identifier
            docker_url: DinD Docker URL (tcp://ip:port)
            image: Image name/tag to transfer
            pull_if_missing: If True, pull image to host if not found locally
            progress_callback: Optional callback(transferred_bytes, total_bytes, status)

        Returns:
            True if transfer succeeded, False otherwise
        """
        def report_progress(transferred: int, total: int, status: str):
            if progress_callback:
                try:
                    progress_callback(transferred, total, status)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        logger.info(f"Transferring image '{image}' to DinD for range {range_id}")
        report_progress(0, 0, 'starting')

        # Check if image exists on host
        try:
            host_image = self.client.images.get(image)
            image_size = host_image.attrs.get('Size', 0)
            logger.debug(f"Image '{image}' found on host ({image_size} bytes)")
            report_progress(0, image_size, 'found_on_host')
        except docker.errors.ImageNotFound:
            if pull_if_missing:
                logger.info(f"Image '{image}' not on host, pulling...")
                report_progress(0, 0, 'pulling_to_host')
                try:
                    host_image = self.client.images.pull(image)
                    image_size = host_image.attrs.get('Size', 0)
                    logger.info(f"Pulled '{image}' to host ({image_size} bytes)")
                    report_progress(image_size, image_size, 'pulled_to_host')
                except Exception as e:
                    logger.error(f"Failed to pull '{image}' to host: {e}")
                    report_progress(0, 0, 'error')
                    return False
            else:
                logger.error(f"Image '{image}' not found on host")
                report_progress(0, 0, 'error')
                return False

        try:
            # Get client for DinD
            range_client = self.get_range_client_sync(range_id, docker_url)

            # Check if image already exists in DinD
            try:
                range_client.images.get(image)
                logger.info(f"Image '{image}' already exists in DinD, skipping transfer")
                report_progress(image_size, image_size, 'already_exists')
                return True
            except docker.errors.ImageNotFound:
                pass  # Need to transfer

            # Export image from host and import to DinD
            logger.info(f"Streaming image '{image}' from host to DinD...")
            report_progress(0, image_size, 'transferring')

            # Get image as tar stream from host
            image_data = host_image.save(named=True)

            # Load into DinD - images.load accepts an iterator of bytes
            result = range_client.images.load(image_data)

            if result:
                loaded_images = [img.tags[0] if img.tags else img.id for img in result]
                logger.info(f"Successfully transferred to DinD: {loaded_images}")
            else:
                logger.info(f"Successfully transferred '{image}' to DinD")

            report_progress(image_size, image_size, 'complete')
            return True

        except Exception as e:
            logger.error(f"Error transferring image '{image}' to DinD: {e}")
            report_progress(0, image_size if 'image_size' in locals() else 0, 'error')
            return False
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/services/test_docker_service.py::TestImageTransfer::test_transfer_image_with_progress_callback -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/docker_service.py backend/tests/services/test_docker_service.py
git commit -m "feat: add progress callback to image transfer for DinD"
```

---

### Task 1.2: Add VNC Proxy Container for DinD Console Access

**Problem:** Traefik runs on the host but VMs are inside DinD containers. Traefik cannot directly route to containers inside DinD because they're in a separate Docker daemon.

**Solution:** Deploy a lightweight nginx proxy container inside each DinD that exposes VNC ports on the DinD's management IP, which Traefik CAN reach.

**Files:**
- Modify: `backend/cyroid/services/dind_service.py`
- Modify: `backend/cyroid/services/range_deployment_service.py`
- Create: `backend/cyroid/services/vnc_proxy_service.py`
- Test: `backend/tests/services/test_vnc_proxy_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_vnc_proxy_service.py
import pytest
from unittest.mock import MagicMock, patch
from cyroid.services.vnc_proxy_service import VNCProxyService

class TestVNCProxyService:
    """Tests for VNC proxy deployment inside DinD."""

    @pytest.fixture
    def vnc_proxy_service(self):
        mock_docker_service = MagicMock()
        return VNCProxyService(docker_service=mock_docker_service)

    @pytest.mark.asyncio
    async def test_deploy_vnc_proxy_creates_container(self, vnc_proxy_service):
        """VNC proxy should be deployed inside DinD with correct port mappings."""
        mock_range_client = MagicMock()
        vnc_proxy_service.docker_service.get_range_client_sync.return_value = mock_range_client

        # Mock container creation
        mock_container = MagicMock()
        mock_container.id = 'proxy-container-123'
        mock_range_client.containers.run.return_value = mock_container

        vm_ports = [
            {'vm_id': 'vm-1', 'hostname': 'dc01', 'vnc_port': 8006},
            {'vm_id': 'vm-2', 'hostname': 'web01', 'vnc_port': 6901},
        ]

        result = await vnc_proxy_service.deploy_vnc_proxy(
            range_id='range-123',
            docker_url='tcp://172.30.1.5:2375',
            dind_mgmt_ip='172.30.1.5',
            vm_ports=vm_ports
        )

        assert result['container_id'] == 'proxy-container-123'
        assert 'nginx' in mock_range_client.containers.run.call_args[1]['image']
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/services/test_vnc_proxy_service.py -v`
Expected: FAIL with "No module named 'cyroid.services.vnc_proxy_service'"

**Step 3: Create VNC proxy service**

```python
# backend/cyroid/services/vnc_proxy_service.py
"""VNC Proxy service for routing console access into DinD containers."""

import logging
from typing import List, Dict, Any, Optional
from cyroid.services.docker_service import DockerService

logger = logging.getLogger(__name__)

# Nginx config template for TCP stream proxying
NGINX_STREAM_CONFIG = """
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;

events {
    worker_connections 1024;
}

stream {
    log_format proxy '$remote_addr [$time_local] '
                     '$protocol $status $bytes_sent $bytes_received '
                     '$session_time "$upstream_addr"';
    access_log /var/log/nginx/access.log proxy;

%(upstreams)s

%(servers)s
}
"""

UPSTREAM_TEMPLATE = """
    upstream vnc_{vm_id_short} {{
        server {container_name}:{vnc_port};
    }}
"""

SERVER_TEMPLATE = """
    server {{
        listen {external_port};
        proxy_pass vnc_{vm_id_short};
        proxy_timeout 3600s;
        proxy_connect_timeout 60s;
    }}
"""


class VNCProxyService:
    """Manages VNC proxy containers inside DinD for console access."""

    # Base port for VNC proxy (inside DinD, exposed on management IP)
    VNC_PROXY_BASE_PORT = 15900

    def __init__(self, docker_service: DockerService):
        self.docker_service = docker_service

    async def deploy_vnc_proxy(
        self,
        range_id: str,
        docker_url: str,
        dind_mgmt_ip: str,
        vm_ports: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Deploy nginx-based VNC proxy inside DinD container.

        Args:
            range_id: Range identifier
            docker_url: DinD Docker daemon URL
            dind_mgmt_ip: Management IP of DinD container (reachable from host)
            vm_ports: List of dicts with vm_id, hostname, vnc_port, container_name

        Returns:
            Dict with container_id and port_mappings
        """
        logger.info(f"Deploying VNC proxy for range {range_id}")

        range_client = self.docker_service.get_range_client_sync(range_id, docker_url)

        # Generate nginx config
        upstreams = []
        servers = []
        port_mappings = {}

        for idx, vm_info in enumerate(vm_ports):
            vm_id_short = vm_info['vm_id'][:8]
            external_port = self.VNC_PROXY_BASE_PORT + idx

            upstreams.append(UPSTREAM_TEMPLATE.format(
                vm_id_short=vm_id_short,
                container_name=vm_info['container_name'],
                vnc_port=vm_info['vnc_port']
            ))

            servers.append(SERVER_TEMPLATE.format(
                external_port=external_port,
                vm_id_short=vm_id_short
            ))

            port_mappings[vm_info['vm_id']] = {
                'proxy_port': external_port,
                'proxy_host': dind_mgmt_ip,
                'original_port': vm_info['vnc_port'],
            }

        nginx_config = NGINX_STREAM_CONFIG % {
            'upstreams': '\n'.join(upstreams),
            'servers': '\n'.join(servers),
        }

        # Build port bindings for container
        port_bindings = {}
        for vm_id, mapping in port_mappings.items():
            port_bindings[f"{mapping['proxy_port']}/tcp"] = mapping['proxy_port']

        # Remove existing proxy if any
        await self.remove_vnc_proxy(range_id, docker_url)

        # Create proxy container
        container = range_client.containers.run(
            image='nginx:alpine',
            name=f'cyroid-vnc-proxy-{range_id[:8]}',
            detach=True,
            command=['sh', '-c', f'echo "{nginx_config}" > /etc/nginx/nginx.conf && nginx -g "daemon off;"'],
            ports=port_bindings,
            labels={
                'cyroid.range_id': range_id,
                'cyroid.component': 'vnc-proxy',
            },
            restart_policy={'Name': 'unless-stopped'},
        )

        logger.info(f"VNC proxy deployed for range {range_id}: {container.id[:12]}")

        return {
            'container_id': container.id,
            'port_mappings': port_mappings,
        }

    async def remove_vnc_proxy(self, range_id: str, docker_url: str) -> None:
        """Remove VNC proxy container from DinD."""
        range_client = self.docker_service.get_range_client_sync(range_id, docker_url)

        try:
            container = range_client.containers.get(f'cyroid-vnc-proxy-{range_id[:8]}')
            container.stop(timeout=5)
            container.remove(force=True)
            logger.info(f"Removed VNC proxy for range {range_id}")
        except Exception:
            pass  # Container doesn't exist

    async def update_vnc_proxy(
        self,
        range_id: str,
        docker_url: str,
        dind_mgmt_ip: str,
        vm_ports: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update VNC proxy with new VM list (redeploys container)."""
        return await self.deploy_vnc_proxy(range_id, docker_url, dind_mgmt_ip, vm_ports)

    def get_vnc_url_for_vm(
        self,
        vm_id: str,
        dind_mgmt_ip: str,
        port_mappings: Dict[str, Dict[str, Any]]
    ) -> Optional[str]:
        """Get the proxied VNC URL for a VM."""
        if vm_id not in port_mappings:
            return None

        mapping = port_mappings[vm_id]
        return f"http://{mapping['proxy_host']}:{mapping['proxy_port']}"
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/services/test_vnc_proxy_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/vnc_proxy_service.py backend/tests/services/test_vnc_proxy_service.py
git commit -m "feat: add VNC proxy service for DinD console access"
```

---

### Task 1.3: Wire VNC Proxy into Range Deployment

**Files:**
- Modify: `backend/cyroid/services/range_deployment_service.py`
- Modify: `backend/cyroid/api/vms.py` (VNC info endpoint)
- Modify: `backend/cyroid/models/range.py` (add vnc_proxy_mappings field)
- Test: `backend/tests/services/test_range_deployment_service.py`

**Step 1: Add vnc_proxy_mappings to Range model**

```python
# backend/cyroid/models/range.py
# Add this field after dind_docker_url (around line 50)

    # VNC proxy port mappings (JSON: {vm_id: {proxy_host, proxy_port}})
    vnc_proxy_mappings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

**Step 2: Create database migration**

Run: `cd /Users/JonWFH/jondev/CYROID && alembic revision --autogenerate -m "add vnc_proxy_mappings to range"`

**Step 3: Apply migration**

Run: `cd /Users/JonWFH/jondev/CYROID && alembic upgrade head`

**Step 4: Update range deployment service**

```python
# backend/cyroid/services/range_deployment_service.py
# Add import at top
from cyroid.services.vnc_proxy_service import VNCProxyService

# In RangeDeploymentService.__init__, add:
        self.vnc_proxy_service = VNCProxyService(docker_service)

# After VM creation loop (around line 220), add VNC proxy deployment:

        # Deploy VNC proxy for console access
        vm_ports = []
        for vm in vms:
            if vm.container_id:
                # Determine VNC port based on VM type
                vnc_port = 8006  # Default for QEMU/Windows
                if vm.template and vm.template.vm_type == VMType.CONTAINER:
                    vnc_port = 6901 if 'kasmweb' in (vm.template.base_image or '') else 3000

                vm_ports.append({
                    'vm_id': str(vm.id),
                    'hostname': vm.hostname,
                    'vnc_port': vnc_port,
                    'container_name': f'cyroid-{vm.hostname}-{str(vm.id)[:8]}',
                })

        if vm_ports:
            proxy_result = await self.vnc_proxy_service.deploy_vnc_proxy(
                range_id=str(range_id),
                docker_url=dind_docker_url,
                dind_mgmt_ip=dind_mgmt_ip,
                vm_ports=vm_ports,
            )
            db_range.vnc_proxy_mappings = proxy_result['port_mappings']
            db.commit()
```

**Step 5: Update VNC info endpoint to use proxy**

```python
# backend/cyroid/api/vms.py
# In get_vnc_info endpoint (around line 680), update to check for DinD proxy:

    # Check if range uses DinD isolation with VNC proxy
    range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
    if range_obj and range_obj.vnc_proxy_mappings:
        proxy_mapping = range_obj.vnc_proxy_mappings.get(str(vm.id))
        if proxy_mapping:
            return VNCInfoResponse(
                path=f"/vnc/{vm.id}",
                websocket_path="websockify",
                hostname=vm.hostname,
                proxy_host=proxy_mapping['proxy_host'],
                proxy_port=proxy_mapping['proxy_port'],
            )
```

**Step 6: Commit**

```bash
git add backend/cyroid/models/range.py backend/cyroid/services/range_deployment_service.py backend/cyroid/api/vms.py backend/alembic/versions/*.py
git commit -m "feat: wire VNC proxy into range deployment for DinD console access"
```

---

### Task 1.4: Implement iptables Isolation Inside DinD

**Files:**
- Modify: `backend/cyroid/services/dind_service.py`
- Test: `backend/tests/services/test_dind_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/services/test_dind_service.py
import pytest
from unittest.mock import MagicMock, patch

class TestDinDIptables:
    """Tests for iptables isolation inside DinD containers."""

    @pytest.mark.asyncio
    async def test_setup_network_isolation_in_dind(self):
        """Should apply iptables rules inside DinD container."""
        from cyroid.services.dind_service import DinDService

        mock_docker_service = MagicMock()
        mock_range_client = MagicMock()
        mock_docker_service.get_range_client_sync.return_value = mock_range_client

        service = DinDService(docker_service=mock_docker_service)

        # Mock exec_run for iptables commands
        mock_container = MagicMock()
        mock_container.exec_run.return_value = (0, b'')
        mock_range_client.containers.get.return_value = mock_container

        await service.setup_network_isolation_in_dind(
            range_id='range-123',
            docker_url='tcp://172.30.1.5:2375',
            networks=['lan', 'dmz'],
            allow_internet=['lan'],  # Only LAN can reach internet
        )

        # Verify iptables commands were executed
        exec_calls = mock_container.exec_run.call_args_list
        assert len(exec_calls) >= 2  # At least isolation rules
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/services/test_dind_service.py::TestDinDIptables -v`
Expected: FAIL

**Step 3: Implement iptables isolation in DinD**

```python
# backend/cyroid/services/dind_service.py
# Add this method to DinDService class

    async def setup_network_isolation_in_dind(
        self,
        range_id: str,
        docker_url: str,
        networks: List[str],
        allow_internet: Optional[List[str]] = None,
    ) -> None:
        """
        Apply iptables rules inside DinD container for network isolation.

        Args:
            range_id: Range identifier
            docker_url: DinD Docker daemon URL
            networks: List of network names in this range
            allow_internet: Networks that should have internet access (via DinD NAT)
        """
        allow_internet = allow_internet or []
        range_client = self.docker_service.get_range_client_sync(range_id, docker_url)

        # Get the DinD container itself (runs on host)
        dind_container_name = f"cyroid-dind-{range_id[:8]}"

        try:
            # Execute iptables inside the DinD container
            dind_container = self.docker_service.client.containers.get(dind_container_name)
        except Exception as e:
            logger.error(f"Cannot find DinD container {dind_container_name}: {e}")
            return

        # Apply isolation rules
        rules = []

        # Default: drop forwarding between range networks
        rules.append("iptables -P FORWARD DROP")

        # Allow established connections
        rules.append("iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT")

        # Allow traffic within each network (same bridge)
        for network in networks:
            rules.append(f"iptables -A FORWARD -i br-{network[:12]} -o br-{network[:12]} -j ACCEPT")

        # Allow internet for specified networks
        for network in allow_internet:
            rules.append(f"iptables -A FORWARD -i br-{network[:12]} -o eth0 -j ACCEPT")
            # NAT for outbound traffic
            rules.append(f"iptables -t nat -A POSTROUTING -s 10.0.0.0/8 -o eth0 -j MASQUERADE")

        # Execute rules
        for rule in rules:
            exit_code, output = dind_container.exec_run(rule, privileged=True)
            if exit_code != 0:
                logger.warning(f"iptables rule failed: {rule} -> {output}")

        logger.info(f"Applied network isolation rules for range {range_id}")

    async def teardown_network_isolation_in_dind(
        self,
        range_id: str,
    ) -> None:
        """Remove iptables rules (happens automatically when DinD container is destroyed)."""
        # No action needed - destroying DinD container removes all rules
        pass
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/services/test_dind_service.py::TestDinDIptables -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/services/dind_service.py backend/tests/services/test_dind_service.py
git commit -m "feat: implement iptables network isolation inside DinD containers"
```

---

### Task 1.5: Implement Full Range Lifecycle Endpoints

**Files:**
- Modify: `backend/cyroid/api/ranges.py`
- Modify: `backend/cyroid/services/range_deployment_service.py`
- Test: `backend/tests/api/test_ranges.py`

**Step 1: Write failing tests for lifecycle endpoints**

```python
# backend/tests/api/test_ranges.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

class TestRangeLifecycle:
    """Tests for range lifecycle with DinD."""

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, test_user_token):
        return {"Authorization": f"Bearer {test_user_token}"}

    def test_stop_range_stops_dind_containers(self, client, auth_headers, test_range):
        """Stop should stop all containers inside DinD."""
        response = client.post(
            f"/api/v1/ranges/{test_range.id}/stop",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()['status'] == 'stopped'

    def test_start_range_starts_dind_containers(self, client, auth_headers, test_range):
        """Start should start all containers inside DinD."""
        response = client.post(
            f"/api/v1/ranges/{test_range.id}/start",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()['status'] == 'running'

    def test_delete_range_destroys_dind(self, client, auth_headers, test_range):
        """Delete should completely destroy DinD container."""
        response = client.delete(
            f"/api/v1/ranges/{test_range.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
```

**Step 2: Update ranges.py with DinD-aware lifecycle**

```python
# backend/cyroid/api/ranges.py
# Update the stop_range endpoint (around line 465)

@router.post("/{range_id}/stop", response_model=RangeResponse)
async def stop_range(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker: DockerService = Depends(get_docker_service),
):
    """Stop a running range (preserves DinD container but stops VMs)."""
    db_range = db.query(Range).filter(Range.id == range_id).first()
    if not db_range:
        raise HTTPException(status_code=404, detail="Range not found")

    if db_range.status != RangeStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Range is not running")

    # Stop VMs inside DinD
    if db_range.dind_container_id and db_range.dind_docker_url:
        range_client = docker.get_range_client_sync(str(range_id), db_range.dind_docker_url)

        # Stop all range containers
        for vm in db_range.vms:
            if vm.container_id:
                try:
                    container = range_client.containers.get(vm.container_id)
                    container.stop(timeout=30)
                    vm.status = VMStatus.STOPPED
                except Exception as e:
                    logger.warning(f"Failed to stop VM {vm.id}: {e}")

        # Stop VyOS router
        if db_range.router and db_range.router.container_id:
            try:
                container = range_client.containers.get(db_range.router.container_id)
                container.stop(timeout=30)
            except Exception:
                pass

    db_range.status = RangeStatus.STOPPED
    db_range.stopped_at = datetime.utcnow()
    db.commit()

    return db_range


@router.post("/{range_id}/start", response_model=RangeResponse)
async def start_range(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker: DockerService = Depends(get_docker_service),
):
    """Start a stopped range (restarts VMs inside existing DinD)."""
    db_range = db.query(Range).filter(Range.id == range_id).first()
    if not db_range:
        raise HTTPException(status_code=404, detail="Range not found")

    if db_range.status != RangeStatus.STOPPED:
        raise HTTPException(status_code=400, detail="Range is not stopped")

    if not db_range.dind_container_id:
        raise HTTPException(status_code=400, detail="Range has no DinD container - redeploy required")

    # Ensure DinD container is running
    try:
        dind_container = docker.client.containers.get(db_range.dind_container_id)
        if dind_container.status != 'running':
            dind_container.start()
            await asyncio.sleep(3)  # Wait for Docker daemon
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start DinD: {e}")

    # Start VMs inside DinD
    range_client = docker.get_range_client_sync(str(range_id), db_range.dind_docker_url)

    # Start VyOS router first
    if db_range.router and db_range.router.container_id:
        try:
            container = range_client.containers.get(db_range.router.container_id)
            container.start()
        except Exception as e:
            logger.warning(f"Failed to start router: {e}")

    # Start all VMs
    for vm in db_range.vms:
        if vm.container_id:
            try:
                container = range_client.containers.get(vm.container_id)
                container.start()
                vm.status = VMStatus.RUNNING
            except Exception as e:
                logger.warning(f"Failed to start VM {vm.id}: {e}")
                vm.status = VMStatus.ERROR

    db_range.status = RangeStatus.RUNNING
    db_range.started_at = datetime.utcnow()
    db.commit()

    return db_range


@router.delete("/{range_id}", response_model=dict)
async def delete_range(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker: DockerService = Depends(get_docker_service),
    dind_service: DinDService = Depends(get_dind_service),
):
    """Completely delete a range including DinD container."""
    db_range = db.query(Range).filter(Range.id == range_id).first()
    if not db_range:
        raise HTTPException(status_code=404, detail="Range not found")

    # Destroy DinD container (automatically cleans up all VMs, networks inside)
    if db_range.dind_container_id:
        try:
            await dind_service.destroy_dind_container(str(range_id))
        except Exception as e:
            logger.warning(f"Failed to destroy DinD for range {range_id}: {e}")

    # Clear Docker client cache
    docker.close_range_client(str(range_id))

    # Delete database record
    db.delete(db_range)
    db.commit()

    return {"status": "deleted", "range_id": str(range_id)}
```

**Step 3: Run tests**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/api/test_ranges.py::TestRangeLifecycle -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/cyroid/api/ranges.py backend/tests/api/test_ranges.py
git commit -m "feat: implement full range lifecycle (start/stop/delete) with DinD support"
```

---

### Task 1.6: Delete LXD Plan Document

**Files:**
- Delete: `docs/plans/lxd-isolation-refactor.md`

**Step 1: Delete the file**

```bash
rm /Users/JonWFH/jondev/CYROID/docs/plans/lxd-isolation-refactor.md
```

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove obsolete LXD isolation plan (using DinD instead)"
```

---

## Phase 2: VM Library Refactor

### Task 2.1: Update Snapshot Model for Global Visibility

**Files:**
- Modify: `backend/cyroid/models/snapshot.py`
- Create migration

**Step 1: Update Snapshot model**

```python
# backend/cyroid/models/snapshot.py
from typing import Optional, List
from uuid import UUID
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cyroid.models.base import Base, TimestampMixin, UUIDMixin


class Snapshot(Base, UUIDMixin, TimestampMixin):
    """
    VM Snapshot stored as Docker image.

    Snapshots can be used as the source for new VMs, allowing preconfigured
    environments (DC, web server, etc.) to be quickly deployed.
    """
    __tablename__ = "snapshots"

    # Source VM (optional - can be null for imported snapshots)
    vm_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vms.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Docker image reference
    docker_image_id: Mapped[Optional[str]] = mapped_column(String(128))
    docker_image_tag: Mapped[Optional[str]] = mapped_column(String(255))  # e.g., cyroid-snapshot:dc01-v1

    # Metadata for VM creation (copied from source VM's template)
    os_type: Mapped[Optional[str]] = mapped_column(String(20))  # windows, linux, network, custom
    vm_type: Mapped[Optional[str]] = mapped_column(String(20))  # container, linux_vm, windows_vm
    default_cpu: Mapped[int] = mapped_column(Integer, default=2)
    default_ram_mb: Mapped[int] = mapped_column(Integer, default=4096)
    default_disk_gb: Mapped[int] = mapped_column(Integer, default=40)

    # Display configuration
    display_type: Mapped[Optional[str]] = mapped_column(String(20))  # desktop, headless
    vnc_port: Mapped[int] = mapped_column(Integer, default=8006)

    # Global visibility (all users can see and use)
    is_global: Mapped[bool] = mapped_column(Boolean, default=True)

    # Tags for categorization
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Relationships
    vm = relationship("VM", back_populates="snapshots", foreign_keys=[vm_id])
    # VMs created from this snapshot
    created_vms = relationship(
        "VM",
        back_populates="source_snapshot",
        foreign_keys="VM.snapshot_id"
    )
```

**Step 2: Create migration**

Run: `cd /Users/JonWFH/jondev/CYROID && alembic revision --autogenerate -m "enhance snapshot model for vm library"`

**Step 3: Apply migration**

Run: `cd /Users/JonWFH/jondev/CYROID && alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/cyroid/models/snapshot.py backend/alembic/versions/*.py
git commit -m "feat: enhance Snapshot model with metadata for VM Library"
```

---

### Task 2.2: Update VM Model for Snapshot Support

**Files:**
- Modify: `backend/cyroid/models/vm.py`
- Create migration

**Step 1: Update VM model**

```python
# backend/cyroid/models/vm.py
# Make template_id optional and add snapshot_id
# Around line 25, change:

    # Source: either template OR snapshot (mutually exclusive)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("vm_templates.id"), nullable=True
    )
    snapshot_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("snapshots.id"), nullable=True
    )

# Add relationship around line 95:
    source_snapshot = relationship(
        "Snapshot",
        back_populates="created_vms",
        foreign_keys=[snapshot_id]
    )
```

**Step 2: Create migration**

Run: `cd /Users/JonWFH/jondev/CYROID && alembic revision --autogenerate -m "add snapshot_id to vm model"`

**Step 3: Apply migration**

Run: `cd /Users/JonWFH/jondev/CYROID && alembic upgrade head`

**Step 4: Commit**

```bash
git add backend/cyroid/models/vm.py backend/alembic/versions/*.py
git commit -m "feat: add snapshot_id to VM model for Library support"
```

---

### Task 2.3: Update VM Schemas with Validation

**Files:**
- Modify: `backend/cyroid/schemas/vm.py`
- Test: `backend/tests/schemas/test_vm.py`

**Step 1: Write failing test**

```python
# backend/tests/schemas/test_vm.py
import pytest
from pydantic import ValidationError
from cyroid.schemas.vm import VMCreate

class TestVMCreateValidation:
    """Tests for VM creation schema validation."""

    def test_requires_template_or_snapshot(self):
        """Must provide exactly one of template_id or snapshot_id."""
        # Neither provided - should fail
        with pytest.raises(ValidationError) as exc_info:
            VMCreate(
                range_id="00000000-0000-0000-0000-000000000001",
                network_id="00000000-0000-0000-0000-000000000002",
                hostname="test-vm",
                ip_address="10.0.1.10",
            )
        assert "template_id or snapshot_id" in str(exc_info.value).lower()

    def test_rejects_both_template_and_snapshot(self):
        """Cannot provide both template_id and snapshot_id."""
        with pytest.raises(ValidationError) as exc_info:
            VMCreate(
                range_id="00000000-0000-0000-0000-000000000001",
                network_id="00000000-0000-0000-0000-000000000002",
                template_id="00000000-0000-0000-0000-000000000003",
                snapshot_id="00000000-0000-0000-0000-000000000004",
                hostname="test-vm",
                ip_address="10.0.1.10",
            )
        assert "cannot specify both" in str(exc_info.value).lower()

    def test_accepts_template_only(self):
        """Should accept template_id without snapshot_id."""
        vm = VMCreate(
            range_id="00000000-0000-0000-0000-000000000001",
            network_id="00000000-0000-0000-0000-000000000002",
            template_id="00000000-0000-0000-0000-000000000003",
            hostname="test-vm",
            ip_address="10.0.1.10",
        )
        assert vm.template_id is not None
        assert vm.snapshot_id is None

    def test_accepts_snapshot_only(self):
        """Should accept snapshot_id without template_id."""
        vm = VMCreate(
            range_id="00000000-0000-0000-0000-000000000001",
            network_id="00000000-0000-0000-0000-000000000002",
            snapshot_id="00000000-0000-0000-0000-000000000004",
            hostname="test-vm",
            ip_address="10.0.1.10",
        )
        assert vm.template_id is None
        assert vm.snapshot_id is not None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/schemas/test_vm.py -v`
Expected: FAIL

**Step 3: Update VM schema**

```python
# backend/cyroid/schemas/vm.py
from pydantic import field_validator, model_validator
from typing import Optional
from uuid import UUID

class VMCreate(VMBase):
    range_id: UUID
    network_id: UUID
    template_id: Optional[UUID] = None  # Changed from required
    snapshot_id: Optional[UUID] = None  # New field

    # ... rest of fields ...

    @model_validator(mode='after')
    def check_source(self) -> 'VMCreate':
        """Ensure exactly one of template_id or snapshot_id is provided."""
        has_template = self.template_id is not None
        has_snapshot = self.snapshot_id is not None

        if has_template and has_snapshot:
            raise ValueError("Cannot specify both template_id and snapshot_id")
        if not has_template and not has_snapshot:
            raise ValueError("Must provide either template_id or snapshot_id")

        return self
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/schemas/test_vm.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/cyroid/schemas/vm.py backend/tests/schemas/test_vm.py
git commit -m "feat: add snapshot_id to VM schema with mutual exclusivity validation"
```

---

### Task 2.4: Update VM API for Snapshot Support

**Files:**
- Modify: `backend/cyroid/api/vms.py`
- Test: `backend/tests/api/test_vms.py`

**Step 1: Update create_vm endpoint**

```python
# backend/cyroid/api/vms.py
# In create_vm function (around line 153), update validation logic:

    # Validate source (template OR snapshot)
    template = None
    snapshot = None

    if vm_data.template_id:
        template = db.query(VMTemplate).filter(VMTemplate.id == vm_data.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {vm_data.template_id}")
    elif vm_data.snapshot_id:
        snapshot = db.query(Snapshot).filter(Snapshot.id == vm_data.snapshot_id).first()
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Snapshot not found: {vm_data.snapshot_id}")
        if not snapshot.docker_image_id:
            raise HTTPException(status_code=400, detail="Snapshot has no Docker image")

    # Set defaults from source
    if template:
        cpu = vm_data.cpu or template.default_cpu
        ram_mb = vm_data.ram_mb or template.default_ram_mb
        disk_gb = vm_data.disk_gb or template.default_disk_gb
    else:  # snapshot
        cpu = vm_data.cpu or snapshot.default_cpu
        ram_mb = vm_data.ram_mb or snapshot.default_ram_mb
        disk_gb = vm_data.disk_gb or snapshot.default_disk_gb
```

**Step 2: Update start_vm endpoint**

```python
# backend/cyroid/api/vms.py
# In start_vm function (around line 297), handle snapshot source:

    # Get source configuration
    if vm.template_id:
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="VM's template not found")
        base_image = template.base_image
        os_type = template.os_type
        vm_type = template.vm_type
    elif vm.snapshot_id:
        snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first()
        if not snapshot:
            raise HTTPException(status_code=404, detail="VM's snapshot not found")
        base_image = snapshot.docker_image_tag or snapshot.docker_image_id
        os_type = OSType(snapshot.os_type) if snapshot.os_type else OSType.LINUX
        vm_type = VMType(snapshot.vm_type) if snapshot.vm_type else VMType.CONTAINER
    else:
        raise HTTPException(status_code=400, detail="VM has no template or snapshot")
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/vms.py
git commit -m "feat: update VM API to support snapshot-based VM creation"
```

---

### Task 2.5: Add Pre-Deployment Validation

**Files:**
- Create: `backend/cyroid/services/deployment_validator.py`
- Modify: `backend/cyroid/api/ranges.py`
- Test: `backend/tests/services/test_deployment_validator.py`

**Step 1: Create deployment validator service**

```python
# backend/cyroid/services/deployment_validator.py
"""Pre-deployment validation for ranges."""

import logging
import platform
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from cyroid.models import Range, VM, VMTemplate, Snapshot
from cyroid.services.docker_service import DockerService

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    message: str
    severity: str = "error"  # error, warning, info
    vm_id: Optional[str] = None


@dataclass
class DeploymentValidation:
    """Complete deployment validation result."""
    valid: bool
    results: List[ValidationResult]

    @property
    def errors(self) -> List[ValidationResult]:
        return [r for r in self.results if r.severity == "error" and not r.valid]

    @property
    def warnings(self) -> List[ValidationResult]:
        return [r for r in self.results if r.severity == "warning"]


class DeploymentValidator:
    """Validates range configuration before deployment."""

    def __init__(self, db: Session, docker_service: DockerService):
        self.db = db
        self.docker = docker_service

    async def validate_range(self, range_id: UUID) -> DeploymentValidation:
        """Run all validation checks for a range."""
        results = []

        db_range = self.db.query(Range).filter(Range.id == range_id).first()
        if not db_range:
            return DeploymentValidation(
                valid=False,
                results=[ValidationResult(False, "Range not found", "error")]
            )

        # Run all validators
        results.extend(await self._validate_images_exist(db_range))
        results.extend(await self._validate_architecture(db_range))
        results.extend(await self._validate_disk_space(db_range))
        results.extend(self._validate_network_config(db_range))

        valid = all(r.valid for r in results if r.severity == "error")

        return DeploymentValidation(valid=valid, results=results)

    async def _validate_images_exist(self, db_range: Range) -> List[ValidationResult]:
        """Check that all required Docker images exist."""
        results = []

        for vm in db_range.vms:
            if vm.template_id:
                template = self.db.query(VMTemplate).filter(
                    VMTemplate.id == vm.template_id
                ).first()
                if not template:
                    results.append(ValidationResult(
                        False, f"Template not found for VM {vm.hostname}",
                        "error", str(vm.id)
                    ))
                    continue
                image = template.base_image
            elif vm.snapshot_id:
                snapshot = self.db.query(Snapshot).filter(
                    Snapshot.id == vm.snapshot_id
                ).first()
                if not snapshot:
                    results.append(ValidationResult(
                        False, f"Snapshot not found for VM {vm.hostname}",
                        "error", str(vm.id)
                    ))
                    continue
                if not snapshot.docker_image_id:
                    results.append(ValidationResult(
                        False, f"Snapshot {snapshot.name} has no Docker image",
                        "error", str(vm.id)
                    ))
                    continue
                image = snapshot.docker_image_tag or snapshot.docker_image_id
            else:
                results.append(ValidationResult(
                    False, f"VM {vm.hostname} has no template or snapshot",
                    "error", str(vm.id)
                ))
                continue

            # Check if image exists locally
            try:
                self.docker.client.images.get(image)
                results.append(ValidationResult(
                    True, f"Image {image} found for {vm.hostname}",
                    "info", str(vm.id)
                ))
            except Exception:
                # Image not local - will be pulled during deployment
                results.append(ValidationResult(
                    True, f"Image {image} will be pulled for {vm.hostname}",
                    "warning", str(vm.id)
                ))

        return results

    async def _validate_architecture(self, db_range: Range) -> List[ValidationResult]:
        """Check architecture compatibility."""
        results = []
        host_arch = platform.machine()

        for vm in db_range.vms:
            if vm.template_id:
                template = self.db.query(VMTemplate).filter(
                    VMTemplate.id == vm.template_id
                ).first()
                if template and template.native_arch:
                    if template.native_arch != 'both' and template.native_arch != host_arch:
                        if host_arch == 'arm64' and template.native_arch == 'x86_64':
                            results.append(ValidationResult(
                                True,
                                f"VM {vm.hostname} will run under x86_64 emulation (slower)",
                                "warning", str(vm.id)
                            ))
                        else:
                            results.append(ValidationResult(
                                False,
                                f"VM {vm.hostname} requires {template.native_arch} but host is {host_arch}",
                                "error", str(vm.id)
                            ))

        return results

    async def _validate_disk_space(self, db_range: Range) -> List[ValidationResult]:
        """Check sufficient disk space."""
        results = []

        # Calculate total required space
        total_gb = sum(vm.disk_gb or 20 for vm in db_range.vms)

        # Check available space
        try:
            disk_usage = shutil.disk_usage("/var/lib/docker")
            available_gb = disk_usage.free / (1024 ** 3)

            if available_gb < total_gb * 1.2:  # 20% buffer
                results.append(ValidationResult(
                    False,
                    f"Insufficient disk space: {available_gb:.1f}GB available, {total_gb}GB required",
                    "error"
                ))
            else:
                results.append(ValidationResult(
                    True,
                    f"Disk space OK: {available_gb:.1f}GB available, {total_gb}GB required",
                    "info"
                ))
        except Exception as e:
            results.append(ValidationResult(
                True, f"Could not check disk space: {e}",
                "warning"
            ))

        return results

    def _validate_network_config(self, db_range: Range) -> List[ValidationResult]:
        """Validate network configuration."""
        results = []

        # Check for duplicate IPs
        ip_map = {}
        for vm in db_range.vms:
            key = (str(vm.network_id), vm.ip_address)
            if key in ip_map:
                results.append(ValidationResult(
                    False,
                    f"Duplicate IP {vm.ip_address}: {vm.hostname} and {ip_map[key]}",
                    "error", str(vm.id)
                ))
            else:
                ip_map[key] = vm.hostname

        if not results:
            results.append(ValidationResult(
                True, "Network configuration valid",
                "info"
            ))

        return results
```

**Step 2: Add validation endpoint to ranges API**

```python
# backend/cyroid/api/ranges.py
# Add new endpoint before deploy endpoint

@router.get("/{range_id}/validate", response_model=dict)
async def validate_range_deployment(
    range_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker: DockerService = Depends(get_docker_service),
):
    """Validate range configuration before deployment."""
    from cyroid.services.deployment_validator import DeploymentValidator

    validator = DeploymentValidator(db, docker)
    result = await validator.validate_range(range_id)

    return {
        "valid": result.valid,
        "errors": [{"message": r.message, "vm_id": r.vm_id} for r in result.errors],
        "warnings": [{"message": r.message, "vm_id": r.vm_id} for r in result.warnings],
    }
```

**Step 3: Commit**

```bash
git add backend/cyroid/services/deployment_validator.py backend/cyroid/api/ranges.py
git commit -m "feat: add pre-deployment validation for ranges"
```

---

### Task 2.6: Rename Templates Page to VM Library

**Files:**
- Rename: `frontend/src/pages/Templates.tsx` → `frontend/src/pages/VMLibrary.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`

**Step 1: Rename and update Templates page**

```bash
mv frontend/src/pages/Templates.tsx frontend/src/pages/VMLibrary.tsx
```

**Step 2: Update component name and add snapshot section**

```typescript
// frontend/src/pages/VMLibrary.tsx
// Change the component name and add snapshots tab

export default function VMLibrary() {
  const [activeTab, setActiveTab] = useState<'snapshots' | 'base-images'>('snapshots')
  // ... rest of state ...

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">VM Library</h1>
          <p className="text-gray-400 mt-1">
            Manage preconfigured snapshots and base OS images
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-700">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('snapshots')}
            className={clsx(
              'py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'snapshots'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            )}
          >
            Snapshots
          </button>
          <button
            onClick={() => setActiveTab('base-images')}
            className={clsx(
              'py-4 px-1 border-b-2 font-medium text-sm',
              activeTab === 'base-images'
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            )}
          >
            Base OS Images
          </button>
        </nav>
      </div>

      {/* Content based on active tab */}
      {activeTab === 'snapshots' ? (
        <SnapshotsSection />
      ) : (
        <BaseImagesSection templates={templates} />
      )}
    </div>
  )
}
```

**Step 3: Update App.tsx route**

```typescript
// frontend/src/App.tsx
// Change the import and route
import VMLibrary from './pages/VMLibrary'

// Update route (around line 80)
<Route path="/vm-library" element={<VMLibrary />} />
```

**Step 4: Update Sidebar**

```typescript
// frontend/src/components/layout/Sidebar.tsx
// Change the link text and path
{ name: 'VM Library', href: '/vm-library', icon: Database },
```

**Step 5: Commit**

```bash
git add frontend/src/pages/VMLibrary.tsx frontend/src/App.tsx frontend/src/components/layout/Sidebar.tsx
git rm frontend/src/pages/Templates.tsx
git commit -m "feat: rename Templates page to VM Library with snapshots focus"
```

---

### Task 2.7: Add Snapshot Selection to VM Creation

**Files:**
- Modify: `frontend/src/pages/RangeDetail.tsx`
- Modify: `frontend/src/services/api.ts`

**Step 1: Update VMCreate interface**

```typescript
// frontend/src/services/api.ts
// Update VMCreate interface (around line 315)

export interface VMCreate {
  range_id: string
  network_id: string
  template_id?: string  // Now optional
  snapshot_id?: string  // New optional field
  hostname: string
  ip_address: string
  // ... rest of fields ...
}
```

**Step 2: Update RangeDetail VM form**

```typescript
// frontend/src/pages/RangeDetail.tsx
// Add state for source type and snapshot selection

const [vmSourceType, setVmSourceType] = useState<'template' | 'snapshot'>('template')
const [availableSnapshots, setAvailableSnapshots] = useState<Snapshot[]>([])

// Fetch snapshots on mount
useEffect(() => {
  const fetchSnapshots = async () => {
    try {
      const response = await snapshotsApi.list()
      setAvailableSnapshots(response.data)
    } catch (err) {
      console.error('Failed to fetch snapshots:', err)
    }
  }
  fetchSnapshots()
}, [])

// Update VM form state
const [vmForm, setVmForm] = useState<Partial<VMCreate>>({
  hostname: '',
  ip_address: '',
  network_id: '',
  template_id: '',
  snapshot_id: undefined,  // New field
  // ... rest ...
})

// Add source type toggle in the form JSX
<div className="mb-4">
  <label className="block text-sm font-medium text-gray-300 mb-2">
    Create from
  </label>
  <div className="flex space-x-4">
    <label className="flex items-center">
      <input
        type="radio"
        value="template"
        checked={vmSourceType === 'template'}
        onChange={() => {
          setVmSourceType('template')
          setVmForm({ ...vmForm, snapshot_id: undefined })
        }}
        className="mr-2"
      />
      Base Template
    </label>
    <label className="flex items-center">
      <input
        type="radio"
        value="snapshot"
        checked={vmSourceType === 'snapshot'}
        onChange={() => {
          setVmSourceType('snapshot')
          setVmForm({ ...vmForm, template_id: undefined })
        }}
        className="mr-2"
      />
      Library Snapshot
    </label>
  </div>
</div>

{/* Conditionally show template or snapshot selector */}
{vmSourceType === 'template' ? (
  <select
    value={vmForm.template_id || ''}
    onChange={(e) => setVmForm({ ...vmForm, template_id: e.target.value })}
    className="..."
  >
    <option value="">Select template...</option>
    {templates.map((t) => (
      <option key={t.id} value={t.id}>{t.name}</option>
    ))}
  </select>
) : (
  <select
    value={vmForm.snapshot_id || ''}
    onChange={(e) => setVmForm({ ...vmForm, snapshot_id: e.target.value })}
    className="..."
  >
    <option value="">Select snapshot...</option>
    {availableSnapshots.map((s) => (
      <option key={s.id} value={s.id}>{s.name}</option>
    ))}
  </select>
)}
```

**Step 3: Update handleCreateVm**

```typescript
// frontend/src/pages/RangeDetail.tsx
// Update the submit handler

const handleCreateVm = async (e: React.FormEvent) => {
  e.preventDefault()

  const vmData: VMCreate = {
    range_id: id!,
    network_id: vmForm.network_id!,
    hostname: vmForm.hostname!,
    ip_address: vmForm.ip_address!,
    cpu: vmForm.cpu || 2,
    ram_mb: vmForm.ram_mb || 2048,
    disk_gb: vmForm.disk_gb || 20,
    // Conditionally include template_id or snapshot_id
    ...(vmSourceType === 'template'
      ? { template_id: vmForm.template_id! }
      : { snapshot_id: vmForm.snapshot_id! }
    ),
  }

  await vmsApi.create(vmData)
  // ... rest of handler ...
}
```

**Step 4: Commit**

```bash
git add frontend/src/pages/RangeDetail.tsx frontend/src/services/api.ts
git commit -m "feat: add snapshot selection to VM creation in range builder"
```

---

### Task 2.8: Add Promote to Library Feature in Image Cache

**Files:**
- Modify: `backend/cyroid/api/cache.py`
- Modify: `frontend/src/pages/ImageCache.tsx`

**Step 1: Add promote endpoint**

```python
# backend/cyroid/api/cache.py
# Add new endpoint

@router.post("/promote-to-library", response_model=SnapshotResponse)
async def promote_image_to_library(
    image_name: str = Body(...),
    name: str = Body(...),
    description: str = Body(None),
    os_type: str = Body("linux"),
    vm_type: str = Body("container"),
    default_cpu: int = Body(2),
    default_ram_mb: int = Body(4096),
    default_disk_gb: int = Body(40),
    tags: List[str] = Body(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    docker: DockerService = Depends(get_docker_service),
):
    """Promote a cached Docker image to the VM Library as a snapshot."""
    # Verify image exists
    try:
        image = docker.client.images.get(image_name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Image not found: {image_name}")

    # Create snapshot record
    snapshot = Snapshot(
        name=name,
        description=description,
        docker_image_id=image.id,
        docker_image_tag=image_name,
        os_type=os_type,
        vm_type=vm_type,
        default_cpu=default_cpu,
        default_ram_mb=default_ram_mb,
        default_disk_gb=default_disk_gb,
        is_global=True,
        tags=tags,
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot
```

**Step 2: Add promote button in ImageCache.tsx**

```typescript
// frontend/src/pages/ImageCache.tsx
// Add promote modal and handler

const [promoteModal, setPromoteModal] = useState<{
  show: boolean
  imageName: string
}>({ show: false, imageName: '' })

const handlePromoteToLibrary = async (formData: PromoteFormData) => {
  try {
    await cacheApi.promoteToLibrary({
      image_name: promoteModal.imageName,
      ...formData,
    })
    toast.success('Image promoted to VM Library')
    setPromoteModal({ show: false, imageName: '' })
  } catch (err) {
    toast.error('Failed to promote image')
  }
}

// Add button next to each Docker image in the list
<button
  onClick={() => setPromoteModal({ show: true, imageName: image.name })}
  className="text-green-400 hover:text-green-300"
  title="Promote to VM Library"
>
  <Plus className="w-4 h-4" />
</button>
```

**Step 3: Commit**

```bash
git add backend/cyroid/api/cache.py frontend/src/pages/ImageCache.tsx
git commit -m "feat: add promote-to-library feature for cached images"
```

---

## Phase 3: Integration Testing

### Task 3.1: Create DinD Integration Tests

**Files:**
- Create: `backend/tests/integration/test_dind_deployment.py`

```python
# backend/tests/integration/test_dind_deployment.py
"""Integration tests for DinD-based range deployment."""

import pytest
import asyncio
from uuid import uuid4

from cyroid.services.docker_service import DockerService
from cyroid.services.dind_service import DinDService
from cyroid.services.range_deployment_service import RangeDeploymentService


@pytest.fixture
def docker_service():
    return DockerService()


@pytest.fixture
def dind_service(docker_service):
    return DinDService(docker_service)


class TestDinDDeployment:
    """Integration tests for DinD deployment flow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_and_destroy_dind_container(self, dind_service):
        """Should create and destroy DinD container."""
        range_id = str(uuid4())

        # Create
        result = await dind_service.create_dind_container(range_id)
        assert result['container_id'] is not None
        assert result['docker_url'].startswith('tcp://')

        # Verify container exists
        container = dind_service.docker_service.client.containers.get(
            result['container_id']
        )
        assert container.status == 'running'

        # Destroy
        await dind_service.destroy_dind_container(range_id)

        # Verify container removed
        with pytest.raises(Exception):
            dind_service.docker_service.client.containers.get(
                result['container_id']
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_two_ranges_same_subnet_no_conflict(self, dind_service, docker_service):
        """Two ranges with identical subnets should not conflict."""
        range1_id = str(uuid4())
        range2_id = str(uuid4())
        subnet = "10.0.1.0/24"

        try:
            # Create two DinD containers
            result1 = await dind_service.create_dind_container(range1_id)
            result2 = await dind_service.create_dind_container(range2_id)

            # Create same network in both DinD containers
            client1 = docker_service.get_range_client_sync(
                range1_id, result1['docker_url']
            )
            client2 = docker_service.get_range_client_sync(
                range2_id, result2['docker_url']
            )

            # Both should succeed without conflict
            net1 = client1.networks.create("lan", driver="bridge", ipam={
                'Config': [{'Subnet': subnet}]
            })
            net2 = client2.networks.create("lan", driver="bridge", ipam={
                'Config': [{'Subnet': subnet}]
            })

            assert net1.name == "lan"
            assert net2.name == "lan"

        finally:
            # Cleanup
            await dind_service.destroy_dind_container(range1_id)
            await dind_service.destroy_dind_container(range2_id)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_image_transfer_to_dind(self, docker_service, dind_service):
        """Should transfer image from host to DinD."""
        range_id = str(uuid4())

        try:
            # Create DinD
            result = await dind_service.create_dind_container(range_id)

            # Pull test image to host
            docker_service.client.images.pull("alpine:latest")

            # Transfer to DinD
            progress_updates = []
            success = await docker_service.transfer_image_to_dind(
                range_id=range_id,
                docker_url=result['docker_url'],
                image="alpine:latest",
                progress_callback=lambda t, total, s: progress_updates.append(s)
            )

            assert success is True
            assert 'complete' in progress_updates

            # Verify image exists in DinD
            range_client = docker_service.get_range_client_sync(
                range_id, result['docker_url']
            )
            image = range_client.images.get("alpine:latest")
            assert image is not None

        finally:
            await dind_service.destroy_dind_container(range_id)
```

**Step 1: Run integration tests**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/integration/test_dind_deployment.py -v -m integration`

**Step 2: Commit**

```bash
git add backend/tests/integration/test_dind_deployment.py
git commit -m "test: add DinD deployment integration tests"
```

---

### Task 3.2: Create VM Library Integration Tests

**Files:**
- Create: `backend/tests/integration/test_vm_library.py`

```python
# backend/tests/integration/test_vm_library.py
"""Integration tests for VM Library (snapshot-based VM creation)."""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient


class TestVMLibrary:
    """Integration tests for VM Library workflow."""

    @pytest.mark.integration
    def test_create_vm_from_snapshot(self, client, auth_headers, test_range, test_snapshot):
        """Should create VM from snapshot instead of template."""
        response = client.post(
            "/api/v1/vms",
            headers=auth_headers,
            json={
                "range_id": str(test_range.id),
                "network_id": str(test_range.networks[0].id),
                "snapshot_id": str(test_snapshot.id),
                "hostname": "vm-from-snapshot",
                "ip_address": "10.0.1.50",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['snapshot_id'] == str(test_snapshot.id)
        assert data['template_id'] is None

    @pytest.mark.integration
    def test_promote_image_to_library(self, client, auth_headers):
        """Should promote cached image to VM Library."""
        response = client.post(
            "/api/v1/cache/promote-to-library",
            headers=auth_headers,
            json={
                "image_name": "alpine:latest",
                "name": "Alpine Test",
                "description": "Test snapshot from alpine",
                "os_type": "linux",
                "vm_type": "container",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['name'] == "Alpine Test"
        assert data['is_global'] is True

    @pytest.mark.integration
    def test_deployment_validation(self, client, auth_headers, test_range):
        """Should validate range before deployment."""
        response = client.get(
            f"/api/v1/ranges/{test_range.id}/validate",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert 'valid' in data
        assert 'errors' in data
        assert 'warnings' in data
```

**Step 1: Run integration tests**

Run: `cd /Users/JonWFH/jondev/CYROID && python -m pytest backend/tests/integration/test_vm_library.py -v -m integration`

**Step 2: Commit**

```bash
git add backend/tests/integration/test_vm_library.py
git commit -m "test: add VM Library integration tests"
```

---

## Final Task: Update Documentation

### Task 4.1: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

Update the roadmap status and feature tables to reflect completed work:

- Phase 4 completion with DinD isolation
- VM Library feature status
- Updated version to 0.12.0

**Commit:**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with VM Library and DinD completion status"
```

---

## Summary

**Total Tasks:** 18
**Estimated Time:** 8-12 hours

**Phase 1 (DinD):** 6 tasks
- Enhanced image transfer with progress
- VNC proxy for console access
- iptables inside DinD
- Full lifecycle endpoints
- Delete LXD plan

**Phase 2 (VM Library):** 8 tasks
- Enhanced Snapshot model
- VM model snapshot support
- Schema validation
- API updates
- Pre-deployment validation
- Frontend VM Library page
- Snapshot selection in ranges
- Promote to library feature

**Phase 3 (Testing):** 2 tasks
- DinD integration tests
- VM Library integration tests

**Phase 4 (Docs):** 1 task
- Update CLAUDE.md

---

Plan complete and saved to `docs/plans/2026-01-19-vm-library-dind-refactor.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
