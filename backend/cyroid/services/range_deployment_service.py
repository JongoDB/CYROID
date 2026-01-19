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
from cyroid.services.dind_service import DinDService, get_dind_service
from cyroid.services.docker_service import DockerService, get_docker_service

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

        logger.info(f"Deploying range {range_id} with DinD isolation")

        # Use default limits if not specified
        memory_limit = memory_limit or getattr(settings, "range_default_memory", "8g")
        cpu_limit = cpu_limit or getattr(settings, "range_default_cpu", 4.0)

        # 1. Create DinD container
        dind_info = await self.dind_service.create_range_container(
            range_id=range_id,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
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

        db.commit()

        # 3. Pull required images into DinD
        vms = db.query(VM).filter(VM.range_id == range_obj.id).all()
        unique_images = set()
        for vm in vms:
            if vm.template and vm.template.image:
                unique_images.add(vm.template.image)

        for image in unique_images:
            try:
                await self.docker_service.pull_image_to_dind(
                    range_id=range_id,
                    docker_url=docker_url,
                    image=image,
                )
            except Exception as e:
                logger.warning(f"Could not pull image {image} into DinD: {e}")

        # 4. Create VMs inside DinD
        for vm in vms:
            if not vm.template or not vm.template.image:
                logger.warning(f"VM {vm.hostname} has no template/image, skipping")
                continue

            network = db.query(Network).filter(Network.id == vm.network_id).first()
            if not network:
                logger.warning(f"VM {vm.hostname} has no network, skipping")
                continue

            labels = {
                "cyroid.range_id": range_id,
                "cyroid.vm_id": str(vm.id),
            }

            container_id = await self.docker_service.create_range_container_dind(
                range_id=range_id,
                docker_url=docker_url,
                name=vm.hostname,
                image=vm.template.image,
                network_name=network.name,
                ip_address=vm.ip_address,
                cpu_limit=vm.cpu or 2,
                memory_limit_mb=vm.ram_mb or 2048,
                hostname=vm.hostname,
                labels=labels,
                dns_servers=network.dns_servers,
                dns_search=network.dns_search,
            )

            vm.container_id = container_id

            # Start the container
            await self.docker_service.start_range_container_dind(
                range_id=range_id,
                docker_url=docker_url,
                container_id=container_id,
            )

        db.commit()

        return {
            "range_id": range_id,
            "status": "deployed",
            "isolation": "dind",
            "dind_container": dind_info["container_name"],
            "mgmt_ip": dind_info["mgmt_ip"],
            "docker_url": docker_url,
            "networks_created": len(networks),
            "vms_created": len([vm for vm in vms if vm.container_id]),
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

        # Delete the DinD container (cleans up everything inside)
        logger.info(f"Destroying range {range_id_str} DinD container")
        await self.dind_service.delete_range_container(range_id_str)

        # Clear DinD info
        range_obj.dind_container_id = None
        range_obj.dind_container_name = None
        range_obj.dind_mgmt_ip = None
        range_obj.dind_docker_url = None

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
