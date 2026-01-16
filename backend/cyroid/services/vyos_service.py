# cyroid/services/vyos_service.py
"""
VyOS router service for managing per-range network routing and isolation.

Each range gets a dedicated VyOS container that:
- Connects to the management network (eth0) for CYROID control
- Has LAN interfaces (eth1, eth2, ...) for each network in the range
- Handles NAT for internet-enabled networks
- Enforces isolation via firewall rules
"""
import docker
from docker.errors import APIError, NotFound, ImageNotFound
from typing import Optional, Dict, List, Any
import logging
import time
import ipaddress

from cyroid.config import get_settings

logger = logging.getLogger(__name__)


class VyOSService:
    """Service for managing VyOS router containers."""

    def __init__(self):
        self.client = docker.from_env()
        self.settings = get_settings()
        self._verify_connection()

    def _verify_connection(self) -> None:
        """Verify connection to Docker daemon."""
        try:
            self.client.ping()
            logger.info("VyOS Service: Connected to Docker daemon")
        except Exception as e:
            logger.error(f"VyOS Service: Failed to connect to Docker daemon: {e}")
            raise RuntimeError("Cannot connect to Docker daemon")

    def ensure_vyos_image(self) -> bool:
        """
        Ensure the VyOS image is available locally.

        Returns:
            True if image is available
        """
        image = self.settings.vyos_image
        try:
            self.client.images.get(image)
            logger.debug(f"VyOS image already present: {image}")
            return True
        except ImageNotFound:
            logger.info(f"Pulling VyOS image: {image}")
            try:
                self.client.images.pull(image)
                logger.info(f"Successfully pulled VyOS image: {image}")
                return True
            except Exception as e:
                logger.error(f"Failed to pull VyOS image: {e}")
                return False

    def get_or_create_management_network(self) -> str:
        """
        Get or create the management network for CYROID infrastructure.

        Returns:
            Network ID of the management network
        """
        network_name = self.settings.management_network_name
        subnet = self.settings.management_network_subnet
        gateway = self.settings.management_network_gateway

        # Check if network already exists
        try:
            networks = self.client.networks.list(names=[network_name])
            for network in networks:
                if network.name == network_name:
                    logger.debug(f"Management network already exists: {network.id}")
                    return network.id
        except Exception as e:
            logger.warning(f"Error checking for management network: {e}")

        # Create the management network
        try:
            ipam_pool = docker.types.IPAMPool(
                subnet=subnet,
                gateway=gateway
            )
            ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])

            network = self.client.networks.create(
                name=network_name,
                driver="bridge",
                internal=False,  # Needs external access for internet routing
                ipam=ipam_config,
                labels={
                    "cyroid.type": "management",
                    "cyroid.managed": "true"
                },
                attachable=True
            )
            logger.info(f"Created management network: {network_name} ({network.id[:12]})")
            return network.id
        except APIError as e:
            logger.error(f"Failed to create management network: {e}")
            raise

    def allocate_management_ip(self) -> str:
        """
        Allocate a unique IP from the management network.

        Returns:
            IP address string (e.g., "10.10.0.2")
        """
        # Get existing containers on the management network
        network_name = self.settings.management_network_name
        used_ips = set()

        try:
            network = self.client.networks.get(network_name)
            containers = network.attrs.get("Containers", {})
            for container_id, config in containers.items():
                ip = config.get("IPv4Address", "").split("/")[0]
                if ip:
                    used_ips.add(ip)
        except NotFound:
            pass

        # Allocate next available IP (starting from .2, .1 is gateway)
        subnet = ipaddress.ip_network(self.settings.management_network_subnet, strict=False)
        for host in subnet.hosts():
            ip_str = str(host)
            # Skip gateway and already used IPs
            if ip_str == self.settings.management_network_gateway:
                continue
            if ip_str in used_ips:
                continue
            return ip_str

        raise RuntimeError("No available IPs in management network")

    def create_router_container(
        self,
        range_id: str,
        management_ip: str
    ) -> str:
        """
        Create a VyOS router container for a range.

        Args:
            range_id: UUID of the range
            management_ip: IP address on the management network

        Returns:
            Container ID
        """
        # Ensure image is available
        if not self.ensure_vyos_image():
            raise RuntimeError("VyOS image not available")

        # Ensure management network exists
        mgmt_network_id = self.get_or_create_management_network()
        mgmt_network = self.client.networks.get(mgmt_network_id)

        container_name = f"cyroid-router-{range_id[:8]}"

        # Create networking config for management network
        networking_config = self.client.api.create_networking_config({
            mgmt_network.name: self.client.api.create_endpoint_config(
                ipv4_address=management_ip
            )
        })

        # VyOS environment configuration
        environment = {
            "VYOS_RANGE_ID": range_id,
        }

        try:
            container = self.client.api.create_container(
                image=self.settings.vyos_image,
                name=container_name,
                hostname=f"vyos-{range_id[:8]}",
                command="/sbin/init",
                detach=True,
                tty=True,
                stdin_open=True,
                networking_config=networking_config,
                host_config=self.client.api.create_host_config(
                    privileged=True,
                    cap_add=["NET_ADMIN", "SYS_ADMIN"],
                    sysctls={
                        "net.ipv4.ip_forward": "1",
                        "net.ipv4.conf.all.forwarding": "1",
                    },
                    restart_policy={"Name": "unless-stopped"}
                ),
                environment=environment,
                labels={
                    "cyroid.type": "router",
                    "cyroid.range_id": range_id,
                    "cyroid.managed": "true"
                }
            )
            container_id = container["Id"]
            logger.info(f"Created VyOS router container: {container_name} ({container_id[:12]})")
            return container_id
        except APIError as e:
            logger.error(f"Failed to create VyOS router: {e}")
            raise

    def start_router(self, container_id: str) -> bool:
        """Start the VyOS router container."""
        try:
            self.client.api.start(container_id)
            logger.info(f"Started VyOS router: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"VyOS router not found: {container_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to start VyOS router: {e}")
            raise

    def stop_router(self, container_id: str, timeout: int = 10) -> bool:
        """Stop the VyOS router container."""
        try:
            self.client.api.stop(container_id, timeout=timeout)
            logger.info(f"Stopped VyOS router: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"VyOS router not found: {container_id}")
            return False
        except APIError as e:
            logger.error(f"Failed to stop VyOS router: {e}")
            raise

    def remove_router(self, container_id: str, force: bool = True) -> bool:
        """Remove the VyOS router container."""
        try:
            self.client.api.remove_container(container_id, force=force)
            logger.info(f"Removed VyOS router: {container_id[:12]}")
            return True
        except NotFound:
            logger.warning(f"VyOS router not found: {container_id}")
            return True  # Already gone
        except APIError as e:
            logger.error(f"Failed to remove VyOS router: {e}")
            raise

    def connect_to_network(
        self,
        container_id: str,
        network_id: str,
        interface_ip: str
    ) -> bool:
        """
        Connect the VyOS router to a range network.

        Args:
            container_id: VyOS container ID
            network_id: Docker network ID to connect to
            interface_ip: IP address for the router on this network (usually .1)

        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(network_id)

            # First, disconnect any existing/partial connection to avoid conflicts
            try:
                network.disconnect(container_id, force=True)
                logger.debug(f"Cleared existing connection to {network.name}")
            except (NotFound, APIError):
                pass  # Not connected, which is fine

            # Now connect with the desired IP
            network.connect(container_id, ipv4_address=interface_ip)
            logger.info(f"Connected VyOS router to network {network.name} with IP {interface_ip}")
            return True
        except NotFound as e:
            logger.error(f"Network or container not found: {e}")
            return False
        except APIError as e:
            logger.error(f"Failed to connect VyOS to network: {e}")
            raise

    def disconnect_from_network(
        self,
        container_id: str,
        network_id: str
    ) -> bool:
        """
        Disconnect the VyOS router from a network.

        Args:
            container_id: VyOS container ID
            network_id: Docker network ID

        Returns:
            True if successful
        """
        try:
            network = self.client.networks.get(network_id)
            network.disconnect(container_id)
            logger.info(f"Disconnected VyOS router from network {network.name}")
            return True
        except NotFound:
            return True  # Already disconnected
        except APIError as e:
            logger.warning(f"Failed to disconnect VyOS from network: {e}")
            return False

    def exec_vyos_command(
        self,
        container_id: str,
        command: str,
        timeout: int = 30
    ) -> tuple[int, str]:
        """
        Execute a VyOS CLI command in the router container.

        Args:
            container_id: VyOS container ID
            command: VyOS command to execute
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, output)
        """
        try:
            container = self.client.containers.get(container_id)

            # VyOS commands need to be run through vbash
            full_command = f"/bin/vbash -c 'source /opt/vyatta/etc/functions/script-template; {command}'"

            exec_result = container.exec_run(
                full_command,
                user="root",
                demux=True
            )
            stdout = exec_result.output[0] or b""
            stderr = exec_result.output[1] or b""
            output = (stdout + stderr).decode("utf-8", errors="replace")
            return exec_result.exit_code, output
        except NotFound:
            raise ValueError(f"VyOS container not found: {container_id}")
        except APIError as e:
            logger.error(f"Failed to exec VyOS command: {e}")
            raise

    def configure_interface(
        self,
        container_id: str,
        interface: str,
        ip_address: str,
        description: str = ""
    ) -> bool:
        """
        Configure a network interface on the VyOS router.

        Args:
            container_id: VyOS container ID
            interface: Interface name (eth0, eth1, etc.)
            ip_address: IP address with CIDR (e.g., "10.0.1.1/24")
            description: Interface description

        Returns:
            True if successful
        """
        commands = [
            f"set interfaces ethernet {interface} address '{ip_address}'",
        ]
        if description:
            commands.append(f"set interfaces ethernet {interface} description '{description}'")
        commands.append("commit")
        commands.append("save")

        full_command = " && ".join(commands)
        exit_code, output = self.exec_vyos_command(container_id, full_command)

        if exit_code != 0:
            logger.error(f"Failed to configure interface {interface}: {output}")
            return False

        logger.info(f"Configured VyOS interface {interface} with {ip_address}")
        return True

    def configure_nat_outbound(
        self,
        container_id: str,
        rule_number: int,
        source_network: str,
        outbound_interface: str = "eth0"
    ) -> bool:
        """
        Configure outbound NAT (masquerade) for a network.

        Args:
            container_id: VyOS container ID
            rule_number: NAT rule number (10, 20, etc.)
            source_network: Source network CIDR (e.g., "10.0.1.0/24")
            outbound_interface: Interface for outbound traffic (usually eth0)

        Returns:
            True if successful
        """
        commands = [
            f"set nat source rule {rule_number} outbound-interface name '{outbound_interface}'",
            f"set nat source rule {rule_number} source address '{source_network}'",
            f"set nat source rule {rule_number} translation address 'masquerade'",
            "commit",
            "save"
        ]

        full_command = " && ".join(commands)
        exit_code, output = self.exec_vyos_command(container_id, full_command)

        if exit_code != 0:
            logger.error(f"Failed to configure NAT for {source_network}: {output}")
            return False

        logger.info(f"Configured NAT masquerade for {source_network}")
        return True

    def remove_nat_rule(
        self,
        container_id: str,
        rule_number: int
    ) -> bool:
        """
        Remove a NAT rule.

        Args:
            container_id: VyOS container ID
            rule_number: NAT rule number to remove

        Returns:
            True if successful
        """
        commands = [
            f"delete nat source rule {rule_number}",
            "commit",
            "save"
        ]

        full_command = " && ".join(commands)
        exit_code, output = self.exec_vyos_command(container_id, full_command)

        if exit_code != 0:
            logger.warning(f"Failed to remove NAT rule {rule_number}: {output}")
            return False

        logger.info(f"Removed NAT rule {rule_number}")
        return True

    def configure_firewall_isolated(
        self,
        container_id: str,
        interface: str,
        allow_established: bool = True
    ) -> bool:
        """
        Configure firewall to isolate a network (block outbound except established).

        Args:
            container_id: VyOS container ID
            interface: Interface to apply firewall (eth1, eth2, etc.)
            allow_established: Allow established/related connections

        Returns:
            True if successful
        """
        fw_name = f"ISOLATED-{interface.upper()}"
        commands = [
            f"set firewall ipv4 name {fw_name} default-action 'drop'",
        ]

        if allow_established:
            commands.extend([
                f"set firewall ipv4 name {fw_name} rule 10 action 'accept'",
                f"set firewall ipv4 name {fw_name} rule 10 state established 'enable'",
                f"set firewall ipv4 name {fw_name} rule 10 state related 'enable'",
            ])

        # Allow intra-network traffic
        commands.extend([
            f"set firewall ipv4 name {fw_name} rule 20 action 'accept'",
            f"set firewall ipv4 name {fw_name} rule 20 destination group network-group 'SAME-NET'",
        ])

        # Apply to interface
        commands.extend([
            f"set firewall interface {interface} out ipv4 name '{fw_name}'",
            "commit",
            "save"
        ])

        full_command = " && ".join(commands)
        exit_code, output = self.exec_vyos_command(container_id, full_command)

        if exit_code != 0:
            logger.error(f"Failed to configure isolation firewall for {interface}: {output}")
            return False

        logger.info(f"Configured isolation firewall for {interface}")
        return True

    def remove_firewall_rules(
        self,
        container_id: str,
        interface: str
    ) -> bool:
        """
        Remove firewall rules for an interface.

        Args:
            container_id: VyOS container ID
            interface: Interface to remove firewall from

        Returns:
            True if successful
        """
        fw_name = f"ISOLATED-{interface.upper()}"
        commands = [
            f"delete firewall interface {interface} out",
            f"delete firewall ipv4 name {fw_name}",
            "commit",
            "save"
        ]

        full_command = " && ".join(commands)
        exit_code, output = self.exec_vyos_command(container_id, full_command)

        # Ignore errors - rules may not exist
        if exit_code == 0:
            logger.info(f"Removed firewall rules for {interface}")
        return True

    def get_router_status(self, container_id: str) -> Optional[str]:
        """Get the status of a VyOS router container."""
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except NotFound:
            return None

    def wait_for_router_ready(
        self,
        container_id: str,
        timeout: int = 60,
        check_interval: int = 5
    ) -> bool:
        """
        Wait for the VyOS router to be ready to accept commands.

        Args:
            container_id: VyOS container ID
            timeout: Maximum wait time in seconds
            check_interval: Time between checks in seconds

        Returns:
            True if router is ready
        """
        elapsed = 0
        while elapsed < timeout:
            status = self.get_router_status(container_id)
            if status == "running":
                # Try a simple command to verify VyOS is operational
                try:
                    exit_code, _ = self.exec_vyos_command(container_id, "show version")
                    if exit_code == 0:
                        logger.info(f"VyOS router {container_id[:12]} is ready")
                        return True
                except Exception:
                    pass  # VyOS not ready yet

            time.sleep(check_interval)
            elapsed += check_interval

        logger.warning(f"VyOS router {container_id[:12]} not ready after {timeout}s")
        return False

    # Internet Access Methods (via management interface eth0 and Docker bridge NAT)

    def configure_internet_nat(
        self,
        container_id: str,
        source_network: str,
        outbound_interface: str = "eth0"
    ) -> bool:
        """
        Configure NAT masquerade for internet access via the management interface.

        Traffic flow: VM → VyOS NAT (eth0) → Docker bridge NAT → Internet.

        This uses Docker's native NAT on the management bridge for internet connectivity,
        which is simpler and more reliable than macvlan configurations.

        Args:
            container_id: VyOS container ID
            source_network: Source network CIDR to NAT (e.g., "10.100.1.0/24")
            outbound_interface: Outbound interface for NAT (default eth0 = management)

        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(container_id)

            # Enable IP forwarding
            container.exec_run("bash -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'", user="root")

            # Disable rp_filter on all interfaces (needed for proper forwarding)
            container.exec_run("bash -c 'for i in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $i; done'", user="root")

            # Check if rule already exists
            check_cmd = f"iptables -t nat -C POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE 2>/dev/null"
            result = container.exec_run(f"bash -c '{check_cmd}'", user="root")
            if result.exit_code == 0:
                logger.debug(f"Internet NAT rule for {source_network} already exists")
                return True

            # Add MASQUERADE rule for internet access
            add_cmd = f"iptables -t nat -A POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE"
            result = container.exec_run(f"bash -c '{add_cmd}'", user="root")
            if result.exit_code != 0:
                logger.error(f"Failed to add internet NAT rule: {result.output}")
                return False

            # Ensure ACCEPT rules in raw table to bypass VyOS's NOTRACK rules
            # Without these, conntrack is disabled and NAT return traffic fails
            # Rule 1: Allow conntrack for traffic FROM the source network
            accept_src_cmd = f"iptables -t raw -I PREROUTING 1 -s {source_network} -j ACCEPT 2>/dev/null || true"
            container.exec_run(f"bash -c '{accept_src_cmd}'", user="root")

            # Rule 2: Allow conntrack for return traffic TO the VyOS NAT IP
            # This is critical - without it, SYN-ACK responses are not tracked and get RST
            accept_dst_cmd = f"iptables -t raw -I PREROUTING 1 -d 10.10.0.0/16 -j ACCEPT 2>/dev/null || true"
            container.exec_run(f"bash -c '{accept_dst_cmd}'", user="root")

            # Rule 3: Allow conntrack for outbound NAT'd traffic
            accept_out_cmd = f"iptables -t raw -I OUTPUT 1 -s 10.10.0.0/16 -j ACCEPT 2>/dev/null || true"
            container.exec_run(f"bash -c '{accept_out_cmd}'", user="root")

            logger.info(f"Configured internet NAT for {source_network} via {outbound_interface}")
            return True

        except Exception as e:
            logger.error(f"Failed to configure internet NAT: {e}")
            return False

    def remove_internet_nat(
        self,
        container_id: str,
        source_network: str,
        outbound_interface: str = "eth0"
    ) -> bool:
        """
        Remove NAT masquerade rule for internet access.

        Args:
            container_id: VyOS container ID
            source_network: Source network CIDR
            outbound_interface: Outbound interface (default eth0)

        Returns:
            True if successful
        """
        try:
            container = self.client.containers.get(container_id)

            # Remove MASQUERADE rule
            del_cmd = f"iptables -t nat -D POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE 2>/dev/null || true"
            container.exec_run(f"bash -c '{del_cmd}'", user="root")

            logger.info(f"Removed internet NAT rule for {source_network}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove internet NAT: {e}")
            return False


# Singleton instance
_vyos_service: Optional[VyOSService] = None


def get_vyos_service() -> VyOSService:
    """Get the VyOS service singleton."""
    global _vyos_service
    if _vyos_service is None:
        _vyos_service = VyOSService()
    return _vyos_service
