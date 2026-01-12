# cyroid/tasks/deployment.py
"""Async deployment tasks using Dramatiq."""
import dramatiq
import logging
from uuid import UUID

from cyroid.database import SessionLocal
from cyroid.models.range import Range, RangeStatus
from cyroid.models.network import Network, IsolationLevel
from cyroid.models.vm import VM, VMStatus
from cyroid.models.template import VMTemplate

logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=3, min_backoff=1000)
def deploy_range_task(range_id: str):
    """
    Async task to deploy a range.
    Creates Docker networks and starts all VMs.
    """
    logger.info(f"Starting async deployment for range {range_id}")

    db = SessionLocal()
    try:
        from cyroid.services.docker_service import get_docker_service
        docker = get_docker_service()

        range_obj = db.query(Range).filter(Range.id == UUID(range_id)).first()
        if not range_obj:
            logger.error(f"Range {range_id} not found")
            return

        # Set to deploying
        range_obj.status = RangeStatus.DEPLOYING
        db.commit()

        # Step 1: Provision all networks
        networks = db.query(Network).filter(Network.range_id == UUID(range_id)).all()
        for network in networks:
            if not network.docker_network_id:
                internal = network.isolation_level in [IsolationLevel.COMPLETE, IsolationLevel.CONTROLLED]
                docker_network_id = docker.create_network(
                    name=f"cyroid-{network.name}-{str(network.id)[:8]}",
                    subnet=network.subnet,
                    gateway=network.gateway,
                    internal=internal,
                    labels={
                        "cyroid.range_id": range_id,
                        "cyroid.network_id": str(network.id),
                    }
                )
                network.docker_network_id = docker_network_id
                db.commit()
                logger.info(f"Provisioned network {network.name}")

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
    Stops and removes all VMs, then removes networks.
    """
    logger.info(f"Starting async teardown for range {range_id}")

    db = SessionLocal()
    try:
        from cyroid.services.docker_service import get_docker_service
        docker = get_docker_service()

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

        # Step 2: Remove all Docker networks
        networks = db.query(Network).filter(Network.range_id == UUID(range_id)).all()
        for network in networks:
            if network.docker_network_id:
                try:
                    docker.delete_network(network.docker_network_id)
                except Exception as e:
                    logger.warning(f"Failed to delete network {network.id}: {e}")
                network.docker_network_id = None
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
