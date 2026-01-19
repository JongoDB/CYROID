# cyroid/services/docker_service.py
"""
Docker orchestration service for managing containers and networks.

Supports three VM/container types:
1. Container: Basic Docker containers for lightweight Linux workloads
2. Linux VM: Full Linux VMs via qemus/qemu (desktop & server environments)
3. Windows VM: Full Windows VMs via dockur/windows

Both qemus/qemu and dockur/windows provide:
- KVM acceleration for near-native performance
- Web-based VNC console on port 8006
- Persistent storage and golden image support
- Auto-download of OS images (24+ Linux distros, all Windows versions)

DinD (Docker-in-Docker) Isolation:
When DIND_ISOLATION_ENABLED=true, each range deploys inside its own DinD
container, providing complete network namespace isolation. This eliminates
IP conflicts between concurrent range instances using identical blueprint IPs.
"""
import docker
from docker.errors import APIError, NotFound, ImageNotFound
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING
import logging
import time
import ipaddress

from cyroid.utils.arch import IS_ARM, HOST_ARCH, requires_emulation
from cyroid.config import get_settings

if TYPE_CHECKING:
    from cyroid.services.dind_service import DinDService

logger = logging.getLogger(__name__)


class DockerService:
    """
    Service for managing Docker containers and networks.

    With DinD isolation enabled:
    - Host operations: Uses local Docker daemon (for CYROID infrastructure)
    - Range operations: Uses Docker daemon inside range's DinD container

    Without DinD isolation (legacy mode):
    - All operations use local Docker daemon directly
    """

    def __init__(self, dind_service: Optional["DinDService"] = None):
        """
        Initialize Docker service.

        Args:
            dind_service: Optional DinD service for range isolation.
                         If None and DinD is enabled, will be created on demand.
        """
        self.client = docker.from_env()
        self._dind_service = dind_service
        self._verify_connection()

    @property
    def dind_service(self) -> "DinDService":
        """Get DinD service, creating lazily if needed."""
        if self._dind_service is None:
            from cyroid.services.dind_service import get_dind_service
            self._dind_service = get_dind_service()

        return self._dind_service

    async def get_range_client(self, range_id: str, docker_url: Optional[str] = None) -> docker.DockerClient:
        """
        Get Docker client for a range's DinD container.

        Returns client connected to the range's inner Docker daemon.

        Args:
            range_id: Range identifier
            docker_url: Optional Docker URL (if known). If not provided,
                       will query DinD service for the URL.

        Returns:
            DockerClient for operating on the range
        """
        if docker_url:
            return self.dind_service.get_range_client(str(range_id), docker_url)

        # Get container info to find Docker URL
        container_info = await self.dind_service.get_container_info(str(range_id))
        if not container_info or not container_info.get("docker_url"):
            raise ValueError(f"Range {range_id} has no active DinD container")

        return self.dind_service.get_range_client(str(range_id), container_info["docker_url"])

    def get_range_client_sync(self, range_id: str, docker_url: str) -> docker.DockerClient:
        """
        Synchronous version of get_range_client (for use when URL is known).

        Args:
            range_id: Range identifier
            docker_url: Docker URL (tcp://ip:port)

        Returns:
            DockerClient for operating on the range
        """
        return self.dind_service.get_range_client(str(range_id), docker_url)
    
    def _verify_connection(self) -> None:
        """Verify connection to Docker daemon."""
        try:
            self.client.ping()
            logger.info("Connected to Docker daemon")
        except Exception as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            raise RuntimeError("Cannot connect to Docker daemon")
    
    # Network Operations
    
    def create_network(
        self,
        name: str,
        subnet: str,
        gateway: str,
        internal: bool = True,
        labels: Optional[Dict[str, str]] = None,
        use_vyos_gateway: bool = True
    ) -> str:
        """
        Create a Docker network with the specified configuration.

        Args:
            name: Network name
            subnet: CIDR notation (e.g., "10.0.1.0/24")
            gateway: Gateway IP address (used by VyOS, not Docker bridge)
            internal: If True, no external connectivity (isolation)
            labels: Optional labels for the network
            use_vyos_gateway: If True, don't assign gateway to Docker bridge (VyOS will be gateway)

        Returns:
            Network ID
        """
        if use_vyos_gateway:
            # Docker bridge uses .254, leaving .1 available for VyOS
            import ipaddress
            subnet_obj = ipaddress.ip_network(subnet, strict=False)
            hosts = list(subnet_obj.hosts())
            # Use last usable host (.254 for /24) for Docker bridge
            bridge_ip = str(hosts[-1]) if hosts else gateway

            ipam_pool = docker.types.IPAMPool(
                subnet=subnet,
                gateway=bridge_ip  # Docker bridge uses .254, not .1
            )
        else:
            # Legacy mode: Docker bridge is the gateway
            ipam_pool = docker.types.IPAMPool(
                subnet=subnet,
                gateway=gateway
            )
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])

        try:
            network = self.client.networks.create(
                name=name,
                driver="bridge",
                internal=internal,
                ipam=ipam_config,
                labels=labels or {},
                attachable=True
            )
            logger.info(f"Created network: {name} ({network.id[:12]}) [VyOS gateway mode: {use_vyos_gateway}]")
            return network.id
        except APIError as e:
            logger.error(f"Failed to create network {name}: {e}")
            raise
    
    def delete_network(self, network_id: str) -> bool:
        """Delete a Docker network."""
        try:
            network = self.client.networks.get(network_id)
            network.remove()
            logger.info(f"Deleted network: {network_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"Network not found: {network_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to delete network {network_id}: {e}")
            raise
    
    def get_network(self, network_id: str) -> Optional[Dict[str, Any]]:
        """Get network information."""
        try:
            network = self.client.networks.get(network_id)
            return {
                "id": network.id,
                "name": network.name,
                "created": network.attrs.get("Created"),
                "scope": network.attrs.get("Scope"),
                "driver": network.attrs.get("Driver"),
                "containers": list(network.attrs.get("Containers", {}).keys())
            }
        except NotFound:
            return None

    def get_container_logs(self, container_id: str, tail: int = 100) -> list[str]:
        """
        Get last N lines of container logs.

        Args:
            container_id: Docker container ID
            tail: Number of lines to retrieve

        Returns:
            List of log lines with timestamps
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
            return logs.strip().split('\n') if logs.strip() else []
        except NotFound:
            return ["Container not found - it may have been removed"]
        except APIError as e:
            return [f"Error fetching logs: {e}"]

    def _connect_to_traefik_network(self, container_id: str) -> None:
        """
        DEPRECATED: VMs should NOT be connected to traefik-routing for security.
        Instead, traefik is connected to range networks via connect_traefik_to_network().

        This method is kept for backwards compatibility but logs a warning.
        """
        logger.warning(f"_connect_to_traefik_network is deprecated - VMs should not be on management network")
        # Do nothing - VMs should not be on traefik-routing

    def connect_traefik_to_network(self, network_id: str) -> bool:
        """
        Connect the traefik container to a range network.
        This allows traefik to route to VMs on that network without exposing
        the management network to VMs.

        Traefik is assigned .253 in the subnet, leaving .1 available for VyOS
        and .254 for the Docker bridge.

        Args:
            network_id: Docker network ID to connect traefik to

        Returns:
            True if successful, False if traefik not found or already connected
        """
        try:
            import ipaddress

            # Find the traefik container
            traefik_container = None
            for container in self.client.containers.list():
                if 'traefik' in container.name.lower():
                    traefik_container = container
                    break

            if not traefik_container:
                logger.warning("Traefik container not found - VNC routing may not work")
                return False

            # Get the network
            network = self.client.networks.get(network_id)

            # Check if traefik is already connected
            connected_containers = network.attrs.get("Containers", {})
            if traefik_container.id in connected_containers:
                logger.debug(f"Traefik already connected to network {network.name}")
                return True

            # Calculate Traefik IP (.253 in the subnet)
            # This leaves .1 for VyOS and .254 for Docker bridge
            ipam_config = network.attrs.get("IPAM", {}).get("Config", [])
            traefik_ip = None
            if ipam_config:
                subnet_str = ipam_config[0].get("Subnet")
                if subnet_str:
                    subnet_obj = ipaddress.ip_network(subnet_str, strict=False)
                    hosts = list(subnet_obj.hosts())
                    if len(hosts) >= 3:
                        # .253 is second-to-last usable host
                        traefik_ip = str(hosts[-2])

            # Connect traefik to the network with specific IP
            if traefik_ip:
                network.connect(traefik_container.id, ipv4_address=traefik_ip)
                logger.info(f"Connected traefik to network {network.name} at {traefik_ip}")
            else:
                network.connect(traefik_container.id)
                logger.info(f"Connected traefik to network {network.name} for VM routing")
            return True

        except NotFound as e:
            logger.warning(f"Network not found when connecting traefik: {e}")
            return False
        except APIError as e:
            logger.warning(f"Failed to connect traefik to network: {e}")
            return False

    def disconnect_traefik_from_network(self, network_id: str) -> bool:
        """
        Disconnect the traefik container from a range network.
        Called during network teardown.

        Args:
            network_id: Docker network ID to disconnect traefik from

        Returns:
            True if successful
        """
        try:
            # Find the traefik container
            traefik_container = None
            for container in self.client.containers.list():
                if 'traefik' in container.name.lower():
                    traefik_container = container
                    break

            if not traefik_container:
                return True  # Nothing to disconnect

            # Get the network
            network = self.client.networks.get(network_id)

            # Disconnect traefik from the network
            network.disconnect(traefik_container.id)
            logger.info(f"Disconnected traefik from network {network.name}")
            return True

        except NotFound:
            return True  # Already disconnected
        except APIError as e:
            logger.warning(f"Failed to disconnect traefik from network: {e}")
            return False

    def setup_network_isolation(self, network_id: str, subnet: str) -> bool:
        """
        Set up iptables rules to isolate a range network from the host and CYROID infrastructure.

        This prevents VMs from:
        - Accessing the Docker host (localhost, host gateway)
        - Accessing CYROID services (backend, database, traefik-routing network)
        - Accessing other range networks

        Args:
            network_id: Docker network ID (used for rule comments/identification)
            subnet: Network subnet in CIDR notation (e.g., "10.0.1.0/24")

        Returns:
            True if successful
        """
        import subprocess

        try:
            # Get the network to find its bridge interface
            network = self.client.networks.get(network_id)
            network_name = network.name

            # Get host IPs to block (Docker gateway IPs and host interfaces)
            # These are common Docker/host IPs that should be blocked
            blocked_destinations = [
                "172.17.0.0/16",      # Default Docker bridge network
                "172.18.0.0/16",      # Docker networks range
                "172.19.0.0/16",      # Docker networks range
                "172.20.0.0/16",      # Docker networks range
                "127.0.0.0/8",        # Localhost
                "10.0.0.0/8",         # Private networks (except our subnet)
                "192.168.0.0/16",     # Private networks
            ]

            # Create a unique chain for this network
            chain_name = f"CYROID-{network_id[:12]}"

            # Create the chain (ignore error if exists)
            subprocess.run(
                ["iptables", "-N", chain_name],
                capture_output=True
            )

            # Flush existing rules in the chain
            subprocess.run(
                ["iptables", "-F", chain_name],
                capture_output=True
            )

            # Add rules to block access to infrastructure
            for dest in blocked_destinations:
                # Skip if destination overlaps with our own subnet
                if self._subnets_overlap(subnet, dest):
                    continue

                subprocess.run([
                    "iptables", "-A", chain_name,
                    "-s", subnet,
                    "-d", dest,
                    "-j", "DROP"
                ], check=True, capture_output=True)

            # Block access to host's physical interfaces
            # Get host IP addresses
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                host_ips = result.stdout.strip().split()
                for host_ip in host_ips:
                    if host_ip and not host_ip.startswith(subnet.split('/')[0].rsplit('.', 1)[0]):
                        subprocess.run([
                            "iptables", "-A", chain_name,
                            "-s", subnet,
                            "-d", f"{host_ip}/32",
                            "-j", "DROP"
                        ], capture_output=True)

            # Allow traffic within the same subnet (for VM-to-VM communication)
            subprocess.run([
                "iptables", "-I", chain_name, "1",
                "-s", subnet,
                "-d", subnet,
                "-j", "ACCEPT"
            ], check=True, capture_output=True)

            # Add jump to our chain from DOCKER-USER (at the beginning)
            # First check if rule already exists
            check_result = subprocess.run([
                "iptables", "-C", "DOCKER-USER",
                "-s", subnet,
                "-j", chain_name
            ], capture_output=True)

            if check_result.returncode != 0:
                # Rule doesn't exist, add it
                subprocess.run([
                    "iptables", "-I", "DOCKER-USER", "1",
                    "-s", subnet,
                    "-j", chain_name
                ], check=True, capture_output=True)

            logger.info(f"Set up network isolation for {network_name} ({subnet})")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up network isolation: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to set up network isolation: {e}")
            return False

    def teardown_network_isolation(self, network_id: str, subnet: str) -> bool:
        """
        Remove iptables rules for a range network.

        Args:
            network_id: Docker network ID
            subnet: Network subnet in CIDR notation

        Returns:
            True if successful
        """
        import subprocess

        try:
            chain_name = f"CYROID-{network_id[:12]}"

            # Remove jump from DOCKER-USER
            subprocess.run([
                "iptables", "-D", "DOCKER-USER",
                "-s", subnet,
                "-j", chain_name
            ], capture_output=True)  # Ignore errors if rule doesn't exist

            # Flush and delete the chain
            subprocess.run(["iptables", "-F", chain_name], capture_output=True)
            subprocess.run(["iptables", "-X", chain_name], capture_output=True)

            logger.info(f"Removed network isolation rules for {subnet}")
            return True

        except Exception as e:
            logger.warning(f"Failed to remove network isolation rules: {e}")
            return False

    def _subnets_overlap(self, subnet1: str, subnet2: str) -> bool:
        """Check if two subnets overlap."""
        import ipaddress
        try:
            net1 = ipaddress.ip_network(subnet1, strict=False)
            net2 = ipaddress.ip_network(subnet2, strict=False)
            return net1.overlaps(net2)
        except ValueError:
            return False

    def connect_traefik_to_management_network(self) -> bool:
        """
        Connect the traefik container to the management network.
        This allows traefik to route to VyOS routers and potentially
        route VNC traffic through the management network.

        Returns:
            True if successful
        """
        from cyroid.config import get_settings
        settings = get_settings()

        try:
            # Find the traefik container
            traefik_container = None
            for container in self.client.containers.list():
                if 'traefik' in container.name.lower():
                    traefik_container = container
                    break

            if not traefik_container:
                logger.warning("Traefik container not found")
                return False

            # Get the management network
            network_name = settings.management_network_name
            try:
                networks = self.client.networks.list(names=[network_name])
                mgmt_network = None
                for network in networks:
                    if network.name == network_name:
                        mgmt_network = network
                        break

                if not mgmt_network:
                    logger.warning(f"Management network {network_name} not found")
                    return False
            except NotFound:
                logger.warning(f"Management network {network_name} not found")
                return False

            # Check if traefik is already connected
            connected_containers = mgmt_network.attrs.get("Containers", {})
            if traefik_container.id in connected_containers:
                logger.debug("Traefik already connected to management network")
                return True

            # Connect traefik to the management network
            mgmt_network.connect(traefik_container.id)
            logger.info(f"Connected traefik to management network {network_name}")
            return True

        except APIError as e:
            logger.warning(f"Failed to connect traefik to management network: {e}")
            return False

    # Container Operations (Linux VMs)

    def create_container(
        self,
        name: str,
        image: str,
        network_id: str,
        ip_address: str,
        cpu_limit: int = 2,
        memory_limit_mb: int = 2048,
        volumes: Optional[Dict[str, Dict]] = None,
        environment: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        privileged: bool = False,
        hostname: Optional[str] = None,
        linux_username: Optional[str] = None,
        linux_password: Optional[str] = None,
        linux_user_sudo: bool = True,
        dns_servers: Optional[str] = None,
        dns_search: Optional[str] = None
    ) -> str:
        """
        Create a Docker container for a Linux VM.

        Args:
            name: Container name
            image: Docker image (e.g., "ubuntu:22.04")
            network_id: Network to attach to
            ip_address: Static IP address in the network
            cpu_limit: CPU core limit
            memory_limit_mb: Memory limit in MB
            volumes: Volume bindings
            environment: Environment variables
            labels: Container labels
            privileged: Run in privileged mode
            hostname: Container hostname
            linux_username: Linux username (for KasmVNC/LinuxServer containers)
            linux_password: Linux password (for KasmVNC/LinuxServer containers)
            linux_user_sudo: Grant sudo privileges (for LinuxServer containers)
            dns_servers: Comma-separated DNS servers (e.g., "8.8.8.8,8.8.4.4")
            dns_search: DNS search domain (e.g., "corp.local")

        Returns:
            Container ID
        """
        # Pull image if not present
        self._ensure_image(image)

        # Initialize environment dict if not provided
        if environment is None:
            environment = {}

        # Configure user settings based on container image type
        if "kasmweb/" in image:
            # KasmVNC containers - use hardcoded VNC password for seamless auto-login
            # The linux_password field is for the actual OS user, not VNC auth
            environment["VNC_PW"] = "vncpassword"
            logger.info(f"Set default VNC password for KasmVNC container {name}")
        elif "linuxserver/" in image or "lscr.io/linuxserver" in image:
            # LinuxServer containers (webtop, etc.)
            if linux_username:
                environment["CUSTOM_USER"] = linux_username
            if linux_password:
                environment["PASSWORD"] = linux_password
            if linux_user_sudo:
                environment["SUDO_ACCESS"] = "true"
            logger.info(f"Set user config for LinuxServer container {name}: user={linux_username}, sudo={linux_user_sudo}")

        # Get Range network for attachment
        # NOTE: VMs are created ONLY on the range network for security.
        # Traefik connects to range networks to route traffic - VMs never see traefik-routing.
        try:
            range_network = self.client.networks.get(network_id)
        except NotFound:
            raise ValueError(f"Network not found: {network_id}")

        # Create container directly on the range network with static IP
        # This ensures VMs cannot access the management network
        networking_config = self.client.api.create_networking_config({
            range_network.name: self.client.api.create_endpoint_config(
                ipv4_address=ip_address
            )
        })

        # Parse DNS configuration
        dns_list = None
        dns_search_list = None
        if dns_servers:
            dns_list = [s.strip() for s in dns_servers.split(",") if s.strip()]
        else:
            dns_list = ["8.8.8.8", "8.8.4.4"]  # Default external DNS
        if dns_search:
            dns_search_list = [s.strip() for s in dns_search.split(",") if s.strip()]

        # Create container
        try:
            host_config_args = {
                "cpu_count": cpu_limit,
                "mem_limit": f"{memory_limit_mb}m",
                "binds": volumes,
                "privileged": privileged,
                "cap_add": ["NET_ADMIN"],  # Required for VyOS gateway routing
                "restart_policy": {"Name": "unless-stopped"},
                "dns": dns_list
            }
            if dns_search_list:
                host_config_args["dns_search"] = dns_search_list

            container = self.client.api.create_container(
                image=image,
                name=name,
                hostname=hostname or name,
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=self.client.api.create_host_config(**host_config_args),
                environment=environment,
                labels=labels or {}
            )
            container_id = container["Id"]
            logger.info(f"Created container: {name} ({container_id[:12]}) on {range_network.name} with IP {ip_address}")

            return container_id
        except APIError as e:
            logger.error(f"Failed to create container {name}: {e}")
            raise

    def create_windows_container(
        self,
        name: str,
        network_id: str,
        ip_address: str,
        cpu_limit: int = 4,
        memory_limit_mb: int = 8192,
        disk_size_gb: int = 64,
        windows_version: str = "11",
        labels: Optional[Dict[str, str]] = None,
        iso_path: Optional[str] = None,
        iso_url: Optional[str] = None,
        storage_path: Optional[str] = None,
        clone_from: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        display_type: str = "desktop",
        # Network configuration
        use_dhcp: bool = False,
        gateway: Optional[str] = None,
        dns_servers: Optional[str] = None,
        dns_search: Optional[str] = None,
        # Extended dockur/windows configuration
        disk2_gb: Optional[int] = None,
        disk3_gb: Optional[int] = None,
        enable_shared_folder: bool = False,
        shared_folder_path: Optional[str] = None,
        enable_global_shared: bool = False,
        global_shared_path: Optional[str] = None,
        language: Optional[str] = None,
        keyboard: Optional[str] = None,
        region: Optional[str] = None,
        manual_install: bool = False,
        oem_script_path: Optional[str] = None,
    ) -> str:
        """
        Create a Windows VM container using dockur/windows.

        Supported Windows versions (dockur/windows auto-downloads):
        - Desktop: 11, 11l (LTSC), 11e (Enterprise), 10, 10l, 10e, 8e
        - Server: 2025, 2022, 2019, 2016, 2012, 2008
        - Legacy: 7u, vu, xp, 2k, 2003

        Args:
            name: Container name
            network_id: Network to attach to
            ip_address: Static IP address
            cpu_limit: CPU core limit (minimum 4 recommended)
            memory_limit_mb: Memory limit in MB (minimum 4096 recommended)
            disk_size_gb: Virtual disk size in GB
            windows_version: Windows version code (11, 10, 2022, etc.)
            labels: Container labels
            iso_path: Path to local Windows ISO (bind mount, skips download)
            iso_url: URL to custom Windows ISO (remote download)
            storage_path: Path to persistent storage for Windows installation
            clone_from: Path to golden image storage to clone from
            username: Optional Windows username (default: Docker)
            password: Optional Windows password (default: empty)
            display_type: Display mode - 'desktop' (VNC/web console on ports 8006/5900)
                         or 'server' (headless/RDP only)
            use_dhcp: Allow Windows to request IP via DHCP instead of static
            disk2_gb: Size of second disk in GB (appears as D: drive)
            disk3_gb: Size of third disk in GB (appears as E: drive)
            enable_shared_folder: Enable per-VM shared folder mount
            shared_folder_path: Host path for per-VM shared folder
            enable_global_shared: Mount global shared folder (read-only)
            global_shared_path: Host path for global shared folder
            language: Windows display language (e.g., "French", "German")
            keyboard: Keyboard layout (e.g., "en-US", "de-DE")
            region: Regional settings (e.g., "en-US", "fr-FR")
            manual_install: Enable manual/interactive installation mode
            oem_script_path: Path to OEM directory containing install.bat

        Returns:
            Container ID
        """
        import os
        import shutil
        from cyroid.config import get_settings
        settings = get_settings()

        image = "dockurr/windows"
        self._ensure_image(image)

        try:
            network = self.client.networks.get(network_id)
        except NotFound:
            raise ValueError(f"Network not found: {network_id}")

        # Create networking config
        networking_config = self.client.api.create_networking_config({
            network.name: self.client.api.create_endpoint_config(
                ipv4_address=ip_address
            )
        })

        # Environment for dockur/windows
        # See: https://github.com/dockur/windows for full documentation
        environment = {
            "VERSION": windows_version,
            "DISK_SIZE": f"{disk_size_gb}G",
            "CPU_CORES": str(cpu_limit),
            "RAM_SIZE": f"{memory_limit_mb}M"
        }

        # Optional username/password for Windows setup
        if username:
            environment["USERNAME"] = username
        if password:
            environment["PASSWORD"] = password

        # Network configuration
        if use_dhcp:
            environment["DHCP"] = "Y"
        else:
            # Static IP configuration - gateway and DNS
            if gateway:
                environment["GATEWAY"] = gateway
            if dns_servers:
                # dockur/windows accepts comma-separated DNS servers
                environment["DNS"] = dns_servers

        # Additional disks
        if disk2_gb:
            environment["DISK2_SIZE"] = f"{disk2_gb}G"
        if disk3_gb:
            environment["DISK3_SIZE"] = f"{disk3_gb}G"

        # Localization
        if language:
            environment["LANGUAGE"] = language
        if keyboard:
            environment["KEYBOARD"] = keyboard
        if region:
            environment["REGION"] = region

        # Manual installation mode
        if manual_install:
            environment["MANUAL"] = "Y"

        # Display type configuration
        # 'desktop' = web VNC console on port 8006 + VNC on port 5900 (default)
        # 'server' = headless mode, RDP only (no VNC/web console)
        if display_type == "server":
            environment["DISPLAY"] = "none"  # Headless mode for server environments
            logger.info(f"Windows VM {name} configured in server mode (RDP only)")
        else:
            environment["DISPLAY"] = "web"  # Web VNC console (default)
            logger.info(f"Windows VM {name} configured in desktop mode (VNC/web console)")

        # Custom ISO URL (dockur downloads from this URL)
        if iso_url:
            environment["BOOT"] = iso_url
            logger.info(f"Using custom ISO URL: {iso_url}")

        # Check if KVM is available for hardware acceleration
        kvm_available = os.path.exists("/dev/kvm")

        # Check if emulation is required (x86 VM on ARM host)
        emulated = IS_ARM  # Windows VMs are always x86

        if kvm_available and not emulated:
            environment["KVM"] = "Y"
            logger.info("KVM acceleration enabled for Windows VM")
        else:
            environment["KVM"] = "N"
            if emulated:
                logger.warning(
                    f"Windows VM '{name}' will run via x86 emulation on ARM host. "
                    "Expect significantly slower performance (10-20x)."
                )
            else:
                logger.warning("KVM not available, Windows VM will run in software emulation mode")

        # Setup volume bindings
        binds = []

        # Check for local ISO bind mount (takes priority over URL)
        # Use os.path.isfile() to ensure it's a file, not a directory
        if iso_path and os.path.isfile(iso_path):
            binds.append(f"{iso_path}:/boot.iso:ro")
            logger.info(f"Using local ISO: {iso_path}")
        elif not iso_url:
            # Check for default ISO in cache directory (only if no URL provided)
            windows_iso_dir = os.path.join(settings.iso_cache_dir, "windows-isos")
            cached_iso = os.path.join(windows_iso_dir, f"windows-{windows_version}.iso")
            if os.path.isfile(cached_iso):
                binds.append(f"{cached_iso}:/boot.iso:ro")
                logger.info(f"Using cached ISO: {cached_iso}")

        # Setup persistent storage
        if storage_path:
            os.makedirs(storage_path, exist_ok=True)

            # Clone from golden image if specified
            if clone_from and os.path.exists(clone_from):
                if not os.listdir(storage_path):  # Only clone if empty
                    logger.info(f"Cloning golden image from {clone_from} to {storage_path}")
                    for item in os.listdir(clone_from):
                        src = os.path.join(clone_from, item)
                        dst = os.path.join(storage_path, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)

            binds.append(f"{storage_path}:/storage")
            logger.info(f"Using persistent storage: {storage_path}")

            # Additional disk storage (uses same parent directory)
            if disk2_gb:
                storage2_path = os.path.join(os.path.dirname(storage_path), "storage2")
                os.makedirs(storage2_path, exist_ok=True)
                binds.append(f"{storage2_path}:/storage2")
                logger.info(f"Using secondary storage: {storage2_path}")

            if disk3_gb:
                storage3_path = os.path.join(os.path.dirname(storage_path), "storage3")
                os.makedirs(storage3_path, exist_ok=True)
                binds.append(f"{storage3_path}:/storage3")
                logger.info(f"Using tertiary storage: {storage3_path}")

        # Shared folder (per-VM)
        if enable_shared_folder and shared_folder_path:
            os.makedirs(shared_folder_path, exist_ok=True)
            binds.append(f"{shared_folder_path}:/shared")
            logger.info(f"Using per-VM shared folder: {shared_folder_path}")

        # Global shared folder (read-only for safety)
        if enable_global_shared and global_shared_path:
            os.makedirs(global_shared_path, exist_ok=True)
            binds.append(f"{global_shared_path}:/global:ro")
            logger.info(f"Using global shared folder: {global_shared_path}")

        # Post-install script from template config_script (OEM directory)
        if oem_script_path and os.path.exists(oem_script_path):
            binds.append(f"{oem_script_path}:/oem:ro")
            logger.info(f"Using OEM script directory: {oem_script_path}")

        # Parse DNS configuration for Docker container
        dns_list = None
        dns_search_list = None
        if dns_servers:
            dns_list = [s.strip() for s in dns_servers.split(",") if s.strip()]
        else:
            dns_list = ["8.8.8.8", "8.8.4.4"]  # Default external DNS
        if dns_search:
            dns_search_list = [s.strip() for s in dns_search.split(",") if s.strip()]

        # Windows containers need privileged mode for KVM
        try:
            host_config_args = {
                "cpu_count": cpu_limit,
                "mem_limit": f"{memory_limit_mb}m",
                "privileged": True,
                "cap_add": ["NET_ADMIN"],
                "restart_policy": {"Name": "unless-stopped"},
                "dns": dns_list
            }
            if dns_search_list:
                host_config_args["dns_search"] = dns_search_list
            if kvm_available:
                host_config_args["devices"] = ["/dev/kvm:/dev/kvm"]
            if binds:
                host_config_args["binds"] = binds

            container = self.client.api.create_container(
                image=image,
                name=name,
                hostname=name,
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=self.client.api.create_host_config(**host_config_args),
                environment=environment,
                labels=labels or {}
            )
            container_id = container["Id"]
            logger.info(f"Created Windows container: {name} ({container_id[:12]}) on range network")
            # NOTE: No traefik-routing connection - traefik connects to range networks for routing

            return container_id
        except APIError as e:
            logger.error(f"Failed to create Windows container {name}: {e}")
            raise

    def create_linux_vm_container(
        self,
        name: str,
        network_id: str,
        ip_address: str,
        cpu_limit: int = 2,
        memory_limit_mb: int = 2048,
        disk_size_gb: int = 64,
        linux_distro: str = "ubuntu",
        labels: Optional[Dict[str, str]] = None,
        iso_path: Optional[str] = None,
        iso_url: Optional[str] = None,
        storage_path: Optional[str] = None,
        clone_from: Optional[str] = None,
        display_type: str = "desktop",
        # Network configuration (for reference - requires manual config in VM)
        gateway: Optional[str] = None,
        dns_servers: Optional[str] = None,
        dns_search: Optional[str] = None,
        # Extended qemus/qemu configuration
        boot_mode: str = "uefi",
        disk_type: str = "scsi",
        disk2_gb: Optional[int] = None,
        disk3_gb: Optional[int] = None,
        enable_shared_folder: bool = False,
        shared_folder_path: Optional[str] = None,
        enable_global_shared: bool = False,
        global_shared_path: Optional[str] = None,
        # Linux user configuration (for cloud-init)
        linux_username: Optional[str] = None,
        linux_password: Optional[str] = None,
        linux_user_sudo: bool = True,
    ) -> str:
        """
        Create a Linux VM container using qemus/qemu.

        Provides full Linux desktop/server VMs with KVM acceleration and web VNC console,
        mirroring the dockur/windows approach for Windows VMs.

        Supported Linux distributions (via BOOT env var):
        Desktop: ubuntu, debian, fedora, alpine, arch, manjaro, opensuse, mint,
                 zorin, elementary, popos, kali, parrot, tails, rocky, alma
        Server: Any of the above work in server mode, or use custom ISO

        See: https://github.com/qemus/qemu for full documentation

        Args:
            name: Container name
            network_id: Network to attach to
            ip_address: Static IP address
            cpu_limit: CPU core limit (default 2)
            memory_limit_mb: Memory limit in MB (default 2048)
            disk_size_gb: Virtual disk size in GB
            linux_distro: Linux distribution to boot (ubuntu, debian, fedora, etc.)
            labels: Container labels
            iso_path: Path to local Linux ISO (bind mount, skips download)
            iso_url: URL to custom Linux ISO (remote download)
            storage_path: Path to persistent storage for Linux installation
            clone_from: Path to golden image storage to clone from
            display_type: Display mode - 'desktop' (VNC/web console on port 8006)
                         or 'server' (headless mode)
            boot_mode: Boot mode - 'uefi' (default) or 'legacy' (BIOS)
            disk_type: Disk interface - 'scsi' (default), 'blk', or 'ide'
            disk2_gb: Size of second disk in GB
            disk3_gb: Size of third disk in GB
            enable_shared_folder: Enable per-VM shared folder mount (via 9pfs)
            shared_folder_path: Host path for per-VM shared folder
            enable_global_shared: Mount global shared folder (read-only)
            global_shared_path: Host path for global shared folder

        Returns:
            Container ID
        """
        import os
        import shutil
        from cyroid.config import get_settings
        settings = get_settings()

        image = "qemux/qemu"
        self._ensure_image(image)

        try:
            network = self.client.networks.get(network_id)
        except NotFound:
            raise ValueError(f"Network not found: {network_id}")

        # Create networking config
        networking_config = self.client.api.create_networking_config({
            network.name: self.client.api.create_endpoint_config(
                ipv4_address=ip_address
            )
        })

        # Environment for qemus/qemu
        # See: https://github.com/qemus/qemu for full documentation
        environment = {
            "BOOT": linux_distro,
            "DISK_SIZE": f"{disk_size_gb}G",
            "CPU_CORES": str(cpu_limit),
            "RAM_SIZE": f"{memory_limit_mb}M",
            "BOOT_MODE": boot_mode.upper(),
            "DISK_TYPE": disk_type,
        }

        # Custom ISO URL (qemu downloads from this URL)
        if iso_url:
            environment["BOOT"] = iso_url
            logger.info(f"Using custom ISO URL: {iso_url}")

        # Additional disks
        if disk2_gb:
            environment["DISK2_SIZE"] = f"{disk2_gb}G"
        if disk3_gb:
            environment["DISK3_SIZE"] = f"{disk3_gb}G"

        # Display type configuration
        # 'desktop' = web VNC console on port 8006 (default)
        # 'server' = headless mode, SSH/console only
        if display_type == "server":
            environment["DISPLAY"] = "none"  # Headless mode for server environments
            logger.info(f"Linux VM {name} configured in server mode (headless)")
        else:
            environment["DISPLAY"] = "web"  # Web VNC console (default)
            logger.info(f"Linux VM {name} configured in desktop mode (VNC/web console)")

        # Check if KVM is available for hardware acceleration
        kvm_available = os.path.exists("/dev/kvm")

        # Determine if this distro needs emulation
        # ARM64-native distros: ubuntu, debian, fedora, alpine, rocky, alma, kali
        arm64_native = linux_distro.lower() in ('ubuntu', 'debian', 'fedora', 'alpine', 'rocky', 'alma', 'kali')
        emulated = IS_ARM and not arm64_native

        if kvm_available:
            if emulated:
                logger.warning(
                    f"Linux VM '{name}' ({linux_distro}) will run via x86 emulation on ARM host. "
                    "Expect significantly slower performance (10-20x)."
                )
            else:
                logger.info(f"KVM acceleration enabled for Linux VM (native {'ARM64' if IS_ARM else 'x86_64'})")
        else:
            logger.warning("KVM not available, Linux VM will run in software emulation mode")

        # Setup volume bindings
        binds = []

        # Check for local ISO bind mount (takes priority over URL)
        if iso_path and os.path.isfile(iso_path):
            binds.append(f"{iso_path}:/boot.iso:ro")
            logger.info(f"Using local ISO: {iso_path}")
        elif not iso_url:
            # Check for default ISO in cache directory (only if no URL provided)
            linux_iso_dir = os.path.join(settings.iso_cache_dir, "linux-isos")
            cached_iso = os.path.join(linux_iso_dir, f"{linux_distro}.iso")
            if os.path.isfile(cached_iso):
                binds.append(f"{cached_iso}:/boot.iso:ro")
                logger.info(f"Using cached ISO: {cached_iso}")

        # Setup persistent storage
        if storage_path:
            os.makedirs(storage_path, exist_ok=True)

            # Clone from golden image if specified
            if clone_from and os.path.exists(clone_from):
                if not os.listdir(storage_path):  # Only clone if empty
                    logger.info(f"Cloning golden image from {clone_from} to {storage_path}")
                    for item in os.listdir(clone_from):
                        src = os.path.join(clone_from, item)
                        dst = os.path.join(storage_path, item)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)

            binds.append(f"{storage_path}:/storage")
            logger.info(f"Using persistent storage: {storage_path}")

            # Additional disk storage
            if disk2_gb:
                storage2_path = os.path.join(os.path.dirname(storage_path), "storage2")
                os.makedirs(storage2_path, exist_ok=True)
                binds.append(f"{storage2_path}:/storage2")
                logger.info(f"Using secondary storage: {storage2_path}")

            if disk3_gb:
                storage3_path = os.path.join(os.path.dirname(storage_path), "storage3")
                os.makedirs(storage3_path, exist_ok=True)
                binds.append(f"{storage3_path}:/storage3")
                logger.info(f"Using tertiary storage: {storage3_path}")

        # Shared folder (per-VM) via 9pfs
        if enable_shared_folder and shared_folder_path:
            os.makedirs(shared_folder_path, exist_ok=True)
            binds.append(f"{shared_folder_path}:/shared")
            logger.info(f"Using per-VM shared folder: {shared_folder_path}")

        # Global shared folder (read-only for safety)
        if enable_global_shared and global_shared_path:
            os.makedirs(global_shared_path, exist_ok=True)
            binds.append(f"{global_shared_path}:/global:ro")
            logger.info(f"Using global shared folder: {global_shared_path}")

        # Cloud-init user configuration
        # Creates a seed ISO with user-data for automatic user setup during Linux installation
        if linux_username and linux_password and storage_path:
            import subprocess
            import crypt

            cloud_init_dir = os.path.join(storage_path, "cloud-init")
            os.makedirs(cloud_init_dir, exist_ok=True)

            # Generate password hash for security
            password_hash = crypt.crypt(linux_password, crypt.mksalt(crypt.METHOD_SHA512))

            # Create user-data file for cloud-init
            sudo_config = "sudo: ALL=(ALL) NOPASSWD:ALL" if linux_user_sudo else ""
            groups_config = "sudo,adm,cdrom,plugdev" if linux_user_sudo else "cdrom,plugdev"

            user_data = f"""#cloud-config
users:
  - name: {linux_username}
    hashed_passwd: {password_hash}
    lock_passwd: false
    shell: /bin/bash
    {sudo_config}
    groups: {groups_config}

hostname: {name}

# Disable cloud-init after first run
runcmd:
  - touch /etc/cloud/cloud-init.disabled
"""
            user_data_path = os.path.join(cloud_init_dir, "user-data")
            with open(user_data_path, "w") as f:
                f.write(user_data)

            # Create meta-data file
            meta_data = f"""instance-id: {name}
local-hostname: {name}
"""
            meta_data_path = os.path.join(cloud_init_dir, "meta-data")
            with open(meta_data_path, "w") as f:
                f.write(meta_data)

            # Generate cloud-init seed ISO
            seed_iso_path = os.path.join(cloud_init_dir, "seed.iso")
            try:
                result = subprocess.run(
                    [
                        "genisoimage", "-output", seed_iso_path,
                        "-volid", "cidata", "-joliet", "-rock",
                        user_data_path, meta_data_path
                    ],
                    check=True,
                    capture_output=True,
                    text=True
                )
                # Mount cloud-init ISO for the VM
                binds.append(f"{seed_iso_path}:/cloud-init.iso:ro")
                # Add QEMU argument to attach cloud-init ISO as a CD-ROM drive
                if "ARGUMENTS" in environment:
                    environment["ARGUMENTS"] += " -cdrom /cloud-init.iso"
                else:
                    environment["ARGUMENTS"] = "-cdrom /cloud-init.iso"
                logger.info(f"Created cloud-init configuration for user: {linux_username}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to create cloud-init ISO: {e.stderr}. User will need manual setup.")
            except FileNotFoundError:
                logger.warning("genisoimage not found. Cloud-init ISO creation skipped. User will need manual setup.")

        # Parse DNS configuration for Docker container
        dns_list = None
        dns_search_list = None
        if dns_servers:
            dns_list = [s.strip() for s in dns_servers.split(",") if s.strip()]
        else:
            dns_list = ["8.8.8.8", "8.8.4.4"]  # Default external DNS
        if dns_search:
            dns_search_list = [s.strip() for s in dns_search.split(",") if s.strip()]

        # Linux VM containers need privileged mode for KVM
        try:
            host_config_args = {
                "cpu_count": cpu_limit,
                "mem_limit": f"{memory_limit_mb}m",
                "privileged": True,
                "cap_add": ["NET_ADMIN"],
                "restart_policy": {"Name": "unless-stopped"},
                "dns": dns_list
            }
            if dns_search_list:
                host_config_args["dns_search"] = dns_search_list
            if kvm_available:
                host_config_args["devices"] = ["/dev/kvm:/dev/kvm"]
            if binds:
                host_config_args["binds"] = binds

            container = self.client.api.create_container(
                image=image,
                name=name,
                hostname=name,
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=self.client.api.create_host_config(**host_config_args),
                environment=environment,
                labels=labels or {}
            )
            container_id = container["Id"]
            logger.info(f"Created Linux VM container: {name} ({container_id[:12]}) on range network")
            # NOTE: No traefik-routing connection - traefik connects to range networks for routing

            return container_id
        except APIError as e:
            logger.error(f"Failed to create Linux VM container {name}: {e}")
            raise

    def start_container(self, container_id: str) -> bool:
        """Start a container."""
        try:
            self.client.api.start(container_id)
            logger.info(f"Started container: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"Container not found: {container_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to start container {container_id}: {e}")
            raise
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop a container."""
        try:
            self.client.api.stop(container_id, timeout=timeout)
            logger.info(f"Stopped container: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"Container not found: {container_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            raise
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """Restart a container."""
        try:
            self.client.api.restart(container_id, timeout=timeout)
            logger.info(f"Restarted container: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"Container not found: {container_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to restart container {container_id}: {e}")
            raise
    
    def remove_container(self, container_id: str, force: bool = True) -> bool:
        """Remove a container."""
        try:
            self.client.api.remove_container(container_id, force=force, v=True)
            logger.info(f"Removed container: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"Container not found: {container_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to remove container {container_id}: {e}")
            raise
    
    def get_container_status(self, container_id: str) -> Optional[str]:
        """Get container status."""
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except NotFound:
            return None
    
    def get_container_info(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed container information."""
        try:
            container = self.client.containers.get(container_id)
            return {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else None,
                "created": container.attrs.get("Created"),
                "ports": container.ports,
                "labels": container.labels
            }
        except NotFound:
            return None

    def get_container_networks(self, container_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all network interfaces for a container.

        Returns:
            List of network interface dicts with:
            - network_id: Docker network ID
            - network_name: Network name
            - ip_address: IP address on this network
            - mac_address: MAC address
            - gateway: Gateway IP (if available)
            - is_management: True if this is the traefik-routing (management) network
        """
        try:
            container = self.client.containers.get(container_id)
            networks_settings = container.attrs.get("NetworkSettings", {}).get("Networks", {})

            interfaces = []
            for net_name, net_config in networks_settings.items():
                interface = {
                    "network_id": net_config.get("NetworkID", ""),
                    "network_name": net_name,
                    "ip_address": net_config.get("IPAddress", ""),
                    "mac_address": net_config.get("MacAddress", ""),
                    "gateway": net_config.get("Gateway", ""),
                    "is_management": net_name == "traefik-routing",
                }
                interfaces.append(interface)

            return interfaces
        except NotFound:
            return None
        except APIError as e:
            logger.error(f"Failed to get network interfaces for container {container_id}: {e}")
            return None

    def connect_container_to_network(
        self,
        container_id: str,
        network_id: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Connect a container to an additional network.

        Args:
            container_id: Container ID
            network_id: Docker network ID to connect to
            ip_address: Optional static IP address

        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(network_id)
            if ip_address:
                network.connect(container_id, ipv4_address=ip_address)
            else:
                network.connect(container_id)
            logger.info(f"Connected container {container_id[:12]} to network {network.name} with IP {ip_address or 'DHCP'}")
            return True
        except NotFound as e:
            logger.error(f"Container or network not found: {e}")
            return False
        except APIError as e:
            logger.error(f"Failed to connect container to network: {e}")
            raise

    def disconnect_container_from_network(
        self,
        container_id: str,
        network_id: str
    ) -> bool:
        """
        Disconnect a container from a network.

        Args:
            container_id: Container ID
            network_id: Docker network ID to disconnect from

        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(network_id)
            network.disconnect(container_id)
            logger.info(f"Disconnected container {container_id[:12]} from network {network.name}")
            return True
        except NotFound as e:
            logger.warning(f"Container or network not found: {e}")
            return False
        except APIError as e:
            logger.error(f"Failed to disconnect container from network: {e}")
            raise

    def get_container_stats(self, container_id: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time resource statistics for a container.

        Returns:
            Dict with cpu_percent, memory_mb, memory_limit_mb, network_rx_bytes, network_tx_bytes
        """
        try:
            container = self.client.containers.get(container_id)
            if container.status != "running":
                return None

            stats = container.stats(stream=False)

            # CPU calculation
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                        stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                           stats["precpu_stats"]["system_cpu_usage"]
            # Normalize to 0-100% (average across all cores) instead of 0-N*100%
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0

            # Memory
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 0)
            memory_mb = memory_usage / (1024 * 1024)
            memory_limit_mb = memory_limit / (1024 * 1024)

            # Network
            network_stats = stats.get("networks", {})
            rx_bytes = sum(n.get("rx_bytes", 0) for n in network_stats.values())
            tx_bytes = sum(n.get("tx_bytes", 0) for n in network_stats.values())

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_mb, 2),
                "memory_limit_mb": round(memory_limit_mb, 2),
                "memory_percent": round((memory_usage / memory_limit) * 100, 2) if memory_limit > 0 else 0,
                "network_rx_bytes": rx_bytes,
                "network_tx_bytes": tx_bytes
            }
        except NotFound:
            return None
        except (KeyError, ZeroDivisionError) as e:
            logger.warning(f"Failed to calculate stats for {container_id}: {e}")
            return None
    
    def exec_command(
        self,
        container_id: str,
        command: str,
        user: str = "root",
        workdir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> tuple[int, str]:
        """
        Execute a command in a running container.
        
        Returns:
            Tuple of (exit_code, output)
        """
        try:
            container = self.client.containers.get(container_id)
            exec_result = container.exec_run(
                command,
                user=user,
                workdir=workdir,
                environment=environment,
                demux=True
            )
            stdout = exec_result.output[0] or b""
            stderr = exec_result.output[1] or b""
            output = (stdout + stderr).decode("utf-8", errors="replace")
            return exec_result.exit_code, output
        except NotFound:
            raise ValueError(f"Container not found: {container_id}")
        except APIError as e:
            logger.error(f"Failed to exec in container {container_id}: {e}")
            raise

    def configure_default_route(
        self,
        container_id: str,
        gateway_ip: str
    ) -> bool:
        """
        Configure the default route in a container to use VyOS as gateway.

        This is needed because Docker networks are created without a gateway
        (VyOS is the actual gateway), so containers don't have a default route.

        Args:
            container_id: Container ID
            gateway_ip: Gateway IP address (VyOS router)

        Returns:
            True if successful
        """
        try:
            # First check if a default route already exists
            exit_code, output = self.exec_command(
                container_id,
                "ip route show default"
            )

            if exit_code == 0 and "default" in output:
                # Delete existing default route
                self.exec_command(container_id, "ip route del default")

            # Add default route via VyOS gateway
            exit_code, output = self.exec_command(
                container_id,
                f"ip route add default via {gateway_ip}"
            )

            if exit_code != 0:
                logger.warning(f"Failed to set default route in container {container_id[:12]}: {output}")
                return False

            logger.info(f"Configured default route via {gateway_ip} in container {container_id[:12]}")
            return True
        except Exception as e:
            logger.warning(f"Failed to configure default route in container {container_id[:12]}: {e}")
            return False

    def set_linux_user_password(
        self,
        container_id: str,
        username: str,
        password: str
    ) -> bool:
        """
        Set the password for a Linux user in a running container.
        Uses chpasswd to change the password.

        Args:
            container_id: The container ID
            username: The Linux username (e.g., 'kasm-user')
            password: The new password

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use chpasswd to set the password
            command = f'echo "{username}:{password}" | chpasswd'
            exit_code, output = self.exec_command(
                container_id,
                f'/bin/sh -c \'{command}\'',
                user="root"
            )
            if exit_code == 0:
                logger.info(f"Set password for user {username} in container {container_id[:12]}")
                return True
            else:
                logger.warning(f"Failed to set password for {username}: {output}")
                return False
        except Exception as e:
            logger.warning(f"Failed to set password for {username} in {container_id[:12]}: {e}")
            return False

    def grant_sudo_privileges(
        self,
        container_id: str,
        username: str,
        nopasswd: bool = False
    ) -> bool:
        """
        Grant sudo privileges to a Linux user in a running container.

        Args:
            container_id: The container ID
            username: The Linux username (e.g., 'kasm-user')
            nopasswd: If True, allows sudo without password. Default False requires password.

        Returns:
            True if successful, False otherwise
        """
        try:
            if nopasswd:
                sudoers_line = f'{username} ALL=(ALL) NOPASSWD: ALL'
            else:
                sudoers_line = f'{username} ALL=(ALL) ALL'

            # Add user to sudoers file
            command = f'echo "{sudoers_line}" >> /etc/sudoers'
            exit_code, output = self.exec_command(
                container_id,
                f'/bin/sh -c \'{command}\'',
                user="root"
            )
            if exit_code == 0:
                logger.info(f"Granted sudo privileges to {username} in container {container_id[:12]}")
                return True
            else:
                logger.warning(f"Failed to grant sudo to {username}: {output}")
                return False
        except Exception as e:
            logger.warning(f"Failed to grant sudo to {username} in {container_id[:12]}: {e}")
            return False

    def copy_to_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str
    ) -> bool:
        """Copy a file or directory to a container."""
        import tarfile
        import io
        import os
        
        try:
            # Create tar archive
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(src_path, arcname=os.path.basename(src_path))
            tar_stream.seek(0)
            
            # Put archive into container
            self.client.api.put_archive(container_id, dest_path, tar_stream)
            logger.info(f"Copied {src_path} to {container_id[:12]}:{dest_path}")
            return True
        except (NotFound, APIError) as e:
            logger.error(f"Failed to copy to container: {e}")
            raise
    
    # Snapshot Operations
    
    def create_snapshot(
        self,
        container_id: str,
        snapshot_name: str,
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create a snapshot (Docker image) from a container.
        
        Returns:
            Image ID
        """
        try:
            container = self.client.containers.get(container_id)
            image = container.commit(
                repository=snapshot_name,
                tag="latest",
                message=f"Snapshot of {container.name}",
                conf={"Labels": labels or {}}
            )
            logger.info(f"Created snapshot: {snapshot_name} ({image.id[:12]})")
            return image.id
        except NotFound:
            raise ValueError(f"Container not found: {container_id}")
        except APIError as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise
    
    def restore_snapshot(
        self,
        image_id: str,
        container_name: str,
        network_id: str,
        ip_address: str,
        **kwargs
    ) -> str:
        """Restore a container from a snapshot image."""
        try:
            image = self.client.images.get(image_id)
        except NotFound:
            raise ValueError(f"Image not found: {image_id}")
        
        return self.create_container(
            name=container_name,
            image=image.tags[0] if image.tags else image.id,
            network_id=network_id,
            ip_address=ip_address,
            **kwargs
        )
    
    def delete_snapshot(self, image_id: str) -> bool:
        """Delete a snapshot image."""
        try:
            self.client.images.remove(image_id, force=True)
            logger.info(f"Deleted snapshot: {image_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"Image not found: {image_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to delete snapshot: {e}")
            raise
    
    # Utility Methods
    
    def _ensure_image(self, image: str) -> None:
        """Pull image if not present locally."""
        try:
            self.client.images.get(image)
            logger.debug(f"Image already present: {image}")
        except ImageNotFound:
            logger.info(f"Pulling image: {image}")
            self.client.images.pull(image)
            logger.info(f"Successfully pulled: {image}")
    
    def list_containers(
        self,
        labels: Optional[Dict[str, str]] = None,
        all: bool = True
    ) -> List[Dict[str, Any]]:
        """List containers, optionally filtered by labels."""
        filters = {}
        if labels:
            filters["label"] = [f"{k}={v}" for k, v in labels.items()]
        
        containers = self.client.containers.list(all=all, filters=filters)
        return [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else None,
                "labels": c.labels
            }
            for c in containers
        ]
    
    def list_networks(
        self,
        labels: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """List networks, optionally filtered by labels."""
        filters = {}
        if labels:
            filters["label"] = [f"{k}={v}" for k, v in labels.items()]
        
        networks = self.client.networks.list(filters=filters)
        return [
            {
                "id": n.id,
                "name": n.name,
                "driver": n.attrs.get("Driver"),
                "scope": n.attrs.get("Scope"),
                "labels": n.attrs.get("Labels", {})
            }
            for n in networks
        ]
    
    def cleanup_range(self, range_id: str) -> Dict[str, int]:
        """
        Remove all containers and networks for a range.

        Returns:
            Dict with counts of removed containers and networks
        """
        labels = {"cyroid.range_id": range_id}

        # Stop and remove containers
        containers = self.list_containers(labels=labels)
        removed_containers = 0
        for container in containers:
            if self.remove_container(container["id"]):
                removed_containers += 1

        # Remove networks - disconnect traefik first to avoid "network has active endpoints" error
        networks = self.list_networks(labels=labels)
        removed_networks = 0
        for network in networks:
            network_id = network["id"]
            # Disconnect traefik before removing network
            self.disconnect_traefik_from_network(network_id)
            # Also teardown iptables isolation rules if any
            try:
                network_info = self.get_network(network_id)
                if network_info:
                    # Get subnet from network config for isolation cleanup
                    docker_net = self.client.networks.get(network_id)
                    ipam_config = docker_net.attrs.get("IPAM", {}).get("Config", [])
                    if ipam_config:
                        subnet = ipam_config[0].get("Subnet")
                        if subnet:
                            self.teardown_network_isolation(network_id, subnet)
            except Exception as e:
                logger.warning(f"Failed to cleanup isolation for network {network_id}: {e}")

            try:
                if self.delete_network(network_id):
                    removed_networks += 1
            except Exception as e:
                logger.error(f"Failed to delete network {network_id}: {e}")

        logger.info(f"Cleaned up range {range_id}: {removed_containers} containers, {removed_networks} networks")
        return {
            "containers": removed_containers,
            "networks": removed_networks
        }

    def cleanup_all_cyroid_resources(self) -> Dict[str, Any]:
        """
        Nuclear option: Remove ALL CYROID-managed Docker resources.

        This cleans up:
        - All containers with cyroid.* labels
        - All networks with cyroid.* labels (except cyroid-management)
        - Disconnects Traefik from networks before removal
        - Tears down iptables isolation rules

        Returns:
            Dict with counts of removed resources and any errors
        """
        results = {
            "containers_removed": 0,
            "networks_removed": 0,
            "errors": []
        }

        # Step 1: Remove all CYROID VM/range containers (not infrastructure)
        logger.info("Cleanup: Removing all CYROID range containers...")
        try:
            all_containers = self.client.containers.list(all=True)
            for container in all_containers:
                labels = container.labels or {}
                # Skip CYROID infrastructure containers (api, worker, db, etc.)
                container_name = container.name or ""
                if any(infra in container_name for infra in [
                    "cyroid-api", "cyroid-worker", "cyroid-db", "cyroid-redis",
                    "cyroid-traefik", "cyroid-frontend", "cyroid-minio"
                ]):
                    continue

                # Remove containers with cyroid labels
                if labels.get("cyroid.range_id") or labels.get("cyroid.vm_id"):
                    try:
                        logger.info(f"Cleanup: Removing container {container.name}")
                        container.remove(force=True)
                        results["containers_removed"] += 1
                    except Exception as e:
                        error_msg = f"Failed to remove container {container.name}: {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Failed to list containers: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        # Step 2: Remove all CYROID networks (except management network)
        logger.info("Cleanup: Removing all CYROID networks...")
        try:
            all_networks = self.client.networks.list()
            for network in all_networks:
                network_name = network.name or ""

                # Skip non-CYROID networks and infrastructure networks
                if not network_name.startswith("cyroid-"):
                    continue
                if network_name in ["cyroid-management", "cyroid_default"]:
                    continue

                try:
                    # Disconnect traefik first
                    self.disconnect_traefik_from_network(network.id)

                    # Teardown iptables isolation if applicable
                    try:
                        ipam_config = network.attrs.get("IPAM", {}).get("Config", [])
                        if ipam_config:
                            subnet = ipam_config[0].get("Subnet")
                            if subnet:
                                self.teardown_network_isolation(network.id, subnet)
                    except Exception as e:
                        logger.warning(f"Failed to teardown isolation for {network_name}: {e}")

                    # Remove the network
                    logger.info(f"Cleanup: Removing network {network_name}")
                    network.remove()
                    results["networks_removed"] += 1
                except Exception as e:
                    error_msg = f"Failed to remove network {network_name}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Failed to list networks: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        logger.info(f"Cleanup complete: {results['containers_removed']} containers, "
                   f"{results['networks_removed']} networks removed, "
                   f"{len(results['errors'])} errors")
        return results

    def get_system_info(self) -> Dict[str, Any]:
        """Get Docker system information."""
        info = self.client.info()
        return {
            "containers": info.get("Containers", 0),
            "containers_running": info.get("ContainersRunning", 0),
            "containers_paused": info.get("ContainersPaused", 0),
            "containers_stopped": info.get("ContainersStopped", 0),
            "images": info.get("Images", 0),
            "docker_version": info.get("ServerVersion"),
            "os": info.get("OperatingSystem"),
            "architecture": info.get("Architecture"),
            "cpus": info.get("NCPU"),
            "memory_bytes": info.get("MemTotal")
        }

    # Image Caching Methods

    def cache_linux_image(self, image: str) -> Dict[str, Any]:
        """
        Pre-pull and cache a Linux container image.

        Args:
            image: Docker image name (e.g., "ubuntu:22.04")

        Returns:
            Dict with image info
        """
        logger.info(f"Caching Linux image: {image}")
        pulled_image = self.client.images.pull(image)
        return {
            "id": pulled_image.id,
            "tags": pulled_image.tags,
            "size_bytes": pulled_image.attrs.get("Size", 0),
            "created": pulled_image.attrs.get("Created")
        }

    def list_cached_images(self) -> List[Dict[str, Any]]:
        """List all cached Docker images."""
        images = self.client.images.list()
        return [
            {
                "id": img.id,
                "tags": img.tags,
                "size_bytes": img.attrs.get("Size", 0),
                "created": img.attrs.get("Created")
            }
            for img in images
            if img.tags  # Only show tagged images
        ]

    def get_windows_iso_cache_status(self) -> Dict[str, Any]:
        """
        Check status of cached Windows ISOs.

        Returns:
            Dict with cached ISOs and their sizes
        """
        import os
        from cyroid.config import get_settings
        settings = get_settings()

        cached_isos = []
        # Windows ISOs are stored in a subdirectory
        windows_iso_dir = os.path.join(settings.iso_cache_dir, "windows-isos")

        if os.path.exists(windows_iso_dir):
            for filename in os.listdir(windows_iso_dir):
                if filename.endswith('.iso'):
                    filepath = os.path.join(windows_iso_dir, filename)
                    cached_isos.append({
                        "filename": filename,
                        "path": filepath,
                        "size_bytes": os.path.getsize(filepath),
                        "size_gb": round(os.path.getsize(filepath) / (1024**3), 2)
                    })

        return {
            "cache_dir": windows_iso_dir,
            "isos": cached_isos,
            "total_count": len(cached_isos)
        }

    def get_linux_iso_cache_status(self) -> Dict[str, Any]:
        """
        Check status of cached Linux ISOs.

        Returns:
            Dict with cached ISOs and their sizes
        """
        import os
        from cyroid.config import get_settings
        settings = get_settings()

        cached_isos = []
        # Linux ISOs are stored in a subdirectory
        linux_iso_dir = os.path.join(settings.iso_cache_dir, "linux-isos")

        if os.path.exists(linux_iso_dir):
            for filename in os.listdir(linux_iso_dir):
                if filename.endswith('.iso') or filename.endswith('.img') or filename.endswith('.qcow2'):
                    filepath = os.path.join(linux_iso_dir, filename)
                    cached_isos.append({
                        "filename": filename,
                        "path": filepath,
                        "size_bytes": os.path.getsize(filepath),
                        "size_gb": round(os.path.getsize(filepath) / (1024**3), 2)
                    })

        return {
            "cache_dir": linux_iso_dir,
            "isos": cached_isos,
            "total_count": len(cached_isos)
        }

    def get_all_iso_cache_status(self) -> Dict[str, Any]:
        """
        Get combined status of all ISO caches (Windows and Linux).

        Returns:
            Dict with both Windows and Linux ISO caches
        """
        windows_cache = self.get_windows_iso_cache_status()
        linux_cache = self.get_linux_iso_cache_status()

        return {
            "windows": windows_cache,
            "linux": linux_cache,
            "total_count": windows_cache["total_count"] + linux_cache["total_count"],
            "total_size_gb": round(
                sum(iso["size_gb"] for iso in windows_cache["isos"]) +
                sum(iso["size_gb"] for iso in linux_cache["isos"]),
                2
            )
        }

    def get_golden_images_status(self, os_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Check status of golden images (pre-installed VM templates).
        Works for both Windows (dockur/windows) and Linux (qemus/qemu) VMs.

        Args:
            os_type: Filter by OS type ('windows', 'linux', or None for all)

        Returns:
            Dict with golden images and their sizes
        """
        import os
        from cyroid.config import get_settings
        settings = get_settings()

        golden_images = []
        template_dir = settings.template_storage_dir

        if os.path.exists(template_dir):
            for dirname in os.listdir(template_dir):
                dirpath = os.path.join(template_dir, dirname)
                if os.path.isdir(dirpath):
                    # Determine OS type from directory name or metadata
                    detected_os = "windows" if dirname.startswith("win") else "linux"

                    # Filter by OS type if specified
                    if os_type and detected_os != os_type:
                        continue

                    # Calculate total size of the golden image
                    total_size = 0
                    for root, dirs, files in os.walk(dirpath):
                        for f in files:
                            total_size += os.path.getsize(os.path.join(root, f))

                    golden_images.append({
                        "name": dirname,
                        "path": dirpath,
                        "size_bytes": total_size,
                        "size_gb": round(total_size / (1024**3), 2),
                        "os_type": detected_os
                    })

        return {
            "template_dir": template_dir,
            "golden_images": golden_images,
            "total_count": len(golden_images)
        }

    def create_golden_image(
        self,
        container_id: str,
        golden_image_name: str,
        os_type: str = "windows"
    ) -> Dict[str, Any]:
        """
        Create a golden image from a running VM container.
        This saves the /storage directory for reuse.
        Works for both Windows (dockur/windows) and Linux (qemus/qemu) VMs.

        Args:
            container_id: ID of the VM container with completed installation
            golden_image_name: Name for the golden image
            os_type: Type of OS ('windows' or 'linux')

        Returns:
            Dict with golden image info
        """
        import os
        import shutil
        from cyroid.config import get_settings
        settings = get_settings()

        # Get container info
        container = self.client.containers.get(container_id)
        mounts = container.attrs.get("Mounts", [])

        # Find the /storage mount
        storage_mount = None
        for mount in mounts:
            if mount.get("Destination") == "/storage":
                storage_mount = mount.get("Source")
                break

        if not storage_mount:
            raise ValueError("Container does not have a /storage mount")

        # Create golden image directory (prefix with OS type for organization)
        if not golden_image_name.startswith(("win", "linux-")):
            prefix = "win-" if os_type == "windows" else "linux-"
            golden_image_name = f"{prefix}{golden_image_name}"

        golden_dir = os.path.join(settings.template_storage_dir, golden_image_name)
        os.makedirs(golden_dir, exist_ok=True)

        # Copy storage to golden image
        logger.info(f"Creating {os_type} golden image from {storage_mount} to {golden_dir}")
        for item in os.listdir(storage_mount):
            src = os.path.join(storage_mount, item)
            dst = os.path.join(golden_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        # Calculate size
        total_size = 0
        for root, dirs, files in os.walk(golden_dir):
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))

        return {
            "name": golden_image_name,
            "path": golden_dir,
            "size_bytes": total_size,
            "size_gb": round(total_size / (1024**3), 2),
            "os_type": os_type
        }

    def create_container_snapshot(
        self,
        container_id: str,
        snapshot_name: str,
        tag: str = "latest"
    ) -> Dict[str, Any]:
        """
        Create a Docker image snapshot from a running container using docker commit.
        Works for any container type (Linux, custom, etc.).

        Args:
            container_id: ID of the container to snapshot
            snapshot_name: Name for the new image (e.g., "cyroid/mytemplate")
            tag: Tag for the image (default: "latest")

        Returns:
            Dict with snapshot image info
        """
        # Get container
        container = self.client.containers.get(container_id)

        # Create the snapshot image
        full_tag = f"{snapshot_name}:{tag}"
        logger.info(f"Creating container snapshot: {full_tag} from container {container_id}")

        # Commit the container to create a new image
        image = container.commit(
            repository=snapshot_name,
            tag=tag,
            message=f"Snapshot created from container {container_id}",
            author="cyroid"
        )

        # Get image details
        image_info = self.client.images.get(image.id)
        size_bytes = image_info.attrs.get("Size", 0)

        return {
            "name": full_tag,
            "id": image.id,
            "short_id": image.short_id,
            "size_bytes": size_bytes,
            "size_gb": round(size_bytes / (1024**3), 2),
            "type": "docker"
        }

    def get_all_snapshots(self) -> Dict[str, Any]:
        """
        Get all snapshots - both Windows golden images and Docker container snapshots.

        Returns:
            Dict with both types of snapshots
        """
        import os
        from cyroid.config import get_settings

        settings = get_settings()

        # Get Windows golden images
        golden_images = self.get_golden_images_status()

        # Get Docker snapshots (images with cyroid/ prefix or cyroid labels)
        docker_snapshots = []
        for image in self.client.images.list():
            tags = image.tags
            labels = image.labels or {}

            # Check if it's a cyroid snapshot
            is_snapshot = False
            for tag in tags:
                if tag.startswith("cyroid/snapshot:") or tag.startswith("cyroid-snapshot/"):
                    is_snapshot = True
                    break

            # Also check labels
            if labels.get("cyroid.snapshot") == "true":
                is_snapshot = True

            if is_snapshot:
                docker_snapshots.append({
                    "id": image.id,
                    "short_id": image.short_id,
                    "tags": tags,
                    "size_bytes": image.attrs.get("Size", 0),
                    "size_gb": round(image.attrs.get("Size", 0) / (1024**3), 2),
                    "created": image.attrs.get("Created"),
                    "type": "docker"
                })

        return {
            "windows_golden_images": golden_images["golden_images"],
            "docker_snapshots": docker_snapshots,
            "total_windows": golden_images["total_count"],
            "total_docker": len(docker_snapshots),
            "template_dir": golden_images["template_dir"]
        }


    # =========================================================================
    # DinD Range Operations (operate inside range's DinD container)
    # =========================================================================

    async def create_range_network_dind(
        self,
        range_id: str,
        docker_url: str,
        name: str,
        subnet: str,
        gateway: Optional[str] = None,
        internal: bool = True,
        labels: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create Docker network inside a range's DinD container.

        Uses EXACT subnet from blueprint - no IP translation needed.
        This is the DinD-aware version of create_network().

        Args:
            range_id: Range identifier
            docker_url: Docker URL for the range's DinD
            name: Network name
            subnet: CIDR notation (exact blueprint subnet)
            gateway: Gateway IP (VyOS will use this)
            internal: If True, no external connectivity
            labels: Optional labels

        Returns:
            Network ID
        """
        range_client = self.get_range_client_sync(range_id, docker_url)

        # Calculate bridge IP (.254) leaving .1 for VyOS
        subnet_obj = ipaddress.ip_network(subnet, strict=False)
        hosts = list(subnet_obj.hosts())
        bridge_ip = str(hosts[-1]) if hosts else gateway

        ipam_pool = docker.types.IPAMPool(
            subnet=subnet,
            gateway=bridge_ip
        )
        ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])

        try:
            network = range_client.networks.create(
                name=name,
                driver="bridge",
                internal=internal,
                ipam=ipam_config,
                labels=labels or {},
                attachable=True
            )
            logger.info(f"Created network '{name}' ({subnet}) in range {range_id} DinD")
            return network.id
        except APIError as e:
            logger.error(f"Failed to create network {name} in DinD: {e}")
            raise

    async def delete_range_network_dind(
        self,
        range_id: str,
        docker_url: str,
        network_id: str
    ) -> bool:
        """Delete Docker network inside a range's DinD container."""
        range_client = self.get_range_client_sync(range_id, docker_url)

        try:
            network = range_client.networks.get(network_id)
            network.remove()
            logger.info(f"Deleted network {network_id[:12]} from range {range_id} DinD")
            return True
        except NotFound:
            logger.warning(f"Network {network_id} not found in DinD")
            return False
        except APIError as e:
            logger.error(f"Failed to delete network in DinD: {e}")
            raise

    async def list_range_networks_dind(
        self,
        range_id: str,
        docker_url: str
    ) -> List[Dict[str, Any]]:
        """List all networks in a range's DinD container."""
        range_client = self.get_range_client_sync(range_id, docker_url)
        networks = range_client.networks.list()

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
            if n.name not in ("bridge", "host", "none")
        ]

    async def create_range_container_dind(
        self,
        range_id: str,
        docker_url: str,
        name: str,
        image: str,
        network_name: str,
        ip_address: str,
        cpu_limit: int = 2,
        memory_limit_mb: int = 2048,
        volumes: Optional[Dict[str, Dict]] = None,
        environment: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
        privileged: bool = False,
        hostname: Optional[str] = None,
        dns_servers: Optional[str] = None,
        dns_search: Optional[str] = None,
    ) -> str:
        """
        Create a container inside a range's DinD container.

        Uses EXACT IP from blueprint - no IP translation needed.

        Args:
            range_id: Range identifier
            docker_url: Docker URL for the range's DinD
            name: Container name
            image: Docker image
            network_name: Network to attach to (inside DinD)
            ip_address: Static IP address (exact blueprint IP)
            Other args same as create_container()

        Returns:
            Container ID
        """
        range_client = self.get_range_client_sync(range_id, docker_url)

        # Pull image if not present in DinD
        try:
            range_client.images.get(image)
        except ImageNotFound:
            logger.info(f"Pulling image {image} into DinD for range {range_id}")
            range_client.images.pull(image)

        # Get network
        try:
            network = range_client.networks.get(network_name)
        except NotFound:
            raise ValueError(f"Network {network_name} not found in DinD")

        # Create networking config
        networking_config = range_client.api.create_networking_config({
            network.name: range_client.api.create_endpoint_config(
                ipv4_address=ip_address
            )
        })

        # Parse DNS
        dns_list = [s.strip() for s in dns_servers.split(",") if s.strip()] if dns_servers else ["8.8.8.8", "8.8.4.4"]
        dns_search_list = [s.strip() for s in dns_search.split(",") if s.strip()] if dns_search else None

        if environment is None:
            environment = {}

        host_config_args = {
            "cpu_count": cpu_limit,
            "mem_limit": f"{memory_limit_mb}m",
            "binds": volumes,
            "privileged": privileged,
            "cap_add": ["NET_ADMIN"],
            "restart_policy": {"Name": "unless-stopped"},
            "dns": dns_list
        }
        if dns_search_list:
            host_config_args["dns_search"] = dns_search_list

        try:
            container = range_client.api.create_container(
                image=image,
                name=name,
                hostname=hostname or name,
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=range_client.api.create_host_config(**host_config_args),
                environment=environment,
                labels=labels or {}
            )
            container_id = container["Id"]
            logger.info(f"Created container '{name}' in range {range_id} DinD with IP {ip_address}")
            return container_id
        except APIError as e:
            logger.error(f"Failed to create container in DinD: {e}")
            raise

    async def start_range_container_dind(
        self,
        range_id: str,
        docker_url: str,
        container_id: str
    ) -> bool:
        """Start a container inside a range's DinD."""
        range_client = self.get_range_client_sync(range_id, docker_url)
        try:
            range_client.api.start(container_id)
            logger.info(f"Started container {container_id[:12]} in range {range_id} DinD")
            return True
        except NotFound:
            return False
        except APIError as e:
            logger.error(f"Failed to start container in DinD: {e}")
            raise

    async def stop_range_container_dind(
        self,
        range_id: str,
        docker_url: str,
        container_id: str,
        timeout: int = 10
    ) -> bool:
        """Stop a container inside a range's DinD."""
        range_client = self.get_range_client_sync(range_id, docker_url)
        try:
            range_client.api.stop(container_id, timeout=timeout)
            logger.info(f"Stopped container {container_id[:12]} in range {range_id} DinD")
            return True
        except NotFound:
            return False
        except APIError as e:
            logger.error(f"Failed to stop container in DinD: {e}")
            raise

    async def remove_range_container_dind(
        self,
        range_id: str,
        docker_url: str,
        container_id: str,
        force: bool = True
    ) -> bool:
        """Remove a container inside a range's DinD."""
        range_client = self.get_range_client_sync(range_id, docker_url)
        try:
            range_client.api.remove_container(container_id, force=force, v=True)
            logger.info(f"Removed container {container_id[:12]} from range {range_id} DinD")
            return True
        except NotFound:
            return False
        except APIError as e:
            logger.error(f"Failed to remove container in DinD: {e}")
            raise

    async def get_range_container_status_dind(
        self,
        range_id: str,
        docker_url: str,
        container_id: str
    ) -> Optional[str]:
        """Get container status inside a range's DinD."""
        range_client = self.get_range_client_sync(range_id, docker_url)
        try:
            container = range_client.containers.get(container_id)
            return container.status
        except NotFound:
            return None

    async def list_range_containers_dind(
        self,
        range_id: str,
        docker_url: str
    ) -> List[Dict[str, Any]]:
        """List all containers in a range's DinD."""
        range_client = self.get_range_client_sync(range_id, docker_url)
        containers = range_client.containers.list(all=True)

        result = []
        for container in containers:
            networks = {}
            for net_name, net_info in container.attrs.get("NetworkSettings", {}).get("Networks", {}).items():
                if net_name not in ("bridge", "host", "none"):
                    networks[net_name] = net_info.get("IPAddress")

            result.append({
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else None,
                "networks": networks,
            })

        return result

    async def transfer_image_to_dind(
        self,
        range_id: str,
        docker_url: str,
        image: str,
        pull_if_missing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> bool:
        """
        Transfer a Docker image from host to a DinD container.

        This method exports the image from the host Docker daemon and imports
        it into the DinD container's Docker daemon. This works for:
        - Locally built images
        - Snapshots saved as images
        - Images without registry access in DinD

        Args:
            range_id: Range identifier
            docker_url: DinD Docker URL (tcp://ip:port)
            image: Image name/tag to transfer
            pull_if_missing: If True, pull image to host if not found locally
            progress_callback: Optional callback for progress reporting.
                Signature: (transferred: int, total: int, status: str) -> None
                Status values: 'starting', 'found_on_host', 'pulling_to_host',
                'pulled_to_host', 'already_exists', 'transferring', 'complete', 'error'

        Returns:
            True if transfer succeeded, False otherwise
        """
        # Helper to safely call progress callback
        def report_progress(transferred: int, total: int, status: str) -> None:
            if progress_callback:
                try:
                    progress_callback(transferred, total, status)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

        logger.info(f"Transferring image '{image}' to DinD for range {range_id}")
        report_progress(0, 0, 'starting')

        image_size = 0

        # Check if image exists on host
        try:
            host_image = self.client.images.get(image)
            image_size = host_image.attrs.get('Size', 0)
            logger.debug(f"Image '{image}' found on host (size: {image_size})")
            report_progress(0, image_size, 'found_on_host')
        except docker.errors.ImageNotFound:
            if pull_if_missing:
                logger.info(f"Image '{image}' not on host, pulling...")
                report_progress(0, 0, 'pulling_to_host')
                try:
                    host_image = self.client.images.pull(image)
                    image_size = host_image.attrs.get('Size', 0)
                    logger.info(f"Pulled '{image}' to host (size: {image_size})")
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
            # Use generator to stream in chunks for large images
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
            report_progress(0, image_size, 'error')
            return False

    async def pull_image_to_dind(
        self,
        range_id: str,
        docker_url: str,
        image: str
    ) -> None:
        """
        Pull/transfer a Docker image into a range's DinD container.

        First attempts to transfer from host, falls back to pulling directly
        into DinD if transfer fails.
        """
        # Try host-to-DinD transfer first (handles local images and snapshots)
        if await self.transfer_image_to_dind(range_id, docker_url, image):
            return

        # Fallback: try direct pull into DinD (requires internet in DinD)
        logger.info(f"Falling back to direct pull of '{image}' into DinD")
        range_client = self.get_range_client_sync(range_id, docker_url)
        range_client.images.pull(image)
        logger.info(f"Successfully pulled '{image}' into DinD")


# Singleton instance
_docker_service: Optional[DockerService] = None


def get_docker_service() -> DockerService:
    """Get the Docker service singleton."""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
