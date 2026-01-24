# cyroid/tasks/deployment.py
"""Async deployment tasks using Dramatiq."""
import asyncio
import base64
import dramatiq
import json
import logging
from uuid import UUID

import os

from cyroid.database import get_session_local
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network
from cyroid.models.vm import VM, VMStatus
from cyroid.models.template import VMType
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.snapshot import Snapshot
from cyroid.models.router import RangeRouter, RouterStatus
from cyroid.models.event_log import EventType
from cyroid.config import get_settings
from cyroid.services.event_service import EventService

logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=3, min_backoff=1000)
def deploy_range_task(range_id: str):
    """
    Async task to deploy a range using DinD isolation.
    Each range runs in its own Docker-in-Docker container.
    """
    logger.info(f"Starting DinD deployment for range {range_id}")

    db = get_session_local()()
    try:
        from cyroid.services.range_deployment_service import get_range_deployment_service
        deployment_service = get_range_deployment_service()

        range_obj = db.query(Range).filter(Range.id == UUID(range_id)).first()
        if not range_obj:
            logger.error(f"Range {range_id} not found")
            return

        # Count resources for event
        networks = db.query(Network).filter(Network.range_id == UUID(range_id)).all()
        vms = db.query(VM).filter(VM.range_id == UUID(range_id)).all()

        # Log deployment start event (needed for elapsed time calculation)
        event_service = EventService(db)
        event_service.log_event(
            range_id=UUID(range_id),
            event_type=EventType.DEPLOYMENT_STARTED,
            message=f"Starting DinD deployment of range '{range_obj.name}'",
            extra_data=json.dumps({
                "total_networks": len(networks),
                "total_vms": len(vms),
                "isolation": "dind"
            })
        )

        # Run async deployment synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                deployment_service.deploy_range(db, UUID(range_id))
            )
            logger.info(f"Range {range_id} deployed successfully: {result}")

            # Log deployment completion
            event_service.log_event(
                range_id=UUID(range_id),
                event_type=EventType.DEPLOYMENT_COMPLETED,
                message=f"Range '{range_obj.name}' deployed successfully with DinD isolation",
                extra_data=json.dumps({
                    "networks_deployed": len(networks),
                    "vms_deployed": len(vms),
                    "dind_container_id": range_obj.dind_container_id
                })
            )
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Failed to deploy range {range_id}: {e}")
        range_obj = db.query(Range).filter(Range.id == UUID(range_id)).first()
        if range_obj:
            range_obj.status = RangeStatus.ERROR
            range_obj.error_message = str(e)[:1000]
            db.commit()

            # Log deployment failure
            try:
                event_service = EventService(db)
                event_service.log_event(
                    range_id=UUID(range_id),
                    event_type=EventType.DEPLOYMENT_FAILED,
                    message=f"Deployment failed: {str(e)[:500]}",
                )
            except Exception:
                pass
    finally:
        db.close()


@dramatiq.actor(max_retries=3, min_backoff=1000)
def deploy_range_task_legacy(range_id: str):
    """
    Legacy deployment task (non-DinD).
    Creates VyOS router, Docker networks, and starts all VMs directly on host.

    DEPRECATED: Use deploy_range_task() which uses DinD isolation.
    """
    logger.info(f"Starting legacy deployment for range {range_id}")

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
                    # Load image sources (base_image, golden_image, or snapshot)
                    base_img = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first() if vm.base_image_id else None
                    golden_img = db.query(GoldenImage).filter(GoldenImage.id == vm.golden_image_id).first() if vm.golden_image_id else None
                    snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first() if vm.snapshot_id else None

                    if not network or not network.docker_network_id:
                        logger.warning(f"Skipping VM {vm.id}: network not provisioned")
                        continue

                    # Determine image properties from source
                    if base_img:
                        image_ref = base_img.docker_image_tag or ""
                        os_type = base_img.os_type
                        vm_type_str = base_img.vm_type
                    elif golden_img:
                        image_ref = golden_img.docker_image_tag or ""
                        os_type = golden_img.os_type
                        vm_type_str = golden_img.vm_type
                    elif snapshot:
                        image_ref = snapshot.docker_image_id or ""
                        os_type = snapshot.os_type or "linux"
                        vm_type_str = snapshot.vm_type or "container"
                    else:
                        logger.warning(f"Skipping VM {vm.id}: no image source found")
                        continue

                    labels = {
                        "cyroid.range_id": range_id,
                        "cyroid.vm_id": str(vm.id),
                        "cyroid.hostname": vm.hostname,
                    }

                    # Add Traefik labels for VNC web console routing
                    # This is needed for async deployments (blueprints, instances)
                    display_type = vm.display_type or "desktop"
                    if display_type == "desktop":
                        vm_id_short = str(vm.id).replace("-", "")[:16]
                        is_linuxserver = "linuxserver/" in image_ref or "lscr.io/linuxserver" in image_ref
                        is_kasmweb = "kasmweb/" in image_ref

                        # Determine VNC port and scheme based on image type
                        # QEMU-based VMs (Linux VM, Windows, custom ISO) use port 8006
                        is_qemu_vm = (
                            vm_type_str == "linux_vm" or
                            vm_type_str == "windows_vm" or
                            os_type == "windows" or
                            os_type == "custom" or
                            image_ref.startswith("iso:")
                        )
                        if is_qemu_vm:
                            vnc_port = "8006"
                            vnc_scheme = "http"
                            needs_auth = False
                        elif is_linuxserver:
                            vnc_port = "3000"
                            vnc_scheme = "http"
                            needs_auth = False
                        elif is_kasmweb:
                            vnc_port = "6901"
                            vnc_scheme = "https"
                            needs_auth = True
                        else:
                            vnc_port = "6901"
                            vnc_scheme = "https"
                            needs_auth = False

                        router_name = f"vnc-{vm_id_short}"
                        middlewares = [f"vnc-strip-{vm_id_short}"]
                        range_network_name = f"cyroid-{network.name}-{str(network.id)[:8]}"

                        labels.update({
                            "traefik.enable": "true",
                            "traefik.docker.network": range_network_name,
                            # Service
                            f"traefik.http.services.{router_name}.loadbalancer.server.port": vnc_port,
                            f"traefik.http.services.{router_name}.loadbalancer.server.scheme": vnc_scheme,
                            # HTTP router
                            f"traefik.http.routers.{router_name}.rule": f"PathPrefix(`/vnc/{vm.id}`)",
                            f"traefik.http.routers.{router_name}.entrypoints": "web",
                            f"traefik.http.routers.{router_name}.service": router_name,
                            f"traefik.http.routers.{router_name}.priority": "100",
                            # HTTPS router
                            f"traefik.http.routers.{router_name}-secure.rule": f"PathPrefix(`/vnc/{vm.id}`)",
                            f"traefik.http.routers.{router_name}-secure.entrypoints": "websecure",
                            f"traefik.http.routers.{router_name}-secure.tls": "true",
                            f"traefik.http.routers.{router_name}-secure.service": router_name,
                            f"traefik.http.routers.{router_name}-secure.priority": "100",
                            # Strip prefix middleware
                            f"traefik.http.middlewares.vnc-strip-{vm_id_short}.stripprefix.prefixes": f"/vnc/{vm.id}",
                        })

                        if vnc_scheme == "https":
                            labels[f"traefik.http.services.{router_name}.loadbalancer.serversTransport"] = "insecure-transport@file"

                        if needs_auth:
                            auth_string = base64.b64encode(b"kasm_user:vncpassword").decode()
                            auth_middleware = f"vnc-auth-{vm_id_short}"
                            labels[f"traefik.http.middlewares.{auth_middleware}.headers.customrequestheaders.Authorization"] = f"Basic {auth_string}"
                            middlewares.append(auth_middleware)

                        labels[f"traefik.http.routers.{router_name}.middlewares"] = ",".join(middlewares)
                        labels[f"traefik.http.routers.{router_name}-secure.middlewares"] = ",".join(middlewares)

                    if os_type == "windows":
                        # Resolve Windows version from VM or image
                        win_version = vm.windows_version
                        if not win_version and image_ref:
                            # Extract version from image_ref like "dockurr/windows:2022" or just "2022"
                            if ":" in image_ref:
                                win_version = image_ref.split(":")[-1]
                            elif image_ref.replace(".", "").isdigit() or image_ref in ["11", "10", "2025", "2022", "2019", "2016", "2012", "2008"]:
                                win_version = image_ref
                        if not win_version:
                            win_version = "11"  # Default to Windows 11

                        logger.info(f"Creating Windows VM {vm.hostname} with version: {win_version}")
                        container_id = docker.create_windows_container(
                            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                            network_id=network.docker_network_id,
                            ip_address=vm.ip_address,
                            cpu_limit=vm.cpu,
                            memory_limit_mb=vm.ram_mb,
                            disk_size_gb=vm.disk_gb,
                            windows_version=win_version,
                            labels=labels,
                            gateway=network.gateway,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search,
                        )
                    elif vm_type_str == "linux_vm":
                        # Linux VM using qemux/qemu
                        settings = get_settings()
                        vm_storage_path = os.path.join(
                            settings.vm_storage_dir,
                            str(vm.range_id),
                            str(vm.id),
                            "storage"
                        )
                        linux_distro = vm.linux_distro or "ubuntu"
                        boot_mode = vm.boot_mode or "uefi"
                        disk_type = vm.disk_type or "scsi"
                        iso_path = base_img.iso_path if base_img and base_img.iso_path else None

                        logger.info(f"Creating Linux VM {vm.hostname} with distro: {linux_distro}")
                        container_id = docker.create_linux_vm_container(
                            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                            network_id=network.docker_network_id,
                            ip_address=vm.ip_address,
                            cpu_limit=vm.cpu,
                            memory_limit_mb=vm.ram_mb,
                            disk_size_gb=vm.disk_gb,
                            linux_distro=linux_distro,
                            labels=labels,
                            iso_path=iso_path,
                            storage_path=vm_storage_path,
                            boot_mode=boot_mode,
                            disk_type=disk_type,
                            display_type=vm.display_type or "desktop",
                            gateway=network.gateway,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search,
                        )
                    elif os_type == "custom" or image_ref.startswith("iso:"):
                        # Custom ISO or ISO-based Linux VMs use qemux/qemu
                        settings = get_settings()
                        vm_storage_path = os.path.join(
                            settings.vm_storage_dir,
                            str(vm.range_id),
                            str(vm.id),
                            "storage"
                        )
                        if os_type == "custom":
                            linux_distro = "custom"
                            iso_path = base_img.iso_path if base_img and base_img.iso_path else None
                        else:
                            linux_distro = image_ref.replace("iso:", "")
                            iso_path = None

                        logger.info(f"Creating custom/ISO VM {vm.hostname} with distro: {linux_distro}")
                        container_id = docker.create_linux_vm_container(
                            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                            network_id=network.docker_network_id,
                            ip_address=vm.ip_address,
                            cpu_limit=vm.cpu,
                            memory_limit_mb=vm.ram_mb,
                            disk_size_gb=vm.disk_gb,
                            linux_distro=linux_distro,
                            labels=labels,
                            iso_path=iso_path,
                            storage_path=vm_storage_path,
                            display_type=vm.display_type or "desktop",
                            gateway=network.gateway,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search,
                        )
                    else:
                        # Docker container (Samba DC, linuxserver images, etc.)
                        needs_privileged = "samba-dc" in image_ref
                        container_id = docker.create_container(
                            name=f"cyroid-{vm.hostname}-{str(vm.id)[:8]}",
                            image=image_ref,
                            network_id=network.docker_network_id,
                            ip_address=vm.ip_address,
                            cpu_limit=vm.cpu,
                            memory_limit_mb=vm.ram_mb,
                            hostname=vm.hostname,
                            labels=labels,
                            dns_servers=network.dns_servers,
                            dns_search=network.dns_search,
                            privileged=needs_privileged,
                        )

                    vm.container_id = container_id
                    docker.start_container(container_id)

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
