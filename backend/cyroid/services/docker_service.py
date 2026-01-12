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
        windows_version: str = "win10",
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create a Windows VM container using dockur/windows.
        
        Args:
            name: Container name
            network_id: Network to attach to
            ip_address: Static IP address
            cpu_limit: CPU core limit (minimum 4 recommended)
            memory_limit_mb: Memory limit in MB (minimum 4096 recommended)
            disk_size_gb: Virtual disk size in GB
            windows_version: Windows version (win10, win11, win2022, etc.)
            labels: Container labels
            
        Returns:
            Container ID
        """
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
        environment = {
            "VERSION": windows_version,
            "DISK_SIZE": f"{disk_size_gb}G",
            "CPU_CORES": str(cpu_limit),
            "RAM_SIZE": f"{memory_limit_mb}M"
        }
        
        # Windows containers need privileged mode for KVM
        try:
            container = self.client.api.create_container(
                image=image,
                name=name,
                hostname=name,
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=self.client.api.create_host_config(
                    cpu_count=cpu_limit,
                    mem_limit=f"{memory_limit_mb}m",
                    privileged=True,
                    devices=["/dev/kvm:/dev/kvm"],
                    cap_add=["NET_ADMIN"],
                    restart_policy={"Name": "unless-stopped"}
                ),
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


# Singleton instance
_docker_service: Optional[DockerService] = None


def get_docker_service() -> DockerService:
    """Get the Docker service singleton."""
    global _docker_service
    if _docker_service is None:
        _docker_service = DockerService()
    return _docker_service
