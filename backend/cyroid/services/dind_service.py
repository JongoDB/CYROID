# backend/cyroid/services/dind_service.py
"""Docker-in-Docker service for range isolation.

Each range runs inside its own DinD container, providing complete network
namespace isolation. This eliminates IP conflicts between concurrent range
instances using the same blueprint IPs.
"""

import asyncio
import logging
from typing import List, Optional

import docker
from docker.errors import APIError, NotFound

from cyroid.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DinDService:
    """Manages Docker-in-Docker containers for range isolation."""

    # Default DinD image - can be overridden in settings
    DIND_IMAGE = "docker:24-dind"
    DOCKER_PORT = 2375
    STARTUP_TIMEOUT = 60  # seconds

    def __init__(self):
        self.host_client = docker.from_env()
        self._range_clients: dict[str, docker.DockerClient] = {}

    @property
    def dind_image(self) -> str:
        """Get configured DinD image."""
        return getattr(settings, "dind_image", self.DIND_IMAGE)

    @property
    def dind_startup_timeout(self) -> int:
        """Get configured startup timeout."""
        return getattr(settings, "dind_startup_timeout", self.STARTUP_TIMEOUT)

    @property
    def dind_docker_port(self) -> int:
        """Get configured Docker port for DinD."""
        return getattr(settings, "dind_docker_port", self.DOCKER_PORT)

    @property
    def ranges_network(self) -> str:
        """Get the network name for range DinD containers."""
        return getattr(settings, "cyroid_ranges_network", "cyroid-ranges")

    async def ensure_dind_image(self) -> None:
        """Ensure the DinD image is available locally."""
        try:
            self.host_client.images.get(self.dind_image)
            logger.debug(f"DinD image '{self.dind_image}' already available")
        except NotFound:
            logger.info(f"Pulling DinD image '{self.dind_image}'...")
            self.host_client.images.pull(self.dind_image)
            logger.info(f"Successfully pulled DinD image '{self.dind_image}'")

    async def ensure_ranges_network(self) -> None:
        """Ensure the ranges network exists on the host."""
        network_name = self.ranges_network
        subnet = getattr(settings, "cyroid_ranges_subnet", "172.30.1.0/24")

        try:
            self.host_client.networks.get(network_name)
            logger.debug(f"Ranges network '{network_name}' already exists")
        except NotFound:
            logger.info(f"Creating ranges network '{network_name}' ({subnet})...")
            ipam_pool = docker.types.IPAMPool(subnet=subnet)
            ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
            self.host_client.networks.create(
                name=network_name,
                driver="bridge",
                ipam=ipam_config,
            )
            logger.info(f"Created ranges network '{network_name}'")

    async def create_range_container(
        self,
        range_id: str,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
    ) -> dict:
        """
        Create a DinD container for range isolation.

        Args:
            range_id: Unique identifier for the range (UUID string)
            memory_limit: Memory limit (e.g., "8g", "4096m")
            cpu_limit: CPU limit as float (e.g., 4.0 for 4 cores)

        Returns:
            dict with container_name, container_id, mgmt_ip, docker_url
        """
        # Ensure prerequisites
        await self.ensure_dind_image()
        await self.ensure_ranges_network()

        # Use first 12 chars of range_id for container name
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"
        volume_name = f"cyroid-range-{short_id}-docker"

        logger.info(f"Creating DinD container '{container_name}' for range {range_id}")

        # Create volume for Docker data (improves performance with overlay-on-overlay)
        try:
            self.host_client.volumes.create(name=volume_name)
            logger.debug(f"Created volume '{volume_name}'")
        except APIError as e:
            if "already exists" not in str(e):
                raise
            logger.debug(f"Volume '{volume_name}' already exists")

        # Prepare container configuration
        container_config = {
            "image": self.dind_image,
            "name": container_name,
            "detach": True,
            "privileged": True,  # Required for DinD
            "environment": {
                "DOCKER_TLS_CERTDIR": "",  # Disable TLS for internal communication
            },
            "volumes": {volume_name: {"bind": "/var/lib/docker", "mode": "rw"}},
            "network": self.ranges_network,
            "labels": {
                "cyroid.range_id": str(range_id),
                "cyroid.type": "dind",
            },
        }

        # Apply resource limits if specified
        if memory_limit:
            container_config["mem_limit"] = memory_limit
        if cpu_limit:
            container_config["nano_cpus"] = int(cpu_limit * 1e9)

        # Create the DinD container
        container = self.host_client.containers.run(**container_config)

        # Get container info including IP
        container.reload()
        networks = container.attrs["NetworkSettings"]["Networks"]
        mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")

        if not mgmt_ip:
            # Fallback: try to get IP from any network
            for net_name, net_info in networks.items():
                if net_info.get("IPAddress"):
                    mgmt_ip = net_info["IPAddress"]
                    logger.warning(
                        f"Using IP from '{net_name}' network instead of '{self.ranges_network}'"
                    )
                    break

        if not mgmt_ip:
            raise RuntimeError(f"Failed to get IP for container {container_name}")

        docker_url = f"tcp://{mgmt_ip}:{self.dind_docker_port}"

        logger.info(f"DinD container '{container_name}' created at {mgmt_ip}")

        # Wait for inner Docker daemon to be ready
        await self._wait_for_docker_ready(docker_url)

        return {
            "container_name": container_name,
            "container_id": container.id,
            "mgmt_ip": mgmt_ip,
            "docker_url": docker_url,
            "docker_port": self.dind_docker_port,
            "volume_name": volume_name,
        }

    async def delete_range_container(self, range_id: str) -> None:
        """Delete DinD container and associated resources."""
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"
        volume_name = f"cyroid-range-{short_id}-docker"

        logger.info(f"Deleting DinD container '{container_name}' for range {range_id}")

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
            logger.debug(f"Volume not found: {volume_name}")
        except Exception as e:
            logger.warning(f"Error deleting volume {volume_name}: {e}")

    async def get_container_info(self, range_id: str) -> Optional[dict]:
        """Get DinD container status and network info."""
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"

        try:
            container = self.host_client.containers.get(container_name)
            container.reload()

            networks = container.attrs["NetworkSettings"]["Networks"]
            mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")

            return {
                "container_name": container_name,
                "container_id": container.id,
                "status": container.status,
                "mgmt_ip": mgmt_ip,
                "docker_url": (
                    f"tcp://{mgmt_ip}:{self.dind_docker_port}" if mgmt_ip else None
                ),
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
        range_id_str = str(range_id)
        if range_id_str not in self._range_clients:
            logger.debug(f"Creating Docker client for range {range_id} at {docker_url}")
            self._range_clients[range_id_str] = docker.DockerClient(base_url=docker_url)

        return self._range_clients[range_id_str]

    def close_range_client(self, range_id: str) -> None:
        """Close and remove cached Docker client for a range."""
        range_id_str = str(range_id)
        if range_id_str in self._range_clients:
            try:
                self._range_clients[range_id_str].close()
            except Exception:
                pass
            del self._range_clients[range_id_str]
            logger.debug(f"Closed Docker client for range {range_id}")

    def close_all_range_clients(self) -> None:
        """Close all cached range Docker clients."""
        for range_id in list(self._range_clients.keys()):
            self.close_range_client(range_id)

    async def _wait_for_docker_ready(
        self, docker_url: str, timeout: Optional[int] = None
    ) -> None:
        """Wait for Docker daemon inside DinD to be ready."""
        timeout = timeout or self.dind_startup_timeout

        for i in range(timeout):
            try:
                # Create client inside retry loop - it connects on initialization
                client = docker.DockerClient(base_url=docker_url)
                client.ping()
                logger.info(f"Docker daemon ready at {docker_url}")
                client.close()
                return
            except Exception as e:
                if i % 10 == 0:
                    logger.debug(f"Waiting for Docker at {docker_url}... ({i}s) - {e}")
                await asyncio.sleep(1)

        raise TimeoutError(f"Docker daemon not ready at {docker_url} after {timeout}s")

    async def exec_in_container(
        self, range_id: str, command: list[str]
    ) -> tuple[int, str]:
        """
        Execute a command inside the DinD container.

        Returns:
            tuple of (exit_code, output)
        """
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"

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
            all=True, filters={"label": "cyroid.type=dind"}
        )

        result = []
        for container in containers:
            networks = container.attrs["NetworkSettings"]["Networks"]
            mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")
            range_id = container.labels.get("cyroid.range_id", "")

            result.append(
                {
                    "container_name": container.name,
                    "container_id": container.id,
                    "status": container.status,
                    "mgmt_ip": mgmt_ip,
                    "range_id": range_id,
                }
            )

        return result

    async def start_range_container(self, range_id: str) -> dict:
        """Start a stopped DinD container."""
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"

        try:
            container = self.host_client.containers.get(container_name)
            container.start()
            container.reload()

            networks = container.attrs["NetworkSettings"]["Networks"]
            mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")
            docker_url = f"tcp://{mgmt_ip}:{self.dind_docker_port}" if mgmt_ip else None

            if docker_url:
                await self._wait_for_docker_ready(docker_url)

            return {
                "container_name": container_name,
                "container_id": container.id,
                "status": container.status,
                "mgmt_ip": mgmt_ip,
                "docker_url": docker_url,
            }
        except NotFound:
            raise ValueError(f"DinD container not found for range {range_id}")

    async def stop_range_container(self, range_id: str, timeout: int = 10) -> None:
        """Stop a running DinD container (keeps data)."""
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"

        # Close cached client
        self.close_range_client(range_id)

        try:
            container = self.host_client.containers.get(container_name)
            container.stop(timeout=timeout)
            logger.info(f"Stopped DinD container: {container_name}")
        except NotFound:
            logger.warning(f"Container not found: {container_name}")

    async def restart_range_container(self, range_id: str, timeout: int = 10) -> dict:
        """Restart a DinD container."""
        short_id = str(range_id).replace("-", "")[:12]
        container_name = f"cyroid-range-{short_id}"

        # Close cached client (will be recreated on next use)
        self.close_range_client(range_id)

        try:
            container = self.host_client.containers.get(container_name)
            container.restart(timeout=timeout)
            container.reload()

            networks = container.attrs["NetworkSettings"]["Networks"]
            mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")
            docker_url = f"tcp://{mgmt_ip}:{self.dind_docker_port}" if mgmt_ip else None

            if docker_url:
                await self._wait_for_docker_ready(docker_url)

            return {
                "container_name": container_name,
                "container_id": container.id,
                "status": container.status,
                "mgmt_ip": mgmt_ip,
                "docker_url": docker_url,
            }
        except NotFound:
            raise ValueError(f"DinD container not found for range {range_id}")

    def _get_container_name(self, range_id: str) -> str:
        """Get the DinD container name for a range."""
        short_id = str(range_id).replace("-", "")[:12]
        return f"cyroid-range-{short_id}"

    async def setup_network_isolation_in_dind(
        self,
        range_id: str,
        networks: List[str],
        allow_internet: Optional[List[str]] = None,
    ) -> None:
        """
        Apply iptables rules inside DinD container for network isolation.

        This sets up firewall rules within the DinD container to:
        - Block forwarding between different networks by default
        - Allow traffic within the same network
        - Optionally allow internet access for specified networks via NAT

        Args:
            range_id: Range identifier
            networks: List of network names in this range
            allow_internet: Networks that should have internet access (via DinD NAT)
        """
        allow_internet = allow_internet or []
        container_name = self._get_container_name(range_id)

        try:
            # Get the DinD container (runs on host Docker daemon)
            dind_container = self.host_client.containers.get(container_name)
        except NotFound:
            logger.error(f"Cannot find DinD container {container_name}")
            return
        except Exception as e:
            logger.error(f"Error getting DinD container {container_name}: {e}")
            return

        # Build list of iptables rules to apply
        rules = []

        # Default: drop forwarding between networks
        rules.append("iptables -P FORWARD DROP")

        # Allow established connections (for return traffic)
        rules.append(
            "iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT"
        )

        # Allow traffic within each network (same Docker bridge)
        # Docker bridge names are based on network ID, but we use a simpler approach
        # by allowing all traffic on the same interface
        for network in networks:
            # Allow loopback within each network
            # Note: Docker internally handles same-network communication,
            # but we add explicit rules for clarity
            bridge_prefix = network[:12]  # Docker truncates to 12 chars
            rules.append(
                f"iptables -A FORWARD -i br-{bridge_prefix} -o br-{bridge_prefix} -j ACCEPT"
            )

        # Allow internet access for specified networks
        for network in allow_internet:
            bridge_prefix = network[:12]
            # Allow outbound traffic from this network to eth0 (external)
            rules.append(f"iptables -A FORWARD -i br-{bridge_prefix} -o eth0 -j ACCEPT")

        # Set up NAT/MASQUERADE for internet-enabled networks (once, not per network)
        if allow_internet:
            # This allows return traffic from internet
            rules.append("iptables -A FORWARD -i eth0 -m state --state ESTABLISHED,RELATED -j ACCEPT")
            # MASQUERADE for outbound traffic (NAT)
            rules.append(
                "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
            )

        # Execute rules inside the DinD container
        for rule in rules:
            try:
                exit_code, output = dind_container.exec_run(rule, privileged=True)
                if exit_code != 0:
                    output_str = output.decode() if isinstance(output, bytes) else str(output)
                    logger.warning(f"iptables rule failed: {rule} -> {output_str}")
                else:
                    logger.debug(f"Applied iptables rule: {rule}")
            except Exception as e:
                logger.warning(f"Error executing iptables rule '{rule}': {e}")

        logger.info(
            f"Applied network isolation rules for range {range_id} "
            f"({len(networks)} networks, {len(allow_internet)} with internet)"
        )

    async def teardown_network_isolation_in_dind(
        self,
        range_id: str,
    ) -> None:
        """
        Remove iptables rules for a range.

        Note: This is effectively a no-op since destroying the DinD container
        automatically removes all iptables rules. This method exists for
        symmetry with setup and potential future use cases where rules might
        need to be removed without destroying the container.

        Args:
            range_id: Range identifier
        """
        # No explicit action needed - destroying DinD container removes all rules
        # Log for debugging purposes
        logger.debug(f"Teardown network isolation for range {range_id} (no-op)")
        pass


# Singleton instance for dependency injection
_dind_service: Optional[DinDService] = None


def get_dind_service() -> DinDService:
    """Get or create the DinD service singleton."""
    global _dind_service
    if _dind_service is None:
        _dind_service = DinDService()
    return _dind_service
