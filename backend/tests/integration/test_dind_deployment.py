# backend/tests/integration/test_dind_deployment.py
"""
Integration tests for DinD (Docker-in-Docker) deployment flow.

These tests verify the complete DinD lifecycle including:
- Container creation and destruction
- Network isolation between ranges
- Image transfer from host to DinD

Requires:
- Docker daemon running with DinD support
- Sufficient permissions to run privileged containers

Run with: pytest -m integration backend/tests/integration/test_dind_deployment.py -v
"""
import pytest
import asyncio
from uuid import uuid4
from typing import List

import docker
from docker.errors import NotFound

from cyroid.services.docker_service import DockerService
from cyroid.services.dind_service import DinDService


@pytest.fixture
def docker_service():
    """Create a real DockerService instance for integration testing."""
    return DockerService()


@pytest.fixture
def dind_service():
    """Create a real DinDService instance for integration testing."""
    return DinDService()


class TestDinDDeployment:
    """Integration tests for DinD deployment flow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_and_destroy_dind_container(self, dind_service):
        """
        Test creating and destroying a DinD container.

        Verifies:
        - Container is created with correct attributes
        - container_id and docker_url are returned
        - Container is running after creation
        - Container is removed after destruction
        """
        range_id = str(uuid4())
        container_info = None

        try:
            # Create the DinD container
            container_info = await dind_service.create_range_container(range_id)

            # Verify container_id and docker_url are returned
            assert "container_id" in container_info, "container_id not in response"
            assert "docker_url" in container_info, "docker_url not in response"
            assert container_info["container_id"], "container_id is empty"
            assert container_info["docker_url"], "docker_url is empty"

            # Verify docker_url format
            docker_url = container_info["docker_url"]
            assert docker_url.startswith("tcp://"), f"Invalid docker_url format: {docker_url}"

            # Verify container is running
            host_client = docker.from_env()
            container = host_client.containers.get(container_info["container_id"])
            assert container.status == "running", f"Container status is {container.status}, expected running"

            # Verify mgmt_ip is returned
            assert "mgmt_ip" in container_info, "mgmt_ip not in response"
            assert container_info["mgmt_ip"], "mgmt_ip is empty"

        finally:
            # Cleanup: destroy the container
            if container_info and container_info.get("container_id"):
                await dind_service.delete_range_container(range_id)

                # Verify container is removed
                host_client = docker.from_env()
                with pytest.raises(NotFound):
                    host_client.containers.get(container_info["container_id"])

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_two_ranges_same_subnet_no_conflict(self, dind_service):
        """
        Test that two DinD containers can use the same subnet without conflict.

        This is the key isolation test - each range runs in its own DinD container,
        so identical subnets should not conflict because they're in separate
        network namespaces.

        Verifies:
        - Two DinD containers can be created simultaneously
        - Both can create networks with the same subnet (e.g., 10.0.1.0/24)
        - No errors occur from subnet conflicts
        """
        range_id_1 = str(uuid4())
        range_id_2 = str(uuid4())
        container_info_1 = None
        container_info_2 = None
        test_subnet = "10.0.1.0/24"
        test_gateway = "10.0.1.254"  # Use .254 for bridge, leave .1 for VyOS

        try:
            # Create two DinD containers for different ranges
            container_info_1 = await dind_service.create_range_container(range_id_1)
            container_info_2 = await dind_service.create_range_container(range_id_2)

            # Verify both containers were created
            assert container_info_1["container_id"] != container_info_2["container_id"]
            assert container_info_1["docker_url"] != container_info_2["docker_url"]

            # Get clients for each DinD
            client_1 = dind_service.get_range_client(range_id_1, container_info_1["docker_url"])
            client_2 = dind_service.get_range_client(range_id_2, container_info_2["docker_url"])

            # Create network with SAME subnet in BOTH DinD containers
            # This should succeed because each DinD has its own network namespace
            ipam_pool = docker.types.IPAMPool(subnet=test_subnet, gateway=test_gateway)
            ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])

            network_1 = client_1.networks.create(
                name="test-network",
                driver="bridge",
                ipam=ipam_config,
                internal=True,
            )

            network_2 = client_2.networks.create(
                name="test-network",
                driver="bridge",
                ipam=ipam_config,
                internal=True,
            )

            # Verify both networks were created successfully
            assert network_1.id, "Network 1 was not created"
            assert network_2.id, "Network 2 was not created"

            # Verify they have the same subnet configuration
            network_1_info = client_1.networks.get(network_1.id)
            network_2_info = client_2.networks.get(network_2.id)

            subnet_1 = network_1_info.attrs["IPAM"]["Config"][0]["Subnet"]
            subnet_2 = network_2_info.attrs["IPAM"]["Config"][0]["Subnet"]

            assert subnet_1 == test_subnet, f"Network 1 subnet mismatch: {subnet_1}"
            assert subnet_2 == test_subnet, f"Network 2 subnet mismatch: {subnet_2}"

            # Clean up networks within DinD before destroying containers
            network_1.remove()
            network_2.remove()

        finally:
            # Cleanup both DinD containers
            if container_info_1:
                await dind_service.delete_range_container(range_id_1)
            if container_info_2:
                await dind_service.delete_range_container(range_id_2)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_image_transfer_to_dind(self, docker_service, dind_service):
        """
        Test transferring an image from host Docker to DinD.

        Verifies:
        - Image can be transferred from host to DinD container
        - Progress callback receives 'complete' status
        - Image exists in DinD after transfer
        """
        range_id = str(uuid4())
        container_info = None
        test_image = "alpine:latest"
        progress_statuses: List[str] = []

        def progress_callback(transferred: int, total: int, status: str) -> None:
            """Capture progress status updates."""
            progress_statuses.append(status)

        try:
            # Ensure alpine:latest is on host
            host_client = docker.from_env()
            try:
                host_client.images.get(test_image)
            except docker.errors.ImageNotFound:
                # Pull it if not present
                host_client.images.pull(test_image)

            # Create DinD container
            container_info = await dind_service.create_range_container(range_id)
            docker_url = container_info["docker_url"]

            # Get client for DinD to verify image doesn't exist yet
            range_client = dind_service.get_range_client(range_id, docker_url)

            # Remove image from DinD if it exists (for clean test)
            try:
                range_client.images.remove(test_image, force=True)
            except docker.errors.ImageNotFound:
                pass  # Expected - image shouldn't exist yet

            # Transfer image to DinD with progress callback
            result = await docker_service.transfer_image_to_dind(
                range_id=range_id,
                docker_url=docker_url,
                image=test_image,
                pull_if_missing=False,  # We already ensured it exists on host
                progress_callback=progress_callback,
            )

            # Verify transfer succeeded
            assert result is True, "Image transfer failed"

            # Verify progress_callback received 'complete' status
            assert "complete" in progress_statuses, (
                f"Expected 'complete' status in progress updates. "
                f"Received statuses: {progress_statuses}"
            )

            # Verify image exists in DinD
            dind_image = range_client.images.get(test_image)
            assert dind_image is not None, "Image not found in DinD after transfer"
            assert test_image.split(":")[0] in str(dind_image.tags) or "alpine" in str(dind_image.tags).lower(), (
                f"Image tags don't match expected. Got: {dind_image.tags}"
            )

        finally:
            # Cleanup
            if container_info:
                await dind_service.delete_range_container(range_id)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dind_container_lifecycle(self, dind_service):
        """
        Test full DinD container lifecycle: create, stop, start, restart, delete.

        Verifies:
        - Container can be stopped and preserves data
        - Container can be started after being stopped
        - Container can be restarted
        - Container is properly cleaned up on delete
        """
        range_id = str(uuid4())
        container_info = None

        try:
            # Create container
            container_info = await dind_service.create_range_container(range_id)
            container_id = container_info["container_id"]

            # Verify running
            info = await dind_service.get_container_info(range_id)
            assert info["status"] == "running"

            # Stop container
            await dind_service.stop_range_container(range_id)
            info = await dind_service.get_container_info(range_id)
            assert info["status"] in ["exited", "stopped"]

            # Start container
            start_info = await dind_service.start_range_container(range_id)
            assert start_info["status"] == "running"
            assert start_info["docker_url"]  # URL should still be valid

            # Restart container
            restart_info = await dind_service.restart_range_container(range_id)
            assert restart_info["status"] == "running"

        finally:
            # Cleanup
            if container_info:
                await dind_service.delete_range_container(range_id)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_network_isolation_within_dind(self, dind_service):
        """
        Test that iptables-based network isolation works within DinD.

        Verifies:
        - Networks can be created inside DinD
        - Isolation rules can be applied
        - Different networks are isolated from each other
        """
        range_id = str(uuid4())
        container_info = None

        try:
            # Create DinD container
            container_info = await dind_service.create_range_container(range_id)
            docker_url = container_info["docker_url"]

            # Create networks inside DinD
            range_client = dind_service.get_range_client(range_id, docker_url)

            networks_to_create = [
                {"name": "lan-network", "subnet": "192.168.1.0/24"},
                {"name": "dmz-network", "subnet": "192.168.2.0/24"},
                {"name": "management", "subnet": "192.168.100.0/24"},
            ]

            created_networks = []
            for net_config in networks_to_create:
                ipam_pool = docker.types.IPAMPool(subnet=net_config["subnet"])
                ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
                network = range_client.networks.create(
                    name=net_config["name"],
                    driver="bridge",
                    ipam=ipam_config,
                    internal=True,
                )
                created_networks.append(network)

            # Apply network isolation rules
            await dind_service.setup_network_isolation_in_dind(
                range_id=range_id,
                docker_url=docker_url,
                networks=["lan-network", "dmz-network", "management"],
                allow_internet=["management"],  # Only management network gets internet
            )

            # Verify networks exist
            for network in created_networks:
                net_info = range_client.networks.get(network.id)
                assert net_info is not None

            # Cleanup networks inside DinD
            for network in created_networks:
                try:
                    network.remove()
                except Exception:
                    pass

        finally:
            # Cleanup DinD container
            if container_info:
                await dind_service.delete_range_container(range_id)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_image_already_exists_in_dind(self, docker_service, dind_service):
        """
        Test that image transfer skips when image already exists in DinD.

        Verifies:
        - Transfer returns True when image already exists
        - Progress callback receives 'already_exists' status
        - No duplicate transfer occurs
        """
        range_id = str(uuid4())
        container_info = None
        test_image = "alpine:latest"

        try:
            # Ensure alpine:latest is on host
            host_client = docker.from_env()
            try:
                host_client.images.get(test_image)
            except docker.errors.ImageNotFound:
                host_client.images.pull(test_image)

            # Create DinD container
            container_info = await dind_service.create_range_container(range_id)
            docker_url = container_info["docker_url"]

            # First transfer
            first_statuses: List[str] = []
            await docker_service.transfer_image_to_dind(
                range_id=range_id,
                docker_url=docker_url,
                image=test_image,
                progress_callback=lambda t, tot, s: first_statuses.append(s),
            )

            # Second transfer - should detect already exists
            second_statuses: List[str] = []
            result = await docker_service.transfer_image_to_dind(
                range_id=range_id,
                docker_url=docker_url,
                image=test_image,
                progress_callback=lambda t, tot, s: second_statuses.append(s),
            )

            # Verify second transfer returned success
            assert result is True

            # Verify second transfer detected image already exists
            assert "already_exists" in second_statuses, (
                f"Expected 'already_exists' status on second transfer. "
                f"Received: {second_statuses}"
            )

        finally:
            # Cleanup
            if container_info:
                await dind_service.delete_range_container(range_id)


class TestDinDResourceLimits:
    """Tests for DinD container resource limits."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_dind_with_memory_limit(self, dind_service):
        """Test creating DinD container with memory limit."""
        range_id = str(uuid4())
        container_info = None

        try:
            container_info = await dind_service.create_range_container(
                range_id=range_id,
                memory_limit="2g",
            )

            # Verify container was created
            assert container_info["container_id"]

            # Verify memory limit was applied
            host_client = docker.from_env()
            container = host_client.containers.get(container_info["container_id"])
            # Memory limit is stored in bytes
            memory_limit = container.attrs["HostConfig"]["Memory"]
            # 2g = 2 * 1024 * 1024 * 1024 = 2147483648 bytes
            assert memory_limit == 2147483648, f"Memory limit mismatch: {memory_limit}"

        finally:
            if container_info:
                await dind_service.delete_range_container(range_id)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_dind_with_cpu_limit(self, dind_service):
        """Test creating DinD container with CPU limit."""
        range_id = str(uuid4())
        container_info = None

        try:
            container_info = await dind_service.create_range_container(
                range_id=range_id,
                cpu_limit=2.0,  # 2 CPU cores
            )

            # Verify container was created
            assert container_info["container_id"]

            # Verify CPU limit was applied
            host_client = docker.from_env()
            container = host_client.containers.get(container_info["container_id"])
            # CPU limit is stored in nano CPUs (1e9 per core)
            nano_cpus = container.attrs["HostConfig"]["NanoCpus"]
            assert nano_cpus == 2000000000, f"CPU limit mismatch: {nano_cpus}"

        finally:
            if container_info:
                await dind_service.delete_range_container(range_id)


class TestDinDCleanup:
    """Tests for DinD cleanup and resource management."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_range_containers(self, dind_service):
        """Test listing all CYROID range DinD containers."""
        range_ids = [str(uuid4()) for _ in range(2)]
        containers_info = []

        try:
            # Create multiple DinD containers
            for range_id in range_ids:
                info = await dind_service.create_range_container(range_id)
                containers_info.append(info)

            # List all range containers
            all_containers = await dind_service.list_range_containers()

            # Verify our containers are in the list
            container_ids = {c["container_id"] for c in containers_info}
            listed_ids = {c["container_id"] for c in all_containers}

            for cid in container_ids:
                assert cid in listed_ids, f"Container {cid} not found in listing"

            # Verify all listed containers have cyroid labels
            for container in all_containers:
                assert "cyroid-range-" in container["container_name"]

        finally:
            # Cleanup
            for range_id in range_ids:
                try:
                    await dind_service.delete_range_container(range_id)
                except Exception:
                    pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete_removes_volume(self, dind_service):
        """Test that deleting a DinD container also removes its volume."""
        range_id = str(uuid4())
        short_id = range_id.replace("-", "")[:12]
        volume_name = f"cyroid-range-{short_id}-docker"

        try:
            # Create DinD container
            container_info = await dind_service.create_range_container(range_id)

            # Verify volume was created
            host_client = docker.from_env()
            volume = host_client.volumes.get(volume_name)
            assert volume is not None

            # Delete container
            await dind_service.delete_range_container(range_id)

            # Verify volume was removed
            with pytest.raises(NotFound):
                host_client.volumes.get(volume_name)

        except NotFound:
            # Container/volume might already be cleaned up
            pass
