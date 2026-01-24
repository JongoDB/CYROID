# backend/cyroid/services/range_deployment_service.py
"""
Range deployment service with DinD isolation.

This service handles the lifecycle of range deployments using DinD
(Docker-in-Docker) for complete network isolation. Each range runs in its
own DinD container, allowing multiple ranges to use identical IP spaces
without conflicts.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from cyroid.config import get_settings
from cyroid.models import Range, Network, VM, RangeStatus
from cyroid.models.vm import VMStatus
from cyroid.models.template import VMType
from cyroid.models.base_image import BaseImage
from cyroid.models.golden_image import GoldenImage
from cyroid.models.snapshot import Snapshot
from cyroid.models.event_log import EventType
from cyroid.services.event_service import EventService
from cyroid.services.dind_service import DinDService, get_dind_service
from cyroid.services.docker_service import DockerService, get_docker_service
from cyroid.services.traefik_route_service import get_traefik_route_service

logger = logging.getLogger(__name__)
settings = get_settings()


class RangeDeploymentService:
    """
    Manages range deployment lifecycle with DinD-based isolation.

    Each range runs inside its own Docker-in-Docker container:
    - Networks and VMs are created inside the DinD container
    - Provides complete network namespace isolation
    - Allows identical IP spaces across concurrent ranges
    """

    def __init__(
        self,
        docker_service: Optional[DockerService] = None,
        dind_service: Optional[DinDService] = None,
    ):
        self._docker_service = docker_service
        self._dind_service = dind_service

    @property
    def docker_service(self) -> DockerService:
        if self._docker_service is None:
            self._docker_service = get_docker_service()
        return self._docker_service

    @property
    def dind_service(self) -> DinDService:
        if self._dind_service is None:
            self._dind_service = get_dind_service()
        return self._dind_service

    async def deploy_range(
        self,
        db: Session,
        range_id: UUID,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Deploy a range instance inside a DinD container.

        Steps:
        1. Create DinD container for the range
        2. Create Docker networks inside DinD
        3. Pull required images into DinD
        4. Create VM containers inside DinD

        Args:
            db: Database session
            range_id: Range UUID
            memory_limit: Optional memory limit for DinD container
            cpu_limit: Optional CPU limit for DinD container

        Returns:
            Deployment result dict
        """
        # Get range from database
        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            raise ValueError(f"Range {range_id} not found")

        range_obj.status = RangeStatus.DEPLOYING
        db.commit()

        try:
            result = await self._deploy_with_dind(
                db, range_obj, memory_limit, cpu_limit
            )

            # Update range status
            range_obj.status = RangeStatus.RUNNING
            range_obj.deployed_at = datetime.utcnow()
            range_obj.started_at = datetime.utcnow()
            range_obj.error_message = None
            db.commit()

            return result

        except Exception as e:
            logger.error(f"Failed to deploy range {range_id}: {e}")
            range_obj.status = RangeStatus.ERROR
            range_obj.error_message = str(e)[:1000]
            db.commit()
            raise

    async def _deploy_with_dind(
        self,
        db: Session,
        range_obj: Range,
        memory_limit: Optional[str],
        cpu_limit: Optional[float],
    ) -> Dict[str, Any]:
        """Deploy range inside a DinD container."""
        range_id = str(range_obj.id)
        range_uuid = range_obj.id

        logger.info(f"Deploying range {range_id} with DinD isolation")

        # Initialize event service for progress logging
        event_service = EventService(db)

        # Use default limits if not specified
        memory_limit = memory_limit or getattr(settings, "range_default_memory", "8g")
        cpu_limit = cpu_limit or getattr(settings, "range_default_cpu", 4.0)

        # 1. Create DinD container with progress reporting
        event_service.log_event(
            range_id=range_uuid,
            event_type=EventType.ROUTER_CREATING,
            message="Creating DinD container for range isolation...",
        )

        def dind_progress_callback(msg: str) -> None:
            """Report DinD creation progress as deployment step events."""
            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.DEPLOYMENT_STEP,
                message=msg,
            )

        dind_info = await self.dind_service.create_range_container(
            range_id=range_id,
            range_name=range_obj.name,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            progress_callback=dind_progress_callback,
        )

        event_service.log_event(
            range_id=range_uuid,
            event_type=EventType.ROUTER_CREATED,
            message=f"DinD container ready at {dind_info['mgmt_ip']}",
        )

        # Store DinD info in range
        range_obj.dind_container_id = dind_info["container_id"]
        range_obj.dind_container_name = dind_info["container_name"]
        range_obj.dind_mgmt_ip = dind_info["mgmt_ip"]
        range_obj.dind_docker_url = dind_info["docker_url"]
        db.commit()

        docker_url = dind_info["docker_url"]

        # 2. Create networks inside DinD
        networks = db.query(Network).filter(Network.range_id == range_obj.id).all()
        network_ids = {}

        for network in networks:
            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.NETWORK_CREATING,
                message=f"Creating network '{network.name}' ({network.subnet})...",
                network_id=network.id,
            )

            labels = {
                "cyroid.range_id": range_id,
                "cyroid.network_id": str(network.id),
            }

            network_docker_id = await self.docker_service.create_range_network_dind(
                range_id=range_id,
                docker_url=docker_url,
                name=network.name,
                subnet=network.subnet,
                gateway=network.gateway,
                internal=network.is_isolated,
                labels=labels,
            )

            network.docker_network_id = network_docker_id
            network_ids[str(network.id)] = network_docker_id

            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.NETWORK_CREATED,
                message=f"Network '{network.name}' created",
                network_id=network.id,
            )

        db.commit()

        # 2b. Set up iptables network isolation inside DinD
        network_names = [network.name for network in networks]
        # Networks with internet_enabled=True get NAT/outbound access
        allow_internet = [
            network.name for network in networks if network.internet_enabled
        ]

        await self.dind_service.setup_network_isolation_in_dind(
            range_id=range_id,
            docker_url=docker_url,
            networks=network_names,
            allow_internet=allow_internet,
        )

        # 3. Pull required images into DinD
        vms = db.query(VM).filter(VM.range_id == range_obj.id).all()
        unique_images = set()
        for vm in vms:
            # Get container image from Image Library sources
            if vm.base_image_id:
                base_img = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first()
                if base_img and base_img.image_type == "container":
                    image_tag = base_img.docker_image_tag or base_img.docker_image_id
                    if image_tag:
                        unique_images.add(image_tag)
            elif vm.golden_image_id:
                golden_img = db.query(GoldenImage).filter(GoldenImage.id == vm.golden_image_id).first()
                if golden_img:
                    image_tag = golden_img.docker_image_tag or golden_img.docker_image_id
                    if image_tag:
                        unique_images.add(image_tag)
            elif vm.snapshot_id:
                snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first()
                if snapshot:
                    image_tag = snapshot.docker_image_tag or snapshot.docker_image_id
                    if image_tag:
                        unique_images.add(image_tag)

        if unique_images:
            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.DEPLOYMENT_STEP,
                message=f"Transferring {len(unique_images)} image(s) to DinD container...",
            )

        for idx, image in enumerate(unique_images, 1):
            # Create a progress callback that emits events for this image
            last_status = [None]  # Use list to allow modification in closure
            last_pct = [0]  # Track last reported percentage

            def image_progress_callback(transferred: int, total: int, status: str) -> None:
                # Handle percentage progress updates (format: 'transferring:XX')
                if status.startswith('transferring:'):
                    pct = int(status.split(':')[1])
                    # Only emit progress at 25%, 50%, 75% to avoid spam
                    if pct >= last_pct[0] + 25:
                        last_pct[0] = pct
                        size_mb = total / 1024 / 1024
                        transferred_mb = transferred / 1024 / 1024
                        event_service.log_event(
                            range_id=range_uuid,
                            event_type=EventType.DEPLOYMENT_STEP,
                            message=f"Transferring {image}: {pct}% ({transferred_mb:.0f}/{size_mb:.0f} MB)",
                        )
                    return

                # Only emit event if status changed (avoid spamming)
                if status != last_status[0]:
                    last_status[0] = status
                    if status == 'found_on_host':
                        size_mb = total / 1024 / 1024
                        event_service.log_event(
                            range_id=range_uuid,
                            event_type=EventType.DEPLOYMENT_STEP,
                            message=f"Image {idx}/{len(unique_images)}: {image} found on host ({size_mb:.1f} MB)",
                        )
                    elif status == 'transferring':
                        event_service.log_event(
                            range_id=range_uuid,
                            event_type=EventType.DEPLOYMENT_STEP,
                            message=f"Copying {image} into DinD container (0%)...",
                        )
                    elif status == 'already_exists':
                        event_service.log_event(
                            range_id=range_uuid,
                            event_type=EventType.DEPLOYMENT_STEP,
                            message=f"Image {image} already in DinD, skipping",
                        )
                    elif status == 'pulling_to_host':
                        event_service.log_event(
                            range_id=range_uuid,
                            event_type=EventType.DEPLOYMENT_STEP,
                            message=f"Pulling {image} from registry to host...",
                        )

            try:
                await self.docker_service.pull_image_to_dind(
                    range_id=range_id,
                    docker_url=docker_url,
                    image=image,
                    progress_callback=image_progress_callback,
                )
                event_service.log_event(
                    range_id=range_uuid,
                    event_type=EventType.DEPLOYMENT_STEP,
                    message=f"Image {idx}/{len(unique_images)} ready: {image}",
                )
            except Exception as e:
                error_msg = f"Failed to transfer image {image}: {e}"
                logger.error(error_msg)
                event_service.log_event(
                    range_id=range_uuid,
                    event_type=EventType.DEPLOYMENT_STEP,
                    message=f"ERROR: {error_msg}",
                )
                # Re-raise to fail the deployment with a clear message
                raise RuntimeError(error_msg) from e

        # 4. Create VMs inside DinD
        total_vms = len(vms)
        for vm_idx, vm in enumerate(vms, 1):
            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.VM_CREATING,
                message=f"Creating VM {vm_idx}/{total_vms}: '{vm.hostname}' ({vm.ip_address})...",
                vm_id=vm.id,
            )

            # Determine container image from Image Library or legacy template/snapshot
            container_image = None
            if vm.base_image_id and vm.base_image:
                # New Image Library: Base Image
                if vm.base_image.image_type == "container":
                    container_image = vm.base_image.docker_image_tag or vm.base_image.docker_image_id
                else:
                    logger.warning(f"VM {vm.hostname} uses ISO-based base image, not supported in DinD yet")
                    continue
            elif vm.golden_image_id and vm.golden_image:
                # New Image Library: Golden Image
                container_image = vm.golden_image.docker_image_tag or vm.golden_image.docker_image_id
            elif vm.snapshot_id and vm.snapshot:
                # Snapshot
                container_image = vm.snapshot.docker_image_tag or vm.snapshot.docker_image_id

            if not container_image:
                logger.warning(f"VM {vm.hostname} has no container image, skipping")
                continue

            network = db.query(Network).filter(Network.id == vm.network_id).first()
            if not network:
                logger.warning(f"VM {vm.hostname} has no network, skipping")
                continue

            labels = {
                "cyroid.range_id": range_id,
                "cyroid.vm_id": str(vm.id),
            }

            # Set up environment variables based on image type
            environment = {}
            privileged = False

            # macOS VM (dockur/macos) - requires VERSION env and privileged mode for KVM
            if "dockur/macos" in container_image.lower():
                # Map version number to dockur version name
                macos_version_map = {
                    "15": "sequoia",
                    "14": "sonoma",
                    "13": "ventura",
                    "12": "monterey",
                    "11": "big-sur",
                }
                version_name = macos_version_map.get(vm.macos_version, "sonoma")  # Default to Sonoma
                environment["VERSION"] = version_name
                privileged = True  # Required for KVM access
                labels["cyroid.vm_type"] = "macos"

            # Windows VM (dockur/windows) - set VERSION if specified
            elif "dockur/windows" in container_image.lower():
                if vm.windows_version:
                    environment["VERSION"] = vm.windows_version
                privileged = True  # Required for KVM access
                labels["cyroid.vm_type"] = "windows"

            # Linux VM (qemux/qemu) - uses VERSION for distro
            elif "qemux/qemu" in container_image.lower():
                privileged = True  # Required for KVM access
                labels["cyroid.vm_type"] = "linux"

            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.DEPLOYMENT_STEP,
                message=f"Creating container for '{vm.hostname}' using image {container_image}...",
                vm_id=vm.id,
            )

            container_id = await self.docker_service.create_range_container_dind(
                range_id=range_id,
                docker_url=docker_url,
                name=vm.hostname,
                image=container_image,
                network_name=network.name,
                ip_address=vm.ip_address,
                cpu_limit=vm.cpu or 2,
                memory_limit_mb=vm.ram_mb or 2048,
                hostname=vm.hostname,
                labels=labels,
                dns_servers=network.dns_servers,
                dns_search=network.dns_search,
                environment=environment if environment else None,
                privileged=privileged,
            )

            vm.container_id = container_id

            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.DEPLOYMENT_STEP,
                message=f"Container created for '{vm.hostname}', starting...",
                vm_id=vm.id,
            )

            # Start the container
            await self.docker_service.start_range_container_dind(
                range_id=range_id,
                docker_url=docker_url,
                container_id=container_id,
            )

            # Mark VM as running after successful start (Issue #75)
            vm.status = VMStatus.RUNNING

            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.VM_STARTED,
                message=f"VM '{vm.hostname}' running on {network.name} ({vm.ip_address})",
                vm_id=vm.id,
            )

        db.commit()

        # 5. Set up VNC port forwarding using iptables DNAT (replaces nginx proxy)
        vm_ports = []
        for vm in vms:
            if vm.container_id and vm.ip_address:
                # Determine VNC port based on VM type and image
                vnc_port = 8006  # Default for QEMU/Windows

                # Get base image name for VNC port detection
                base_image = ""
                vm_type = None
                if vm.base_image_id and vm.base_image:
                    base_image = vm.base_image.docker_image_tag or ""
                    vm_type = vm.base_image.vm_type
                elif vm.golden_image_id and vm.golden_image:
                    base_image = vm.golden_image.docker_image_tag or ""
                    vm_type = vm.golden_image.vm_type
                elif vm.snapshot_id and vm.snapshot:
                    base_image = vm.snapshot.docker_image_tag or ""
                    vm_type = vm.snapshot.vm_type

                # Check if it's a container type for VNC port detection
                if vm_type == "container" or vm_type == VMType.CONTAINER:
                    if "kasmweb" in base_image:
                        vnc_port = 6901
                    elif "linuxserver/" in base_image or "lscr.io/linuxserver" in base_image:
                        vnc_port = 3000
                    else:
                        vnc_port = 6901  # Default for containers

                vm_ports.append({
                    "vm_id": str(vm.id),
                    "hostname": vm.hostname,
                    "vnc_port": vnc_port,
                    "ip_address": vm.ip_address,
                })

        if vm_ports:
            event_service.log_event(
                range_id=range_uuid,
                event_type=EventType.DEPLOYMENT_STEP,
                message=f"Setting up VNC console access for {len(vm_ports)} VM(s)...",
            )
            try:
                port_mappings = await self.dind_service.setup_vnc_port_forwarding(
                    range_id=range_id,
                    vm_ports=vm_ports,
                )
                range_obj.vnc_proxy_mappings = port_mappings
                db.commit()
                logger.info(f"Set up VNC port forwarding for range {range_id} with {len(vm_ports)} ports")

                # Generate Traefik routes for VNC console access
                traefik_service = get_traefik_route_service()
                route_file = traefik_service.generate_vnc_routes(range_id, port_mappings)
                if route_file:
                    logger.info(f"Generated Traefik VNC routes for range {range_id}: {route_file}")
                else:
                    logger.warning(f"Could not generate Traefik VNC routes for range {range_id}")

            except Exception as e:
                logger.warning(f"Failed to set up VNC port forwarding for range {range_id}: {e}")
                # Don't fail the deployment if VNC forwarding fails - console will be unavailable

        return {
            "range_id": range_id,
            "status": "deployed",
            "isolation": "dind",
            "dind_container": dind_info["container_name"],
            "mgmt_ip": dind_info["mgmt_ip"],
            "docker_url": docker_url,
            "networks_created": len(networks),
            "vms_created": len([vm for vm in vms if vm.container_id]),
            "vnc_proxy_ports": len(vm_ports),
        }

    async def destroy_range(
        self,
        db: Session,
        range_id: UUID,
    ) -> Dict[str, Any]:
        """
        Destroy a range instance by deleting its DinD container.

        This cleans up everything inside the DinD container automatically.
        """
        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            raise ValueError(f"Range {range_id} not found")

        range_id_str = str(range_id)

        # Remove Traefik VNC routes first
        traefik_service = get_traefik_route_service()
        traefik_service.remove_vnc_routes(range_id_str)

        # Delete the DinD container (cleans up everything inside)
        logger.info(f"Destroying range {range_id_str} DinD container")
        await self.dind_service.delete_range_container(range_id_str)

        # Clear DinD info
        range_obj.dind_container_id = None
        range_obj.dind_container_name = None
        range_obj.dind_mgmt_ip = None
        range_obj.dind_docker_url = None
        range_obj.vnc_proxy_mappings = None

        # Clear VM container IDs
        vms = db.query(VM).filter(VM.range_id == range_id).all()
        for vm in vms:
            vm.container_id = None

        # Clear network Docker IDs
        networks = db.query(Network).filter(Network.range_id == range_id).all()
        for network in networks:
            network.docker_network_id = None

        # Update range status
        range_obj.status = RangeStatus.STOPPED
        range_obj.stopped_at = datetime.utcnow()
        db.commit()

        return {
            "range_id": range_id_str,
            "status": "destroyed",
        }

    async def sync_range(
        self,
        db: Session,
        range_id: UUID,
    ) -> Dict[str, Any]:
        """
        Sync new networks and VMs to an existing deployed range.

        This provisions resources that were added after initial deployment:
        - Networks without docker_network_id → created in DinD
        - VMs without container_id → created in DinD

        Does NOT recreate the DinD container.
        """
        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            raise ValueError(f"Range {range_id} not found")

        if not range_obj.dind_container_id or not range_obj.dind_docker_url:
            raise ValueError(f"Range {range_id} is not deployed (missing DinD container)")

        range_id_str = str(range_id)
        docker_url = range_obj.dind_docker_url

        logger.info(f"Syncing range {range_id_str} - provisioning new resources to DinD")

        result = {
            "range_id": range_id_str,
            "networks_created": 0,
            "vms_created": 0,
            "images_pulled": 0,
            "network_details": [],
            "vm_details": [],
        }

        # 1. Create any new networks
        networks = db.query(Network).filter(Network.range_id == range_id).all()
        new_networks = [n for n in networks if not n.docker_network_id]

        for network in new_networks:
            logger.info(f"Creating network {network.name} in DinD")
            labels = {
                "cyroid.range_id": range_id_str,
                "cyroid.network_id": str(network.id),
            }

            network_docker_id = await self.docker_service.create_range_network_dind(
                range_id=range_id_str,
                docker_url=docker_url,
                name=network.name,
                subnet=network.subnet,
                gateway=network.gateway,
                internal=network.is_isolated,
                labels=labels,
            )

            network.docker_network_id = network_docker_id
            result["networks_created"] += 1
            result["network_details"].append({
                "name": network.name,
                "subnet": network.subnet,
                "docker_id": network_docker_id[:12],
            })

        db.commit()

        # Update iptables if we added networks
        if new_networks:
            network_names = [n.name for n in networks]
            allow_internet = [n.name for n in networks if n.internet_enabled]
            await self.dind_service.setup_network_isolation_in_dind(
                range_id=range_id_str,
                docker_url=docker_url,
                networks=network_names,
                allow_internet=allow_internet,
            )

        # 2. Pull images for new VMs
        vms = db.query(VM).filter(VM.range_id == range_id).all()
        new_vms = [v for v in vms if not v.container_id]

        # Collect unique images needed for new VMs
        unique_images = set()
        for vm in new_vms:
            if vm.base_image_id:
                base_img = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first()
                if base_img:
                    if base_img.image_type == "container":
                        # Container-based VMs use the docker image directly
                        image_tag = base_img.docker_image_tag or base_img.docker_image_id
                        if image_tag:
                            unique_images.add(image_tag)
                    elif base_img.image_type == "iso":
                        # ISO-based VMs use QEMU images based on vm_type
                        if base_img.vm_type == VMType.WINDOWS_VM:
                            if base_img.native_arch == "arm64":
                                unique_images.add("dockurr/windows-arm:latest")
                            else:
                                unique_images.add("dockurr/windows:latest")
                        elif base_img.vm_type == VMType.LINUX_VM:
                            unique_images.add("qemux/qemu:latest")
                        elif base_img.vm_type == VMType.MACOS_VM:
                            unique_images.add("dockurr/macos:latest")
            elif vm.golden_image_id:
                golden_img = db.query(GoldenImage).filter(GoldenImage.id == vm.golden_image_id).first()
                if golden_img:
                    image_tag = golden_img.docker_image_tag or golden_img.docker_image_id
                    if image_tag:
                        unique_images.add(image_tag)
            elif vm.snapshot_id:
                snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first()
                if snapshot:
                    image_tag = snapshot.docker_image_tag or snapshot.docker_image_id
                    if image_tag:
                        unique_images.add(image_tag)

        # Pull images into DinD
        for image in unique_images:
            logger.info(f"Pulling image {image} into DinD for sync")
            await self.docker_service.pull_image_to_dind(range_id_str, docker_url, image)
            result["images_pulled"] += 1

        # 3. Create new VMs
        created_vms = []  # Track successfully created VMs for VNC setup

        for vm in new_vms:
            logger.info(f"Creating VM {vm.hostname} in DinD")
            try:
                # Get image tag
                image_tag = None
                vm_type = None
                if vm.base_image_id:
                    base_img = db.query(BaseImage).filter(BaseImage.id == vm.base_image_id).first()
                    if base_img:
                        image_tag = base_img.docker_image_tag or base_img.docker_image_id
                        vm_type = base_img.vm_type
                elif vm.golden_image_id:
                    golden_img = db.query(GoldenImage).filter(GoldenImage.id == vm.golden_image_id).first()
                    if golden_img:
                        image_tag = golden_img.docker_image_tag or golden_img.docker_image_id
                        vm_type = golden_img.vm_type
                elif vm.snapshot_id:
                    snapshot = db.query(Snapshot).filter(Snapshot.id == vm.snapshot_id).first()
                    if snapshot:
                        image_tag = snapshot.docker_image_tag or snapshot.docker_image_id
                        vm_type = snapshot.vm_type

                # For ISO-based VMs, derive image from vm_type
                if not image_tag and vm_type:
                    if vm_type == VMType.WINDOWS_VM:
                        # Check architecture for Windows ARM
                        if base_img and base_img.native_arch == "arm64":
                            image_tag = "dockurr/windows-arm:latest"
                        else:
                            image_tag = "dockurr/windows:latest"
                        logger.info(f"Using {image_tag} for Windows ISO VM {vm.hostname}")
                    elif vm_type == VMType.LINUX_VM:
                        image_tag = "qemux/qemu:latest"
                        logger.info(f"Using {image_tag} for Linux ISO VM {vm.hostname}")
                    elif vm_type == VMType.MACOS_VM:
                        image_tag = "dockurr/macos:latest"
                        logger.info(f"Using {image_tag} for macOS VM {vm.hostname}")

                if not image_tag:
                    logger.warning(f"No image found for VM {vm.hostname}, skipping")
                    vm.status = VMStatus.ERROR
                    vm.error_message = "No image configured"
                    continue

                # Get network
                vm_network = db.query(Network).filter(Network.id == vm.network_id).first()
                if not vm_network or not vm_network.docker_network_id:
                    logger.warning(f"Network not provisioned for VM {vm.hostname}, skipping")
                    vm.status = VMStatus.ERROR
                    vm.error_message = "Network not provisioned"
                    continue

                labels = {
                    "cyroid.range_id": range_id_str,
                    "cyroid.vm_id": str(vm.id),
                }

                # Set up environment variables based on image type
                environment = {}
                privileged = False
                volumes = {}

                # Get ISO path if this is an ISO-based VM
                iso_path = None
                if base_img and base_img.image_type == "iso" and base_img.iso_path:
                    iso_path = base_img.iso_path

                # macOS VM (dockurr/macos) - requires VERSION env and privileged mode for KVM
                if "dockurr/macos" in image_tag.lower():
                    macos_version_map = {
                        "15": "sequoia",
                        "14": "sonoma",
                        "13": "ventura",
                        "12": "monterey",
                        "11": "big-sur",
                    }
                    version_name = macos_version_map.get(vm.macos_version, "sonoma")
                    environment["VERSION"] = version_name
                    privileged = True
                    labels["cyroid.vm_type"] = "macos"

                # Windows VM (dockurr/windows) - set VERSION if specified
                elif "dockurr/windows" in image_tag.lower():
                    if vm.windows_version:
                        environment["VERSION"] = vm.windows_version
                    # For Windows ISO VMs, mount the ISO file directly
                    if iso_path:
                        import os
                        # Mount ISO file directly to /boot.iso (same as start_vm)
                        volumes[iso_path] = {"bind": "/boot.iso", "mode": "ro"}
                        environment["BOOT"] = "/boot.iso"
                        logger.info(f"Mounting Windows ISO: {iso_path} -> /boot.iso")
                    # Set resource limits
                    environment["CPU_CORES"] = str(vm.cpu or 2)
                    environment["RAM_SIZE"] = f"{vm.ram_mb or 4096}M"
                    environment["DISK_SIZE"] = f"{vm.disk_gb or 64}G"
                    # Disable KVM requirement for Docker Desktop / nested virtualization
                    environment["KVM"] = "N"
                    privileged = True
                    labels["cyroid.vm_type"] = "windows"

                # Linux VM (qemux/qemu) - uses VERSION for distro or BOOT for custom ISO
                elif "qemux/qemu" in image_tag.lower():
                    # For Linux ISO VMs, mount the ISO file directly and set BOOT
                    if iso_path:
                        import os
                        # Mount ISO file directly to /boot.iso (same as start_vm)
                        volumes[iso_path] = {"bind": "/boot.iso", "mode": "ro"}
                        environment["BOOT"] = "/boot.iso"
                        logger.info(f"Mounting Linux ISO: {iso_path} -> /boot.iso")
                    # Set resource limits
                    environment["CPU_CORES"] = str(vm.cpu or 2)
                    environment["RAM_SIZE"] = f"{vm.ram_mb or 2048}M"
                    environment["DISK_SIZE"] = f"{vm.disk_gb or 20}G"
                    # Disable KVM requirement for Docker Desktop / nested virtualization
                    environment["KVM"] = "N"
                    privileged = True
                    labels["cyroid.vm_type"] = "linux"

                # Create container (same pattern as deploy_range)
                container_id = await self.docker_service.create_range_container_dind(
                    range_id=range_id_str,
                    docker_url=docker_url,
                    name=vm.hostname,
                    image=image_tag,
                    network_name=vm_network.name,
                    ip_address=vm.ip_address,
                    cpu_limit=vm.cpu or 2,
                    memory_limit_mb=vm.ram_mb or 2048,
                    hostname=vm.hostname,
                    labels=labels,
                    dns_servers=vm_network.dns_servers,
                    dns_search=vm_network.dns_search,
                    environment=environment if environment else None,
                    privileged=privileged,
                    volumes=volumes if volumes else None,
                )

                vm.container_id = container_id

                # Start the container
                await self.docker_service.start_range_container_dind(
                    range_id=range_id_str,
                    docker_url=docker_url,
                    container_id=container_id,
                )

                vm.status = VMStatus.RUNNING

                # Determine VNC port based on image type
                vnc_port = 8006  # Default for QEMU/Windows
                if vm_type == "container" or vm_type == VMType.CONTAINER:
                    if "kasmweb" in image_tag:
                        vnc_port = 6901
                    elif "linuxserver/" in image_tag or "lscr.io/linuxserver" in image_tag:
                        vnc_port = 3000
                    else:
                        vnc_port = 6901  # Default for containers

                created_vms.append({
                    "vm_id": str(vm.id),
                    "hostname": vm.hostname,
                    "vnc_port": vnc_port,
                    "ip_address": vm.ip_address,
                    "container_id": container_id,
                })

                result["vms_created"] += 1
                result["vm_details"].append({
                    "hostname": vm.hostname,
                    "container_id": container_id[:12],
                    "vnc_port": vnc_port,
                })

            except Exception as e:
                logger.error(f"Failed to create VM {vm.hostname}: {e}")
                vm.status = VMStatus.ERROR
                vm.error_message = str(e)[:500]

        db.commit()

        # 4. Set up VNC port forwarding for newly created VMs
        if created_vms:
            traefik_service = get_traefik_route_service()
            try:
                # Get existing mappings to calculate next available port
                existing_mappings = range_obj.vnc_proxy_mappings or {}

                port_mappings = await self.dind_service.setup_vnc_port_forwarding(
                    range_id=range_id_str,
                    vm_ports=created_vms,
                    existing_mappings=existing_mappings,
                )
                # Merge new port mappings with existing ones
                existing_mappings.update(port_mappings)
                range_obj.vnc_proxy_mappings = existing_mappings
                db.commit()

                # Generate Traefik routes for VNC console access
                route_file = traefik_service.generate_vnc_routes(range_id_str, existing_mappings)
                if route_file:
                    logger.info(f"Updated Traefik VNC routes for range {range_id_str}")
            except Exception as e:
                logger.error(f"Failed to set up VNC forwarding for synced VMs: {e}")

        logger.info(f"Sync complete for range {range_id_str}: {result['networks_created']} networks, {result['vms_created']} VMs")

        return result

    async def get_range_status(
        self,
        db: Session,
        range_id: UUID,
    ) -> Dict[str, Any]:
        """Get detailed status of a range including DinD container info."""
        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            raise ValueError(f"Range {range_id} not found")

        range_id_str = str(range_id)
        result = {
            "range_id": range_id_str,
            "name": range_obj.name,
            "status": range_obj.status.value if range_obj.status else "unknown",
            "deployed_at": range_obj.deployed_at.isoformat() if range_obj.deployed_at else None,
        }

        if range_obj.dind_container_id:
            # Get DinD container status
            dind_info = await self.dind_service.get_container_info(range_id_str)
            if dind_info:
                result["dind"] = {
                    "container_name": dind_info["container_name"],
                    "container_status": dind_info["status"],
                    "mgmt_ip": dind_info["mgmt_ip"],
                    "docker_url": dind_info.get("docker_url"),
                }

                # Get VMs inside DinD if running
                if dind_info["status"] == "running" and dind_info.get("docker_url"):
                    try:
                        vms = await self.docker_service.list_range_containers_dind(
                            range_id=range_id_str,
                            docker_url=dind_info["docker_url"],
                        )
                        result["vms"] = vms
                    except Exception as e:
                        logger.warning(f"Could not list VMs for range {range_id_str}: {e}")
                        result["vms"] = []
            else:
                result["dind"] = None
        else:
            result["dind"] = None
            result["vms"] = []

        return result


# Singleton instance
_range_deployment_service: Optional[RangeDeploymentService] = None


def get_range_deployment_service() -> RangeDeploymentService:
    """Get the range deployment service singleton."""
    global _range_deployment_service
    if _range_deployment_service is None:
        _range_deployment_service = RangeDeploymentService()
    return _range_deployment_service
