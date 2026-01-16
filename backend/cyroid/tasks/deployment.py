# cyroid/tasks/deployment.py
"""Async deployment tasks using Dramatiq."""
import dramatiq
import logging
from uuid import UUID

from cyroid.database import get_session_local
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network
from cyroid.models.vm import VM, VMStatus
from cyroid.models.template import VMTemplate
from cyroid.models.router import RangeRouter, RouterStatus

logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=3, min_backoff=1000)
def deploy_range_task(range_id: str):
    """
    Async task to deploy a range.
    Creates VyOS router, Docker networks, and starts all VMs.
    """
    logger.info(f"Starting async deployment for range {range_id}")

    db = get_session_local()()
    try:
        from cyroid.services.docker_service import get_docker_service
        from cyroid.services.vyos_service import get_vyos_service
        docker = get_docker_service()
        vyos = get_vyos_service()

        range_obj = db.query(Range).filter(Range.id == UUID(range_id)).first()
        if not range_obj:
            logger.error(f"Range {range_id} not found")
            return

        # Set to deploying
        range_obj.status = RangeStatus.DEPLOYING
        db.commit()

        # Step 0: Create VyOS router for this range
        router = db.query(RangeRouter).filter(RangeRouter.range_id == UUID(range_id)).first()
        if not router:
            # Allocate management IP and create router record
            management_ip = vyos.allocate_management_ip()
            router = RangeRouter(
                range_id=UUID(range_id),
                management_ip=management_ip,
                status=RouterStatus.CREATING
            )
            db.add(router)
            db.commit()

        try:
            if not router.container_id:
                # Create and start the VyOS router
                container_id = vyos.create_router_container(range_id, router.management_ip)
                router.container_id = container_id
                db.commit()

                vyos.start_router(container_id)

                # Wait for router to be ready
                if vyos.wait_for_router_ready(container_id, timeout=120):
                    router.status = RouterStatus.RUNNING
                else:
                    router.status = RouterStatus.ERROR
                    router.error_message = "Router failed to become ready"
                db.commit()

                # Connect traefik to management network for routing
                docker.connect_traefik_to_management_network()

            logger.info(f"VyOS router ready for range {range_id}")
        except Exception as e:
            logger.error(f"Failed to create VyOS router for range {range_id}: {e}")
            router.status = RouterStatus.ERROR
            router.error_message = str(e)[:500]
            db.commit()
            # Continue anyway - VMs can still work without VyOS features

        # Step 1: Provision all networks
        networks = db.query(Network).filter(Network.range_id == UUID(range_id)).all()
        interface_num = 1  # eth0 is management, start from eth1

        for network in networks:
            if not network.docker_network_id:
                # Networks are NOT internal when using VyOS - VyOS handles isolation
                docker_network_id = docker.create_network(
                    name=f"cyroid-{network.name}-{str(network.id)[:8]}",
                    subnet=network.subnet,
                    gateway=network.gateway,
                    internal=False,  # VyOS handles isolation, not Docker
                    labels={
                        "cyroid.range_id": range_id,
                        "cyroid.network_id": str(network.id),
                    }
                )
                network.docker_network_id = docker_network_id
                db.commit()

                # Connect traefik to this network for VNC/web console routing
                docker.connect_traefik_to_network(docker_network_id)

                # Connect VyOS router to this network
                if router and router.container_id and router.status == RouterStatus.RUNNING:
                    interface_name = f"eth{interface_num}"
                    network.vyos_interface = interface_name

                    # Router gets the gateway IP on this network
                    vyos.connect_to_network(
                        router.container_id,
                        docker_network_id,
                        network.gateway
                    )

                    # Configure the interface on VyOS
                    subnet_bits = network.subnet.split('/')[1]
                    vyos.configure_interface(
                        router.container_id,
                        interface_name,
                        f"{network.gateway}/{subnet_bits}",
                        description=network.name
                    )

                    # Configure NAT if internet is enabled
                    if network.internet_enabled:
                        rule_num = interface_num * 10
                        vyos.configure_nat_outbound(
                            router.container_id,
                            rule_num,
                            network.subnet
                        )

                    # Configure firewall for isolation
                    if network.is_isolated and not network.internet_enabled:
                        vyos.configure_firewall_isolated(
                            router.container_id,
                            interface_name
                        )

                    # Configure DHCP server if enabled
                    if network.dhcp_enabled:
                        vyos.configure_dhcp_server(
                            container_id=router.container_id,
                            network_name=network.name,
                            subnet=network.subnet,
                            gateway=network.gateway,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search
                        )

                    interface_num += 1
                    db.commit()

                logger.info(f"Provisioned network {network.name} (isolated={network.is_isolated}, internet={network.internet_enabled}, dhcp={network.dhcp_enabled})")

        # Step 2: Create and start all VMs
        vms = db.query(VM).filter(VM.range_id == UUID(range_id)).all()
        for vm in vms:
            try:
                if vm.container_id:
                    docker.start_container(vm.container_id)
                else:
                    network = db.query(Network).filter(Network.id == vm.network_id).first()
                    template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()

                    if not network or not network.docker_network_id:
                        logger.warning(f"Skipping VM {vm.id}: network not provisioned")
                        continue

                    labels = {
                        "cyroid.range_id": range_id,
                        "cyroid.vm_id": str(vm.id),
                        "cyroid.hostname": vm.hostname,
                    }

                    if template.os_type == "windows":
                        container_id = docker.create_windows_container(
                            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                            network_id=network.docker_network_id,
                            ip_address=vm.ip_address,
                            cpu_limit=vm.cpu,
                            memory_limit_mb=vm.ram_mb,
                            disk_size_gb=vm.disk_gb,
                            labels=labels,
                            gateway=network.gateway,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search,
                        )
                    else:
                        container_id = docker.create_container(
                            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                            image=template.base_image,
                            network_id=network.docker_network_id,
                            ip_address=vm.ip_address,
                            cpu_limit=vm.cpu,
                            memory_limit_mb=vm.ram_mb,
                            hostname=vm.hostname,
                            labels=labels,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search,
                        )

                    vm.container_id = container_id
                    docker.start_container(container_id)

                    if template.config_script:
                        try:
                            docker.exec_command(container_id, template.config_script)
                        except Exception as e:
                            logger.warning(f"Config script failed for VM {vm.id}: {e}")

                vm.status = VMStatus.RUNNING
                db.commit()
                logger.info(f"Started VM {vm.hostname}")

            except Exception as e:
                logger.error(f"Failed to start VM {vm.id}: {e}")
                vm.status = VMStatus.ERROR
                db.commit()

        range_obj.status = RangeStatus.RUNNING
        db.commit()
        logger.info(f"Range {range_id} deployed successfully")

    except Exception as e:
        logger.error(f"Failed to deploy range {range_id}: {e}")
        range_obj = db.query(Range).filter(Range.id == UUID(range_id)).first()
        if range_obj:
            range_obj.status = RangeStatus.ERROR
            db.commit()
    finally:
        db.close()


@dramatiq.actor(max_retries=3, min_backoff=1000)
def teardown_range_task(range_id: str):
    """
    Async task to teardown a range.
    Stops and removes all VMs, VyOS router, then removes networks.
    """
    logger.info(f"Starting async teardown for range {range_id}")

    db = get_session_local()()
    try:
        from cyroid.services.docker_service import get_docker_service
        from cyroid.services.vyos_service import get_vyos_service
        docker = get_docker_service()
        vyos = get_vyos_service()

        # Step 1: Stop and remove all VM containers
        vms = db.query(VM).filter(VM.range_id == UUID(range_id)).all()
        for vm in vms:
            if vm.container_id:
                try:
                    docker.remove_container(vm.container_id, force=True)
                except Exception as e:
                    logger.warning(f"Failed to remove container for VM {vm.id}: {e}")
                vm.container_id = None
                vm.status = VMStatus.PENDING
                db.commit()
                logger.info(f"Removed VM {vm.hostname}")

        # Step 2: Remove VyOS router
        router = db.query(RangeRouter).filter(RangeRouter.range_id == UUID(range_id)).first()
        if router and router.container_id:
            try:
                vyos.remove_router(router.container_id)
            except Exception as e:
                logger.warning(f"Failed to remove VyOS router: {e}")
            router.container_id = None
            router.status = RouterStatus.PENDING
            db.commit()
            logger.info(f"Removed VyOS router for range {range_id}")

        # Step 3: Remove all Docker networks
        networks = db.query(Network).filter(Network.range_id == UUID(range_id)).all()
        for network in networks:
            if network.docker_network_id:
                try:
                    # Disconnect traefik before deleting network
                    docker.disconnect_traefik_from_network(network.docker_network_id)
                    docker.delete_network(network.docker_network_id)
                except Exception as e:
                    logger.warning(f"Failed to delete network {network.id}: {e}")
                network.docker_network_id = None
                network.vyos_interface = None
                db.commit()
                logger.info(f"Removed network {network.name}")

        range_obj = db.query(Range).filter(Range.id == UUID(range_id)).first()
        if range_obj:
            range_obj.status = RangeStatus.DRAFT
            db.commit()

        logger.info(f"Range {range_id} torn down successfully")

    except Exception as e:
        logger.error(f"Failed to teardown range {range_id}: {e}")
    finally:
        db.close()
