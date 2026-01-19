# cyroid/services/vnc_proxy_service.py
"""VNC Proxy Service for DinD Console Access.

This service deploys a lightweight nginx proxy container inside each DinD
to expose VNC ports on the DinD's management IP, which Traefik CAN reach.

Problem: Traefik runs on the host but VMs are inside DinD containers.
Traefik cannot directly route to containers inside DinD because they're
in a separate Docker daemon.

Solution: Deploy nginx:alpine inside DinD with TCP stream proxying to
forward traffic from the DinD management IP to VMs' VNC ports.

Architecture:
    Traefik (host) -> 172.30.1.5:15900 -> nginx (in DinD) -> vm-container:8006
"""

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cyroid.services.docker_service import DockerService

logger = logging.getLogger(__name__)

# Base port for VNC proxy - VMs will be mapped to 15900, 15901, 15902, etc.
VNC_PROXY_BASE_PORT = 15900

# Nginx image to use for proxy
NGINX_IMAGE = "nginx:alpine"

# Container name prefix
PROXY_CONTAINER_PREFIX = "cyroid-vnc-proxy"


class VNCProxyService:
    """Manages VNC proxy containers for DinD-based range deployments.

    Each range gets a single nginx proxy container that forwards traffic
    from the DinD management IP to the VNC ports of VMs inside the DinD.
    """

    def __init__(self, docker_service: "DockerService"):
        """
        Initialize VNC proxy service.

        Args:
            docker_service: DockerService instance for container operations.
        """
        self.docker_service = docker_service

    async def deploy_vnc_proxy(
        self,
        range_id: str,
        docker_url: str,
        dind_mgmt_ip: str,
        vm_ports: list[dict],
    ) -> dict:
        """
        Deploy VNC proxy container inside DinD.

        Creates an nginx:alpine container with TCP stream configuration
        to proxy VNC traffic from the DinD management IP to VMs.

        Args:
            range_id: Range identifier (UUID string)
            docker_url: Docker URL for the DinD container (tcp://ip:port)
            dind_mgmt_ip: DinD management IP address (reachable from host)
            vm_ports: List of VM port configurations, each with:
                - vm_id: VM identifier
                - hostname: VM hostname
                - vnc_port: VNC port inside the VM container (e.g., 8006, 6901)
                - container_name: Name of the VM container inside DinD

        Returns:
            dict with:
                - container_id: ID of the proxy container
                - port_mappings: dict mapping vm_id to proxy info:
                    - proxy_port: External port on DinD management IP
                    - proxy_host: DinD management IP
                    - original_port: Original VNC port in VM container
        """
        logger.info(f"Deploying VNC proxy for range {range_id} at {docker_url}")

        # Get Docker client for the DinD container
        range_client = self.docker_service.get_range_client_sync(range_id, docker_url)

        # Generate nginx configuration and port mappings
        nginx_config, port_mappings = self._generate_nginx_config(vm_ports)

        # Add proxy host to all mappings
        for vm_id in port_mappings:
            port_mappings[vm_id]["proxy_host"] = dind_mgmt_ip

        # Create temporary directory for nginx config
        config_dir = tempfile.mkdtemp(prefix="cyroid-vnc-proxy-")
        config_path = Path(config_dir) / "nginx.conf"

        try:
            # Write nginx config
            config_path.write_text(nginx_config)
            logger.debug(f"Generated nginx config at {config_path}")

            # Prepare port mappings for Docker
            # Map each proxy port to the same port on all interfaces
            docker_ports = {}
            for vm_id, mapping in port_mappings.items():
                port = mapping["proxy_port"]
                docker_ports[f"{port}/tcp"] = port

            # Create container name
            short_id = str(range_id).replace("-", "")[:12]
            container_name = f"{PROXY_CONTAINER_PREFIX}-{short_id}"

            # Labels for identification
            labels = {
                "cyroid.type": "vnc-proxy",
                "cyroid.range_id": str(range_id),
            }

            # Volume mount for nginx config
            volumes = {
                str(config_path): {"bind": "/etc/nginx/nginx.conf", "mode": "ro"}
            }

            # Create and start the proxy container
            container = range_client.containers.run(
                image=NGINX_IMAGE,
                name=container_name,
                detach=True,
                ports=docker_ports,
                volumes=volumes,
                labels=labels,
                network_mode="bridge",  # Use default bridge to access all VM containers
                restart_policy={"Name": "unless-stopped"},
            )

            logger.info(
                f"Deployed VNC proxy container {container.id[:12]} for range {range_id}"
            )

            return {
                "container_id": container.id,
                "container_name": container_name,
                "port_mappings": port_mappings,
            }

        except Exception as e:
            logger.error(f"Failed to deploy VNC proxy for range {range_id}: {e}")
            raise

    async def remove_vnc_proxy(self, range_id: str, docker_url: str) -> None:
        """
        Remove VNC proxy container from DinD.

        Args:
            range_id: Range identifier
            docker_url: Docker URL for the DinD container
        """
        logger.info(f"Removing VNC proxy for range {range_id}")

        try:
            range_client = self.docker_service.get_range_client_sync(range_id, docker_url)

            short_id = str(range_id).replace("-", "")[:12]
            container_name = f"{PROXY_CONTAINER_PREFIX}-{short_id}"

            container = range_client.containers.get(container_name)
            container.stop(timeout=5)
            container.remove(force=True)

            logger.info(f"Removed VNC proxy container for range {range_id}")

        except Exception as e:
            # Container might not exist, log but don't fail
            logger.warning(f"Error removing VNC proxy for range {range_id}: {e}")

    async def update_vnc_proxy(
        self,
        range_id: str,
        docker_url: str,
        dind_mgmt_ip: str,
        vm_ports: list[dict],
    ) -> dict:
        """
        Update VNC proxy by removing old and deploying new.

        This is called when VMs are added/removed from a range to update
        the proxy configuration.

        Args:
            range_id: Range identifier
            docker_url: Docker URL for the DinD container
            dind_mgmt_ip: DinD management IP address
            vm_ports: Updated list of VM port configurations

        Returns:
            dict with container_id and port_mappings (same as deploy_vnc_proxy)
        """
        logger.info(f"Updating VNC proxy for range {range_id}")

        # Remove existing proxy
        await self.remove_vnc_proxy(range_id, docker_url)

        # Deploy new proxy with updated config
        return await self.deploy_vnc_proxy(
            range_id=range_id,
            docker_url=docker_url,
            dind_mgmt_ip=dind_mgmt_ip,
            vm_ports=vm_ports,
        )

    def get_vnc_url_for_vm(
        self, vm_id: str, port_mappings: dict[str, dict]
    ) -> Optional[str]:
        """
        Get VNC URL for a specific VM.

        Args:
            vm_id: VM identifier
            port_mappings: Port mappings from deploy_vnc_proxy result

        Returns:
            URL string (e.g., "http://172.30.1.5:15900") or None if VM not found
        """
        if vm_id not in port_mappings:
            return None

        mapping = port_mappings[vm_id]
        return f"http://{mapping['proxy_host']}:{mapping['proxy_port']}"

    def _generate_nginx_config(
        self, vm_ports: list[dict]
    ) -> tuple[str, dict[str, dict]]:
        """
        Generate nginx stream configuration for TCP proxying.

        Args:
            vm_ports: List of VM port configurations with:
                - vm_id: VM identifier
                - hostname: VM hostname
                - vnc_port: VNC port inside the VM container
                - container_name: Name of the VM container

        Returns:
            tuple of (nginx_config_string, port_mappings_dict)
        """
        port_mappings = {}
        upstream_blocks = []
        server_blocks = []

        for idx, vm_info in enumerate(vm_ports):
            vm_id = vm_info["vm_id"]
            container_name = vm_info["container_name"]
            vnc_port = vm_info["vnc_port"]
            external_port = VNC_PROXY_BASE_PORT + idx

            # Create short ID for upstream name (nginx doesn't like dashes)
            vm_id_short = vm_id.replace("-", "")[:8]

            # Record port mapping
            port_mappings[vm_id] = {
                "proxy_port": external_port,
                "original_port": vnc_port,
            }

            # Generate upstream block
            upstream_blocks.append(
                f"""    upstream vnc_{vm_id_short} {{
        server {container_name}:{vnc_port};
    }}"""
            )

            # Generate server block
            server_blocks.append(
                f"""    server {{
        listen {external_port};
        proxy_pass vnc_{vm_id_short};
        proxy_timeout 3600s;
    }}"""
            )

        # Combine into full nginx config
        if upstream_blocks:
            stream_content = "\n".join(upstream_blocks) + "\n" + "\n".join(server_blocks)
            nginx_config = f"""# Auto-generated nginx stream config for VNC proxying
# Range VNC Proxy - forwards traffic to VM containers

events {{
    worker_connections 1024;
}}

stream {{
{stream_content}
}}
"""
        else:
            # Empty config when no VMs
            nginx_config = """# Auto-generated nginx stream config for VNC proxying
# No VMs configured

events {
    worker_connections 1024;
}

stream {
    # No upstream servers configured
}
"""

        return nginx_config, port_mappings


# Singleton instance for dependency injection
_vnc_proxy_service: Optional[VNCProxyService] = None


def get_vnc_proxy_service(
    docker_service: Optional["DockerService"] = None,
) -> VNCProxyService:
    """
    Get or create the VNC proxy service singleton.

    Args:
        docker_service: Optional DockerService instance. If not provided,
                       will be created on demand.

    Returns:
        VNCProxyService singleton instance
    """
    global _vnc_proxy_service

    if _vnc_proxy_service is None:
        if docker_service is None:
            from cyroid.services.docker_service import get_docker_service
            docker_service = get_docker_service()
        _vnc_proxy_service = VNCProxyService(docker_service=docker_service)

    return _vnc_proxy_service
