# cyroid/tasks/vm_tasks.py
"""Async VM lifecycle tasks using Dramatiq."""
import dramatiq
import logging
from uuid import UUID

from cyroid.database import get_session_local
from cyroid.models.vm import VM, VMStatus
from cyroid.models.network import Network
from cyroid.models.template import VMTemplate

logger = logging.getLogger(__name__)


@dramatiq.actor(max_retries=3, min_backoff=1000)
def start_vm_task(vm_id: str):
    """Async task to start a VM."""
    logger.info(f"Starting async VM start for {vm_id}")

    db = get_session_local()()
    try:
        from cyroid.services.docker_service import get_docker_service
        docker = get_docker_service()

        vm = db.query(VM).filter(VM.id == UUID(vm_id)).first()
        if not vm:
            logger.error(f"VM {vm_id} not found")
            return

        network = db.query(Network).filter(Network.id == vm.network_id).first()
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()

        if not network or not network.docker_network_id:
            logger.error(f"Network not provisioned for VM {vm_id}")
            vm.status = VMStatus.ERROR
            db.commit()
            return

        vm.status = VMStatus.CREATING
        db.commit()

        if vm.container_id:
            docker.start_container(vm.container_id)
        else:
            labels = {
                "cyroid.range_id": str(vm.range_id),
                "cyroid.vm_id": vm_id,
                "cyroid.hostname": vm.hostname,
            }

            if template.os_type == "windows":
                # Resolve Windows version from VM, template, or base_image
                # Priority: vm.windows_version > template.os_version > base_image extraction > default
                win_version = vm.windows_version
                if not win_version and template.os_version:
                    win_version = template.os_version
                if not win_version and template.base_image:
                    # Extract version from base_image like "dockurr/windows:2022" or just "2022"
                    img = template.base_image
                    if ":" in img:
                        win_version = img.split(":")[-1]
                    elif img.replace(".", "").isdigit() or img in ["11", "10", "2025", "2022", "2019", "2016", "2012", "2008"]:
                        win_version = img
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
                    logger.warning(f"Config script failed for VM {vm_id}: {e}")

        vm.status = VMStatus.RUNNING
        db.commit()
        logger.info(f"VM {vm.hostname} started successfully")

    except Exception as e:
        logger.error(f"Failed to start VM {vm_id}: {e}")
        vm = db.query(VM).filter(VM.id == UUID(vm_id)).first()
        if vm:
            vm.status = VMStatus.ERROR
            db.commit()
    finally:
        db.close()


@dramatiq.actor(max_retries=3, min_backoff=1000)
def stop_vm_task(vm_id: str):
    """Async task to stop a VM."""
    logger.info(f"Starting async VM stop for {vm_id}")

    db = get_session_local()()
    try:
        from cyroid.services.docker_service import get_docker_service
        docker = get_docker_service()

        vm = db.query(VM).filter(VM.id == UUID(vm_id)).first()
        if not vm:
            logger.error(f"VM {vm_id} not found")
            return

        if vm.container_id:
            docker.stop_container(vm.container_id)

        vm.status = VMStatus.STOPPED
        db.commit()
        logger.info(f"VM {vm.hostname} stopped successfully")

    except Exception as e:
        logger.error(f"Failed to stop VM {vm_id}: {e}")
    finally:
        db.close()


@dramatiq.actor(max_retries=3, min_backoff=1000)
def restart_vm_task(vm_id: str):
    """Async task to restart a VM."""
    logger.info(f"Starting async VM restart for {vm_id}")

    db = get_session_local()()
    try:
        from cyroid.services.docker_service import get_docker_service
        docker = get_docker_service()

        vm = db.query(VM).filter(VM.id == UUID(vm_id)).first()
        if not vm:
            logger.error(f"VM {vm_id} not found")
            return

        if vm.container_id:
            docker.restart_container(vm.container_id)

        vm.status = VMStatus.RUNNING
        db.commit()
        logger.info(f"VM {vm.hostname} restarted successfully")

    except Exception as e:
        logger.error(f"Failed to restart VM {vm_id}: {e}")
        vm = db.query(VM).filter(VM.id == UUID(vm_id)).first()
        if vm:
            vm.status = VMStatus.ERROR
            db.commit()
    finally:
        db.close()
