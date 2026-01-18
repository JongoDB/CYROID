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
            IP address string (e.g., "10.0.0.2")
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
            command: VyOS command to execute (operational mode)
            timeout: Command timeout in seconds

        Returns:
            Tuple of (exit_code, output)
        """
        try:
            container = self.client.containers.get(container_id)

            # For official VyOS image, use the vyatta wrapper
            # Operational commands go through vbash with script-template
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

    def exec_shell_command(
        self,
        container_id: str,
        command: str
    ) -> tuple[int, str]:
        """
        Execute a shell command in the router container.

        Args:
            container_id: Router container ID
            command: Shell command to execute

        Returns:
            Tuple of (exit_code, output)
        """
        try:
            container = self.client.containers.get(container_id)

            exec_result = container.exec_run(
                f"/bin/bash -c '{command}'",
                user="root",
                demux=True
            )
            stdout = exec_result.output[0] or b""
            stderr = exec_result.output[1] or b""
            output = (stdout + stderr).decode("utf-8", errors="replace")
            return exec_result.exit_code, output
        except NotFound:
            raise ValueError(f"Router container not found: {container_id}")
        except APIError as e:
            logger.error(f"Failed to exec shell command: {e}")
            raise

    def configure_interface(
        self,
        container_id: str,
        interface: str,
        ip_address: str,
        description: str = ""
    ) -> bool:
        """
        Configure a network interface on the router using standard Linux ip commands.

        Args:
            container_id: Router container ID
            interface: Interface name (eth0, eth1, etc.)
            ip_address: IP address with CIDR (e.g., "10.0.1.1/24")
            description: Interface description (logged but not applied)

        Returns:
            True if successful
        """
        # Use standard ip commands to configure the interface
        command = f"ip addr add {ip_address} dev {interface} 2>/dev/null || true; ip link set {interface} up"
        exit_code, output = self.exec_shell_command(container_id, command)

        if exit_code != 0:
            logger.error(f"Failed to configure interface {interface}: {output}")
            return False

        logger.info(f"Configured router interface {interface} with {ip_address}")
        return True

    def configure_nat_outbound(
        self,
        container_id: str,
        rule_number: int,
        source_network: str,
        outbound_interface: str = "eth0"
    ) -> bool:
        """
        Configure outbound NAT (masquerade) for a network using iptables.

        Args:
            container_id: Router container ID
            rule_number: NAT rule number (unused, kept for API compatibility)
            source_network: Source network CIDR (e.g., "10.0.1.0/24")
            outbound_interface: Interface for outbound traffic (usually eth0)

        Returns:
            True if successful
        """
        # Use iptables for NAT masquerade
        command = f"iptables -t nat -C POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE"
        exit_code, output = self.exec_shell_command(container_id, command)

        if exit_code != 0:
            logger.error(f"Failed to configure NAT for {source_network}: {output}")
            return False

        logger.info(f"Configured NAT masquerade for {source_network}")
        return True

    def remove_nat_rule(
        self,
        container_id: str,
        rule_number: int,
        source_network: Optional[str] = None,
        outbound_interface: str = "eth0"
    ) -> bool:
        """
        Remove a NAT rule using iptables.

        Args:
            container_id: Router container ID
            rule_number: NAT rule number (unused, kept for API compatibility)
            source_network: Source network CIDR to remove NAT for
            outbound_interface: Outbound interface

        Returns:
            True if successful
        """
        if source_network:
            command = f"iptables -t nat -D POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE 2>/dev/null || true"
            exit_code, output = self.exec_shell_command(container_id, command)
            logger.info(f"Removed NAT rule for {source_network}")
        else:
            logger.warning("No source_network provided for NAT rule removal")
        return True

    def configure_firewall_isolated(
        self,
        container_id: str,
        interface: str,
        allow_established: bool = True
    ) -> bool:
        """
        Configure firewall to isolate a network (block outbound except established) using iptables.

        Args:
            container_id: Router container ID
            interface: Interface to apply firewall (eth1, eth2, etc.)
            allow_established: Allow established/related connections

        Returns:
            True if successful
        """
        commands = []

        # Create a chain for this interface if it doesn't exist
        chain_name = f"ISOLATED_{interface.upper()}"
        commands.append(f"iptables -N {chain_name} 2>/dev/null || true")

        # Flush existing rules in the chain
        commands.append(f"iptables -F {chain_name}")

        if allow_established:
            # Allow established/related connections
            commands.append(f"iptables -A {chain_name} -m state --state ESTABLISHED,RELATED -j ACCEPT")

        # Drop everything else
        commands.append(f"iptables -A {chain_name} -j DROP")

        # Apply chain to interface (FORWARD chain for outbound)
        commands.append(f"iptables -C FORWARD -i {interface} -j {chain_name} 2>/dev/null || iptables -I FORWARD -i {interface} -j {chain_name}")

        command = " && ".join(commands)
        exit_code, output = self.exec_shell_command(container_id, command)

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
        Remove firewall rules for an interface using iptables.

        Args:
            container_id: Router container ID
            interface: Interface to remove firewall from

        Returns:
            True if successful
        """
        chain_name = f"ISOLATED_{interface.upper()}"
        commands = [
            # Remove from FORWARD chain
            f"iptables -D FORWARD -i {interface} -j {chain_name} 2>/dev/null || true",
            # Flush and delete the chain
            f"iptables -F {chain_name} 2>/dev/null || true",
            f"iptables -X {chain_name} 2>/dev/null || true",
        ]

        command = " && ".join(commands)
        exit_code, output = self.exec_shell_command(container_id, command)

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

    # Internet Access Methods (via iptables NAT)

    def configure_internet_nat(
        self,
        container_id: str,
        source_network: str,
        outbound_interface: str = "eth0"
    ) -> bool:
        """
        Configure NAT masquerade for internet access using iptables.

        Traffic flow: VM → Router NAT (eth0) → Docker bridge NAT → Internet.

        Args:
            container_id: Router container ID
            source_network: Source network CIDR to NAT (e.g., "10.100.1.0/24")
            outbound_interface: Outbound interface for NAT (default eth0 = management)

        Returns:
            True if successful
        """
        try:
            # Use iptables for NAT masquerade
            # Check if rule exists first, add if not
            command = f"iptables -t nat -C POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE"
            exit_code, output = self.exec_shell_command(container_id, command)

            if exit_code != 0:
                logger.error(f"Failed to configure internet NAT for {source_network}: {output}")
                return False

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
        Remove NAT masquerade rule for internet access using iptables.

        Args:
            container_id: Router container ID
            source_network: Source network CIDR
            outbound_interface: Outbound interface (default eth0)

        Returns:
            True if successful
        """
        try:
            # Remove the iptables NAT rule
            command = f"iptables -t nat -D POSTROUTING -s {source_network} -o {outbound_interface} -j MASQUERADE 2>/dev/null || true"
            exit_code, output = self.exec_shell_command(container_id, command)

            logger.info(f"Removed internet NAT rule for {source_network}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove internet NAT: {e}")
            return False

    # DHCP Server Methods (using ISC dhcpd)

    def configure_dhcp_server(
        self,
        container_id: str,
        network_name: str,
        subnet: str,
        gateway: str,
        dns_servers: Optional[str] = None,
        dns_search: Optional[str] = None,
        range_start: Optional[str] = None,
        range_end: Optional[str] = None,
        lease_time: int = 86400,
        interface: Optional[str] = None
    ) -> bool:
        """
        Configure DHCP server for a network using ISC dhcpd.

        Args:
            container_id: Router container ID
            network_name: Network name (used for config file naming)
            subnet: Network subnet in CIDR (e.g., "10.0.1.0/24")
            gateway: Default gateway IP (usually the router interface IP)
            dns_servers: Comma-separated DNS servers (e.g., "8.8.8.8,8.8.4.4")
            dns_search: DNS search domain (e.g., "corp.local")
            range_start: Start of DHCP range (defaults to .10)
            range_end: End of DHCP range (defaults to .250)
            lease_time: DHCP lease time in seconds (default 86400 = 24 hours)
            interface: Interface to listen on (auto-detected if not specified)

        Returns:
            True if successful
        """
        try:
            # Parse subnet to calculate DHCP range
            subnet_obj = ipaddress.ip_network(subnet, strict=False)
            hosts = list(subnet_obj.hosts())
            netmask = str(subnet_obj.netmask)
            network_addr = str(subnet_obj.network_address)

            # Default DHCP range: .10 to .250 (avoiding gateway and reserved IPs)
            if not range_start:
                range_start = str(hosts[9]) if len(hosts) > 10 else str(hosts[1])
            if not range_end:
                range_end = str(hosts[min(249, len(hosts) - 2)]) if len(hosts) > 250 else str(hosts[-2])

            # Sanitize network name for config file
            safe_name = network_name.replace("-", "_").replace(" ", "_").lower()[:32]

            # Build DNS servers string
            if dns_servers:
                dns_list = [s.strip() for s in dns_servers.split(",") if s.strip()]
                dns_str = ", ".join(dns_list)
            else:
                dns_str = "8.8.8.8, 8.8.4.4"

            # Build ISC dhcpd configuration
            config_lines = [
                f"# DHCP config for {network_name}",
                f"subnet {network_addr} netmask {netmask} {{",
                f"    range {range_start} {range_end};",
                f"    option routers {gateway};",
                f"    option domain-name-servers {dns_str};",
                f"    default-lease-time {lease_time};",
                f"    max-lease-time {lease_time * 2};",
            ]

            # Add DNS search domain if specified
            if dns_search:
                config_lines.append(f'    option domain-name "{dns_search}";')

            config_lines.append("}")

            # Determine interface for dhcpd
            listen_interface = interface or ""

            # Setup directories
            self.exec_shell_command(container_id, "mkdir -p /var/lib/dhcp /etc/dhcp && touch /var/lib/dhcp/dhcpd.leases")

            # Write config file using base64 to avoid shell escaping issues
            config_file = f"/etc/dhcp/dhcpd-{safe_name}.conf"
            config_content = "\n".join(config_lines)

            import base64
            config_b64 = base64.b64encode(config_content.encode()).decode()

            write_cmd = f"echo '{config_b64}' | base64 -d > {config_file}"
            exit_code, output = self.exec_shell_command(container_id, write_cmd)
            if exit_code != 0:
                logger.error(f"Failed to write DHCP config: {output}")
                return False

            # Kill existing dhcpd and restart
            self.exec_shell_command(container_id, "killall dhcpd 2>/dev/null || true")
            time.sleep(1)

            # Build combined config from all dhcpd config files
            self.exec_shell_command(container_id, "cat /etc/dhcp/dhcpd-*.conf 2>/dev/null > /etc/dhcp/dhcpd.conf.combined")

            # Start dhcpd with combined config using nohup to avoid zombie processes
            # Use -f flag for foreground mode combined with nohup for proper daemonization
            if listen_interface:
                start_cmd = f"rm -f /var/run/dhcpd.pid; nohup dhcpd -f -cf /etc/dhcp/dhcpd.conf.combined -lf /var/lib/dhcp/dhcpd.leases {listen_interface} > /var/log/dhcpd.log 2>&1 &"
            else:
                start_cmd = "rm -f /var/run/dhcpd.pid; nohup dhcpd -f -cf /etc/dhcp/dhcpd.conf.combined -lf /var/lib/dhcp/dhcpd.leases > /var/log/dhcpd.log 2>&1 &"

            exit_code, output = self.exec_shell_command(container_id, start_cmd)

            # Verify dhcpd is running
            time.sleep(2)
            check_code, check_output = self.exec_shell_command(container_id, "pgrep -x dhcpd")

            if check_code != 0:
                logger.error(f"dhcpd not running after configuration: {output}")
                return False

            logger.info(f"Configured DHCP server (dhcpd) for {network_name} ({subnet}), range {range_start}-{range_end}")
            return True

        except Exception as e:
            logger.error(f"Failed to configure DHCP server: {e}")
            return False

    def remove_dhcp_server(
        self,
        container_id: str,
        network_name: str,
        subnet: str
    ) -> bool:
        """
        Remove DHCP server configuration for a network.

        Args:
            container_id: Router container ID
            network_name: Network name
            subnet: Network subnet in CIDR

        Returns:
            True if successful
        """
        try:
            # Sanitize network name
            safe_name = network_name.replace("-", "_").replace(" ", "_").lower()[:32]

            # Remove config file and restart dhcpd
            # Kill existing dhcpd
            self.exec_shell_command(container_id, "pkill -x dhcpd 2>/dev/null || true")

            # Remove the config file
            self.exec_shell_command(container_id, f"rm -f /etc/dhcp/dhcpd-{safe_name}.conf")

            # Rebuild combined config and restart if any configs remain
            self.exec_shell_command(container_id, "cat /etc/dhcp/dhcpd-*.conf 2>/dev/null > /etc/dhcp/dhcpd.conf.combined || rm -f /etc/dhcp/dhcpd.conf.combined")

            # Check if we have any remaining DHCP configs
            check_code, _ = self.exec_shell_command(container_id, "test -s /etc/dhcp/dhcpd.conf.combined")
            if check_code == 0:
                # Start dhcpd with remaining configs
                self.exec_shell_command(
                    container_id,
                    "rm -f /var/run/dhcpd.pid; nohup dhcpd -f -cf /etc/dhcp/dhcpd.conf.combined -lf /var/lib/dhcp/dhcpd.leases > /var/log/dhcpd.log 2>&1 &"
                )

            logger.info(f"Removed DHCP server configuration for {network_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove DHCP server config: {e}")
            return False

    def toggle_dhcp_server(
        self,
        container_id: str,
        network_name: str,
        subnet: str,
        gateway: str,
        enable: bool,
        dns_servers: Optional[str] = None,
        dns_search: Optional[str] = None
    ) -> bool:
        """
        Enable or disable DHCP server for a network.

        Args:
            container_id: Router container ID
            network_name: Network name
            subnet: Network subnet
            gateway: Gateway IP
            enable: True to enable, False to disable
            dns_servers: DNS servers (for enable)
            dns_search: DNS search domain (for enable)

        Returns:
            True if successful
        """
        if enable:
            return self.configure_dhcp_server(
                container_id=container_id,
                network_name=network_name,
                subnet=subnet,
                gateway=gateway,
                dns_servers=dns_servers,
                dns_search=dns_search
            )
        else:
            return self.remove_dhcp_server(
                container_id=container_id,
                network_name=network_name,
                subnet=subnet
            )


# Singleton instance
_vyos_service: Optional[VyOSService] = None


def get_vyos_service() -> VyOSService:
    """Get the VyOS service singleton."""
    global _vyos_service
    if _vyos_service is None:
        _vyos_service = VyOSService()
    return _vyos_service
