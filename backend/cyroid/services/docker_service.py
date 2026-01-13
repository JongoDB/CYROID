# cyroid/services/docker_service.py
"""
Docker orchestration service for managing containers and networks.
Supports Linux containers and dockur/windows for Windows VMs.
"""
import docker
from docker.errors import APIError, NotFound, ImageNotFound
from typing import Optional, Dict, List, Any
import logging
import time
import ipaddress

logger = logging.getLogger(__name__)


class DockerService:
    """Service for managing Docker containers and networks."""
    
    def __init__(self):
        self.client = docker.from_env()
        self._verify_connection()
    
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
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create a Docker network with the specified configuration.
        
        Args:
            name: Network name
            subnet: CIDR notation (e.g., "10.0.1.0/24")
            gateway: Gateway IP address
            internal: If True, no external connectivity (isolation)
            labels: Optional labels for the network
            
        Returns:
            Network ID
        """
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
            logger.info(f"Created network: {name} ({network.id[:12]})")
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
        hostname: Optional[str] = None
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
            
        Returns:
            Container ID
        """
        # Pull image if not present
        self._ensure_image(image)
        
        # Get network for attachment
        try:
            network = self.client.networks.get(network_id)
        except NotFound:
            raise ValueError(f"Network not found: {network_id}")
        
        # Create networking config with static IP
        networking_config = self.client.api.create_networking_config({
            network.name: self.client.api.create_endpoint_config(
                ipv4_address=ip_address
            )
        })
        
        # Create container
        try:
            container = self.client.api.create_container(
                image=image,
                name=name,
                hostname=hostname or name,
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=self.client.api.create_host_config(
                    cpu_count=cpu_limit,
                    mem_limit=f"{memory_limit_mb}m",
                    binds=volumes,
                    privileged=privileged,
                    restart_policy={"Name": "unless-stopped"}
                ),
                environment=environment,
                labels=labels or {}
            )
            container_id = container["Id"]
            logger.info(f"Created container: {name} ({container_id[:12]})")
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
        # Extended dockur/windows configuration
        use_dhcp: bool = False,
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

        # Extended dockur/windows configuration
        # DHCP mode
        if use_dhcp:
            environment["DHCP"] = "Y"

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
        if not kvm_available:
            logger.warning("KVM not available, Windows VM will run in software emulation mode (slower)")
            environment["KVM"] = "N"

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

        # Windows containers need privileged mode for KVM
        try:
            host_config_args = {
                "cpu_count": cpu_limit,
                "mem_limit": f"{memory_limit_mb}m",
                "privileged": True,
                "cap_add": ["NET_ADMIN"],
                "restart_policy": {"Name": "unless-stopped"}
            }
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
            logger.info(f"Created Windows container: {name} ({container_id[:12]})")
            return container_id
        except APIError as e:
            logger.error(f"Failed to create Windows container {name}: {e}")
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
            cpu_count = stats["cpu_stats"].get("online_cpus", 1)
            cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0 if system_delta > 0 else 0.0

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
        
        # Remove networks
        networks = self.list_networks(labels=labels)
        removed_networks = 0
        for network in networks:
            if self.delete_network(network["id"]):
                removed_networks += 1
        
        logger.info(f"Cleaned up range {range_id}: {removed_containers} containers, {removed_networks} networks")
        return {
            "containers": removed_containers,
            "networks": removed_networks
        }
    
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

    def get_golden_images_status(self) -> Dict[str, Any]:
        """
        Check status of Windows golden images (pre-installed templates).

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
                    # Calculate total size of the golden image
                    total_size = 0
                    for root, dirs, files in os.walk(dirpath):
                        for f in files:
                            total_size += os.path.getsize(os.path.join(root, f))

                    golden_images.append({
                        "name": dirname,
                        "path": dirpath,
                        "size_bytes": total_size,
                        "size_gb": round(total_size / (1024**3), 2)
                    })

        return {
            "template_dir": template_dir,
            "golden_images": golden_images,
            "total_count": len(golden_images)
        }

    def create_golden_image(
        self,
        container_id: str,
        golden_image_name: str
    ) -> Dict[str, Any]:
        """
        Create a golden image from a running Windows container.
        This saves the /storage directory for reuse.

        Args:
            container_id: ID of the Windows container with completed installation
            golden_image_name: Name for the golden image

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

        # Create golden image directory
        golden_dir = os.path.join(settings.template_storage_dir, golden_image_name)
        os.makedirs(golden_dir, exist_ok=True)

        # Copy storage to golden image
        logger.info(f"Creating golden image from {storage_mount} to {golden_dir}")
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
            "type": "windows"
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


# Singleton instance
_docker_service: Optional[DockerService] = None


def get_docker_service() -> DockerService:
    """Get the Docker service singleton."""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
