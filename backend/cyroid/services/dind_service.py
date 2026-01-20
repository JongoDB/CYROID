# backend/cyroid/services/dind_service.py
"""Docker-in-Docker service for range isolation.

Each range runs inside its own DinD container, providing complete network
namespace isolation. This eliminates IP conflicts between concurrent range
instances using the same blueprint IPs.
"""

import asyncio
import logging
import re
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

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Docker container names.

        Converts to lowercase, replaces spaces/special chars with hyphens,
        and removes any invalid characters.
        """
        # Replace spaces and underscores with hyphens
        sanitized = re.sub(r'[\s_]+', '-', name)
        # Remove any characters that aren't alphanumeric or hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9-]', '', sanitized)
        # Remove consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        # Limit length to 40 chars to leave room for prefix and suffix
        return sanitized[:40] if sanitized else "range"

    def _get_container_name(self, range_id: str, range_name: Optional[str] = None) -> str:
        """
        Get the DinD container name for a range.

        Format: cyroid-range-{sanitized_name}-{first 8 of uuid}
        Example: cyroid-range-E2E-Test-Fresh-6f372ca8
        """
        short_id = str(range_id).replace("-", "")[:8]
        if range_name:
            sanitized = self._sanitize_name(range_name)
            return f"cyroid-range-{sanitized}-{short_id}"
        return f"cyroid-range-{short_id}"

    def _find_container_by_range_id(self, range_id: str):
        """
        Find a DinD container by its range_id label.

        Returns the container object or None if not found.
        """
        try:
            containers = self.host_client.containers.list(
                all=True,
                filters={"label": f"cyroid.range_id={range_id}"}
            )
            return containers[0] if containers else None
        except Exception as e:
            logger.error(f"Error finding container for range {range_id}: {e}")
            return None

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
        range_name: Optional[str] = None,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
    ) -> dict:
        """
        Create a DinD container for range isolation.

        Args:
            range_id: Unique identifier for the range (UUID string)
            range_name: Human-readable range name (used in container naming)
            memory_limit: Memory limit (e.g., "8g", "4096m")
            cpu_limit: CPU limit as float (e.g., 4.0 for 4 cores)

        Returns:
            dict with container_name, container_id, mgmt_ip, docker_url
        """
        # Ensure prerequisites
        await self.ensure_dind_image()
        await self.ensure_ranges_network()

        # Generate container name: cyroid-range-{name}-{short_id}
        container_name = self._get_container_name(range_id, range_name)
        short_id = str(range_id).replace("-", "")[:8]
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
        short_id = str(range_id).replace("-", "")[:8]
        volume_name = f"cyroid-range-{short_id}-docker"

        logger.info(f"Deleting DinD container for range {range_id}")

        # Close cached client if exists
        self.close_range_client(range_id)

        # Find container by label (handles both old and new naming formats)
        container = self._find_container_by_range_id(range_id)

        # Stop and remove container
        if container:
            container_name = container.name
            try:
                container.stop(timeout=10)
                container.remove(force=True)
                logger.info(f"Deleted DinD container: {container_name}")
            except Exception as e:
                logger.error(f"Error deleting container {container_name}: {e}")
        else:
            logger.warning(f"No DinD container found for range {range_id}")

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
        # Find container by label (handles both old and new naming formats)
        container = self._find_container_by_range_id(range_id)
        if not container:
            return None

        try:
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
        container = self._find_container_by_range_id(range_id)
        if not container:
            raise ValueError(f"DinD container not found for range {range_id}")

        try:
            result = container.exec_run(command, demux=True)
            stdout = result.output[0].decode() if result.output[0] else ""
            stderr = result.output[1].decode() if result.output[1] else ""
            return result.exit_code, stdout + stderr
        except Exception as e:
            logger.error(f"Error executing command in {container.name}: {e}")
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
        container = self._find_container_by_range_id(range_id)
        if not container:
            raise ValueError(f"DinD container not found for range {range_id}")

        container.start()
        container.reload()

        networks = container.attrs["NetworkSettings"]["Networks"]
        mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")
        docker_url = f"tcp://{mgmt_ip}:{self.dind_docker_port}" if mgmt_ip else None

        if docker_url:
            await self._wait_for_docker_ready(docker_url)

        return {
            "container_name": container.name,
            "container_id": container.id,
            "status": container.status,
            "mgmt_ip": mgmt_ip,
            "docker_url": docker_url,
        }

    async def stop_range_container(self, range_id: str, timeout: int = 10) -> None:
        """Stop a running DinD container (keeps data)."""
        # Close cached client
        self.close_range_client(range_id)

        container = self._find_container_by_range_id(range_id)
        if container:
            container.stop(timeout=timeout)
            logger.info(f"Stopped DinD container: {container.name}")
        else:
            logger.warning(f"No DinD container found for range {range_id}")

    async def restart_range_container(self, range_id: str, timeout: int = 10) -> dict:
        """Restart a DinD container."""
        # Close cached client (will be recreated on next use)
        self.close_range_client(range_id)

        container = self._find_container_by_range_id(range_id)
        if not container:
            raise ValueError(f"DinD container not found for range {range_id}")

        container.restart(timeout=timeout)
        container.reload()

        networks = container.attrs["NetworkSettings"]["Networks"]
        mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")
        docker_url = f"tcp://{mgmt_ip}:{self.dind_docker_port}" if mgmt_ip else None

        if docker_url:
            await self._wait_for_docker_ready(docker_url)

        return {
            "container_name": container.name,
            "container_id": container.id,
            "status": container.status,
            "mgmt_ip": mgmt_ip,
            "docker_url": docker_url,
        }

    def _validate_network_name(self, name: str) -> bool:
        """
        Validate network name is safe for iptables rules.

        Prevents command injection by ensuring network names contain only
        safe characters (alphanumeric, underscore, hyphen).

        Args:
            name: Network name to validate

        Returns:
            True if name is valid, False otherwise
        """
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))

    def _get_network_bridge_id(
        self,
        range_client: docker.DockerClient,
        network_name: str,
    ) -> Optional[str]:
        """
        Get the bridge interface ID for a network from Docker inside DinD.

        Docker bridge interfaces are named br-{network_id[:12]}, where
        network_id is the first 12 characters of the network's ID hash.

        Args:
            range_client: Docker client connected to DinD
            network_name: Name of the network

        Returns:
            First 12 chars of network ID, or None if network not found
        """
        try:
            network_obj = range_client.networks.get(network_name)
            return network_obj.id[:12]
        except NotFound:
            logger.warning(f"Network '{network_name}' not found in DinD")
            return None
        except Exception as e:
            logger.error(f"Error getting network ID for '{network_name}': {e}")
            return None

    async def setup_network_isolation_in_dind(
        self,
        range_id: str,
        docker_url: str,
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
            docker_url: Docker daemon URL inside DinD (tcp://ip:port)
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

        # Get range client to query network IDs from Docker inside DinD
        try:
            range_client = self.get_range_client(range_id, docker_url)
        except Exception as e:
            logger.error(f"Cannot connect to Docker daemon in DinD: {e}")
            return

        # Validate network names to prevent command injection
        validated_networks = []
        for network in networks:
            if not self._validate_network_name(network):
                logger.error(f"Invalid network name rejected: {network}")
                continue
            validated_networks.append(network)

        validated_allow_internet = []
        for network in allow_internet:
            if not self._validate_network_name(network):
                logger.error(f"Invalid network name rejected for internet access: {network}")
                continue
            validated_allow_internet.append(network)

        # Build mapping of network names to bridge IDs
        network_bridge_ids = {}
        for network in set(validated_networks + validated_allow_internet):
            bridge_id = self._get_network_bridge_id(range_client, network)
            if bridge_id:
                network_bridge_ids[network] = bridge_id
            else:
                logger.warning(f"Skipping network '{network}' - could not resolve bridge ID")

        # Build list of iptables rules to apply
        rules = []

        # Flush existing FORWARD rules for idempotency (allows re-running safely)
        rules.append("iptables -F FORWARD")

        # Flush NAT POSTROUTING rules for idempotency
        rules.append("iptables -t nat -F POSTROUTING")

        # Default: drop forwarding between networks
        rules.append("iptables -P FORWARD DROP")

        # Allow established connections (for return traffic)
        rules.append(
            "iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT"
        )

        # Allow traffic within each network (same Docker bridge)
        for network in validated_networks:
            bridge_id = network_bridge_ids.get(network)
            if not bridge_id:
                continue
            # Allow traffic on the same bridge interface
            rules.append(
                f"iptables -A FORWARD -i br-{bridge_id} -o br-{bridge_id} -j ACCEPT"
            )

        # Allow internet access for specified networks
        for network in validated_allow_internet:
            bridge_id = network_bridge_ids.get(network)
            if not bridge_id:
                continue
            # Allow outbound traffic from this network to eth0 (external)
            rules.append(f"iptables -A FORWARD -i br-{bridge_id} -o eth0 -j ACCEPT")

        # Set up NAT/MASQUERADE for internet-enabled networks (once, not per network)
        if validated_allow_internet:
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
            f"({len(validated_networks)} networks, {len(validated_allow_internet)} with internet)"
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

    async def setup_vnc_port_forwarding(
        self,
        range_id: str,
        vm_ports: List[dict],
    ) -> dict[str, dict]:
        """
        Set up iptables DNAT rules for VNC port forwarding inside DinD.

        Instead of using nginx proxy, this uses iptables PREROUTING DNAT rules
        to forward traffic from the DinD management IP to VM VNC ports.

        Architecture:
            Traefik (host) -> 172.30.1.5:15900 -> iptables DNAT -> vm-container:8006

        Args:
            range_id: Range identifier
            vm_ports: List of VM port configurations, each with:
                - vm_id: VM identifier
                - hostname: VM hostname
                - vnc_port: VNC port inside the VM container (e.g., 8006, 6901)
                - ip_address: IP address of the VM container inside DinD

        Returns:
            dict mapping vm_id to proxy info:
                - proxy_port: External port on DinD management IP
                - proxy_host: DinD management IP
                - original_port: Original VNC port in VM container
        """
        # Base port for VNC proxy - VMs will be mapped to 15900, 15901, 15902, etc.
        VNC_PROXY_BASE_PORT = 15900

        container_name = self._get_container_name(range_id)

        try:
            dind_container = self.host_client.containers.get(container_name)
        except NotFound:
            logger.error(f"Cannot find DinD container {container_name}")
            raise ValueError(f"DinD container not found for range {range_id}")

        # Get DinD management IP
        dind_container.reload()
        networks = dind_container.attrs["NetworkSettings"]["Networks"]
        dind_mgmt_ip = networks.get(self.ranges_network, {}).get("IPAddress")

        if not dind_mgmt_ip:
            raise ValueError(f"Cannot get management IP for DinD container {container_name}")

        port_mappings = {}

        # Build iptables rules for each VM
        for idx, vm_info in enumerate(vm_ports):
            vm_id = vm_info["vm_id"]
            vm_ip = vm_info["ip_address"]
            vnc_port = vm_info["vnc_port"]
            external_port = VNC_PROXY_BASE_PORT + idx

            # Record port mapping
            port_mappings[vm_id] = {
                "proxy_port": external_port,
                "proxy_host": dind_mgmt_ip,
                "original_port": vnc_port,
            }

            # DNAT rule: forward traffic from external_port to vm_ip:vnc_port
            # -d {dind_mgmt_ip} matches traffic destined for DinD's management IP
            dnat_rule = (
                f"iptables -t nat -A PREROUTING -p tcp "
                f"-d {dind_mgmt_ip} --dport {external_port} "
                f"-j DNAT --to-destination {vm_ip}:{vnc_port}"
            )

            try:
                exit_code, output = dind_container.exec_run(dnat_rule, privileged=True)
                if exit_code != 0:
                    output_str = output.decode() if isinstance(output, bytes) else str(output)
                    logger.warning(f"VNC DNAT rule failed: {dnat_rule} -> {output_str}")
                else:
                    logger.debug(f"Applied VNC DNAT rule: {dnat_rule}")
            except Exception as e:
                logger.warning(f"Error applying VNC DNAT rule: {e}")

        # Ensure FORWARD chain allows the forwarded traffic
        # (May already be set by setup_network_isolation_in_dind, but ensure it)
        try:
            # Insert at the beginning to take precedence
            dind_container.exec_run(
                "iptables -I FORWARD 1 -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT",
                privileged=True
            )
        except Exception as e:
            logger.debug(f"Forward rule may already exist: {e}")

        logger.info(
            f"Set up VNC port forwarding for range {range_id}: "
            f"{len(port_mappings)} ports via iptables DNAT"
        )

        return port_mappings

    async def teardown_vnc_port_forwarding(
        self,
        range_id: str,
    ) -> None:
        """
        Remove VNC port forwarding iptables rules.

        Note: This is effectively a no-op since destroying the DinD container
        automatically removes all iptables rules. This method exists for
        symmetry and potential future use cases.

        Args:
            range_id: Range identifier
        """
        # No explicit action needed - destroying DinD container removes all rules
        logger.debug(f"Teardown VNC port forwarding for range {range_id} (no-op)")

    async def setup_inter_network_routing(
        self,
        range_id: str,
        docker_url: str,
        network_pairs: List[tuple[str, str]],
    ) -> None:
        """
        Enable routing between specified networks within a range.

        This allows communication between network-a and network-b within the
        same range using iptables FORWARD rules. DinD acts as the router.

        By default, networks are isolated from each other (cannot route between
        them). Use this method to enable specific network-to-network communication.

        Args:
            range_id: Range identifier
            docker_url: Docker daemon URL inside DinD
            network_pairs: List of (network_name_a, network_name_b) pairs to enable routing between

        Example:
            # Enable routing between "lan" and "dmz" networks
            await setup_inter_network_routing(
                range_id="...",
                docker_url="tcp://...",
                network_pairs=[("lan", "dmz")]
            )
        """
        container_name = self._get_container_name(range_id)

        try:
            dind_container = self.host_client.containers.get(container_name)
        except NotFound:
            logger.error(f"Cannot find DinD container {container_name}")
            return

        # Get range client to query network IDs
        try:
            range_client = self.get_range_client(range_id, docker_url)
        except Exception as e:
            logger.error(f"Cannot connect to Docker daemon in DinD: {e}")
            return

        # Build mapping of network names to bridge IDs
        network_bridge_ids = {}
        all_networks = set()
        for net_a, net_b in network_pairs:
            all_networks.add(net_a)
            all_networks.add(net_b)

        for network in all_networks:
            if not self._validate_network_name(network):
                logger.error(f"Invalid network name rejected: {network}")
                continue
            bridge_id = self._get_network_bridge_id(range_client, network)
            if bridge_id:
                network_bridge_ids[network] = bridge_id
            else:
                logger.warning(f"Skipping network '{network}' - could not resolve bridge ID")

        # Add FORWARD rules to allow traffic between network pairs
        for net_a, net_b in network_pairs:
            bridge_a = network_bridge_ids.get(net_a)
            bridge_b = network_bridge_ids.get(net_b)

            if not bridge_a or not bridge_b:
                logger.warning(f"Skipping routing between {net_a} and {net_b} - missing bridge ID")
                continue

            # Allow bidirectional traffic between the two networks
            rules = [
                f"iptables -I FORWARD 1 -i br-{bridge_a} -o br-{bridge_b} -j ACCEPT",
                f"iptables -I FORWARD 1 -i br-{bridge_b} -o br-{bridge_a} -j ACCEPT",
            ]

            for rule in rules:
                try:
                    exit_code, output = dind_container.exec_run(rule, privileged=True)
                    if exit_code != 0:
                        output_str = output.decode() if isinstance(output, bytes) else str(output)
                        logger.warning(f"Inter-network routing rule failed: {rule} -> {output_str}")
                    else:
                        logger.debug(f"Applied inter-network routing rule: {rule}")
                except Exception as e:
                    logger.warning(f"Error applying inter-network routing rule: {e}")

        logger.info(
            f"Set up inter-network routing for range {range_id}: "
            f"{len(network_pairs)} network pairs"
        )


# Singleton instance for dependency injection
_dind_service: Optional[DinDService] = None


def get_dind_service() -> DinDService:
    """Get or create the DinD service singleton."""
    global _dind_service
    if _dind_service is None:
        _dind_service = DinDService()
    return _dind_service
