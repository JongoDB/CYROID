# backend/cyroid/services/traefik_route_service.py
"""
Traefik Route Service

Manages dynamic Traefik routes for VNC console access in DinD deployments.
Generates YAML route files that Traefik watches via file provider.
"""
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

logger = logging.getLogger(__name__)


class TraefikRouteService:
    """Manages dynamic Traefik routes for DinD VNC access."""

    def __init__(self, routes_dir: Optional[str] = None):
        """
        Initialize the Traefik route service.

        Args:
            routes_dir: Directory where Traefik route files are written.
                       Defaults to /etc/traefik/vnc-routes or uses TRAEFIK_VNC_ROUTES_DIR env var.
        """
        self.routes_dir = Path(
            routes_dir or
            os.environ.get("TRAEFIK_VNC_ROUTES_DIR", "/etc/traefik/vnc-routes")
        )

    def _ensure_routes_dir(self) -> bool:
        """Ensure the routes directory exists. Returns True if successful."""
        try:
            self.routes_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.warning(f"Cannot create Traefik routes dir {self.routes_dir}: {e}")
            return False

    def generate_vnc_routes(
        self,
        range_id: str,
        port_mappings: Dict[str, Dict[str, Any]],
    ) -> Optional[str]:
        """
        Generate Traefik route file for VNC access to DinD VMs.

        Args:
            range_id: Range identifier
            port_mappings: Dict mapping vm_id to {proxy_host, proxy_port, original_port}

        Returns:
            Path to the generated route file, or None if failed
        """
        if not self._ensure_routes_dir():
            logger.error("Cannot write VNC routes - directory not accessible")
            return None

        if not port_mappings:
            logger.debug(f"No VNC port mappings for range {range_id}, skipping route generation")
            return None

        # Build Traefik dynamic config for VNC routes
        routers = {}
        services = {}
        middlewares = {}

        for vm_id, proxy_info in port_mappings.items():
            proxy_host = proxy_info.get("proxy_host")
            proxy_port = proxy_info.get("proxy_port")
            original_port = proxy_info.get("original_port")

            if not proxy_host or not proxy_port:
                logger.warning(f"Invalid proxy info for VM {vm_id}: {proxy_info}")
                continue

            # Create short ID for Traefik names (first 12 chars of UUID)
            vm_id_short = vm_id[:12].replace("-", "")
            router_name = f"vnc-dind-{vm_id_short}"

            # Determine if backend requires SSL (KasmVNC on port 6901 uses SSL)
            # linuxserver/webtop on port 3000 uses HTTP
            # dockur/windows on port 8006 uses HTTP
            requires_ssl = original_port == 6901

            # Service pointing to DinD proxy port
            if requires_ssl:
                services[router_name] = {
                    "loadBalancer": {
                        "serversTransport": "insecure-transport",
                        "servers": [
                            {"url": f"https://{proxy_host}:{proxy_port}"}
                        ]
                    }
                }
            else:
                services[router_name] = {
                    "loadBalancer": {
                        "servers": [
                            {"url": f"http://{proxy_host}:{proxy_port}"}
                        ]
                    }
                }

            # Middleware to strip /vnc/{vm_id} prefix
            middleware_name = f"vnc-strip-{vm_id_short}"
            middlewares[middleware_name] = {
                "stripPrefix": {
                    "prefixes": [f"/vnc/{vm_id}"]
                }
            }

            # HTTP router (priority=100 to take precedence over frontend catch-all)
            routers[router_name] = {
                "rule": f"PathPrefix(`/vnc/{vm_id}`)",
                "entryPoints": ["web"],
                "service": router_name,
                "priority": 100,
                "middlewares": [middleware_name],
            }

            # HTTPS router
            routers[f"{router_name}-secure"] = {
                "rule": f"PathPrefix(`/vnc/{vm_id}`)",
                "entryPoints": ["websecure"],
                "service": router_name,
                "priority": 100,
                "middlewares": [middleware_name],
                "tls": {},
            }

        if not routers:
            logger.debug(f"No valid VNC routes generated for range {range_id}")
            return None

        # Build the config structure
        config = {
            "http": {
                "routers": routers,
                "services": services,
                "middlewares": middlewares,
            }
        }

        # Write to file
        route_file = self.routes_dir / f"range-{range_id[:8]}.yml"
        try:
            with open(route_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Generated VNC routes for range {range_id}: {route_file}")
            return str(route_file)

        except Exception as e:
            logger.error(f"Failed to write VNC routes for range {range_id}: {e}")
            return None

    def remove_vnc_routes(self, range_id: str) -> bool:
        """
        Remove Traefik route file for a range.

        Args:
            range_id: Range identifier

        Returns:
            True if file was removed or didn't exist, False on error
        """
        route_file = self.routes_dir / f"range-{range_id[:8]}.yml"

        try:
            if route_file.exists():
                route_file.unlink()
                logger.info(f"Removed VNC routes for range {range_id}: {route_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove VNC routes for range {range_id}: {e}")
            return False


# Singleton instance
_traefik_route_service: Optional[TraefikRouteService] = None


def get_traefik_route_service() -> TraefikRouteService:
    """Get the singleton TraefikRouteService instance."""
    global _traefik_route_service
    if _traefik_route_service is None:
        _traefik_route_service = TraefikRouteService()
    return _traefik_route_service
