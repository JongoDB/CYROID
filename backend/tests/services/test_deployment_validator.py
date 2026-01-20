"""Unit tests for the DeploymentValidator service."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from cyroid.services.deployment_validator import (
    DeploymentValidator,
    ValidationResult,
    DeploymentValidation,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_defaults(self):
        """Test ValidationResult default values."""
        result = ValidationResult(valid=True, message="Test message")
        assert result.valid is True
        assert result.message == "Test message"
        assert result.severity == "error"
        assert result.vm_id is None
        assert result.details == {}

    def test_validation_result_with_all_fields(self):
        """Test ValidationResult with all fields specified."""
        result = ValidationResult(
            valid=False,
            message="Test error",
            severity="warning",
            vm_id="vm-123",
            details={"key": "value"}
        )
        assert result.valid is False
        assert result.severity == "warning"
        assert result.vm_id == "vm-123"
        assert result.details == {"key": "value"}


class TestDeploymentValidation:
    """Tests for DeploymentValidation dataclass."""

    def test_deployment_validation_errors_property(self):
        """Test that errors property returns only error-severity failures."""
        results = [
            ValidationResult(valid=False, message="Error 1", severity="error"),
            ValidationResult(valid=True, message="Info 1", severity="info"),
            ValidationResult(valid=True, message="Warning 1", severity="warning"),
            ValidationResult(valid=False, message="Error 2", severity="error"),
        ]
        validation = DeploymentValidation(valid=False, results=results)

        errors = validation.errors
        assert len(errors) == 2
        assert all(e.severity == "error" for e in errors)

    def test_deployment_validation_warnings_property(self):
        """Test that warnings property returns only warning-severity items."""
        results = [
            ValidationResult(valid=True, message="Warning 1", severity="warning"),
            ValidationResult(valid=False, message="Error 1", severity="error"),
            ValidationResult(valid=True, message="Warning 2", severity="warning"),
        ]
        validation = DeploymentValidation(valid=False, results=results)

        warnings = validation.warnings
        assert len(warnings) == 2
        assert all(w.severity == "warning" for w in warnings)

    def test_deployment_validation_info_property(self):
        """Test that info property returns only info-severity items."""
        results = [
            ValidationResult(valid=True, message="Info 1", severity="info"),
            ValidationResult(valid=True, message="Info 2", severity="info"),
            ValidationResult(valid=False, message="Error 1", severity="error"),
        ]
        validation = DeploymentValidation(valid=False, results=results)

        info = validation.info
        assert len(info) == 2
        assert all(i.severity == "info" for i in info)


class TestDeploymentValidator:
    """Tests for DeploymentValidator service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_docker(self):
        """Create mock Docker service."""
        mock = MagicMock()
        mock.client = MagicMock()
        mock.client.info.return_value = {"DockerRootDir": "/var/lib/docker"}
        return mock

    @pytest.fixture
    def mock_range(self):
        """Create mock Range object."""
        range_obj = MagicMock()
        range_obj.id = uuid4()
        range_obj.name = "Test Range"
        return range_obj

    @pytest.fixture
    def mock_vm(self):
        """Create mock VM object."""
        vm = MagicMock()
        vm.id = uuid4()
        vm.hostname = "test-vm"
        vm.ip_address = "10.0.1.10"
        vm.disk_gb = 40
        vm.network_id = uuid4()
        vm.template_id = uuid4()
        vm.snapshot_id = None
        vm.linux_distro = None
        vm.windows_version = None
        return vm

    @pytest.fixture
    def mock_template(self):
        """Create mock VMTemplate object."""
        template = MagicMock()
        template.id = uuid4()
        template.name = "Test Template"
        template.base_image = "ubuntu:22.04"
        template.native_arch = "x86_64"
        return template

    @pytest.fixture
    def mock_network(self):
        """Create mock Network object."""
        network = MagicMock()
        network.id = uuid4()
        network.name = "Test Network"
        network.subnet = "10.0.1.0/24"
        network.gateway = "10.0.1.1"
        return network

    @pytest.mark.asyncio
    async def test_validate_range_not_found(self, mock_db, mock_docker):
        """Test validation returns error when range not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(uuid4())

        assert result.valid is False
        assert len(result.errors) == 1
        assert "Range not found" in result.errors[0].message

    @pytest.mark.asyncio
    async def test_validate_images_exist_template_found(
        self, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test image validation passes when template image exists."""
        mock_vm.network_id = mock_vm.id  # Set to same as vm id for simplicity
        mock_template.id = mock_vm.template_id

        # Configure mock to return image exists
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should have info about image being available
        info_messages = [r.message for r in result.info]
        assert any("available" in msg or "auto_download" in msg.lower() for msg in info_messages)

    @pytest.mark.asyncio
    async def test_validate_images_missing(
        self, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test image validation fails when image is missing."""
        from docker.errors import ImageNotFound

        mock_template.id = mock_vm.template_id
        mock_template.base_image = "nonexistent:image"
        mock_vm.linux_distro = None  # Not auto-downloadable
        mock_vm.windows_version = None

        # Configure mock to raise ImageNotFound
        mock_docker.client.images.get.side_effect = ImageNotFound("not found")

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should have error about missing image
        errors = [r.message for r in result.errors]
        assert any("not found" in msg for msg in errors)

    @pytest.mark.asyncio
    async def test_validate_images_auto_download(
        self, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test that auto-downloadable images don't cause errors."""
        from docker.errors import ImageNotFound

        mock_template.id = mock_vm.template_id
        mock_template.base_image = "qemus/qemu"  # Auto-downloadable
        mock_vm.linux_distro = "ubuntu"  # Indicates auto-download

        # Configure mock to raise ImageNotFound
        mock_docker.client.images.get.side_effect = ImageNotFound("not found")

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should NOT have error since it's auto-downloadable
        errors = [r.message for r in result.errors]
        assert not any("not found" in msg for msg in errors)

    @pytest.mark.asyncio
    @patch('cyroid.services.deployment_validator.requires_emulation')
    @patch('cyroid.services.deployment_validator.HOST_ARCH', 'arm64')
    async def test_validate_architecture_emulation_warning(
        self, mock_requires_emulation, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test architecture validation warns about emulation."""
        mock_requires_emulation.return_value = True
        mock_template.id = mock_vm.template_id
        mock_template.native_arch = "x86_64"

        # Configure mock to return image exists
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should have warning about emulation
        warnings = [r.message for r in result.warnings]
        assert any("emulation" in msg.lower() for msg in warnings)

    @pytest.mark.asyncio
    @patch('shutil.disk_usage')
    async def test_validate_disk_space_sufficient(
        self, mock_disk_usage, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test disk space validation passes with sufficient space."""
        # 100 GB free, 200 GB total
        mock_disk_usage.return_value = MagicMock(
            free=100 * 1024 ** 3,
            total=200 * 1024 ** 3
        )
        mock_template.id = mock_vm.template_id
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should not have disk space error
        errors = [r.message for r in result.errors]
        assert not any("disk space" in msg.lower() for msg in errors)

    @pytest.mark.asyncio
    @patch('shutil.disk_usage')
    async def test_validate_disk_space_insufficient(
        self, mock_disk_usage, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test disk space validation fails with insufficient space."""
        # Only 5 GB free (less than minimum 10 GB)
        mock_disk_usage.return_value = MagicMock(
            free=5 * 1024 ** 3,
            total=100 * 1024 ** 3
        )
        mock_vm.disk_gb = 100  # VM needs 100 GB
        mock_template.id = mock_vm.template_id
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should have disk space error
        errors = [r.message for r in result.errors]
        assert any("disk space" in msg.lower() or "insufficient" in msg.lower() for msg in errors)

    @pytest.mark.asyncio
    async def test_validate_network_duplicate_ips(
        self, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test network validation detects duplicate IPs."""
        # Create two VMs with same IP
        vm1 = MagicMock()
        vm1.id = uuid4()
        vm1.hostname = "vm1"
        vm1.ip_address = "10.0.1.10"
        vm1.disk_gb = 40
        vm1.network_id = uuid4()
        vm1.template_id = mock_template.id
        vm1.snapshot_id = None
        vm1.linux_distro = None
        vm1.windows_version = None

        vm2 = MagicMock()
        vm2.id = uuid4()
        vm2.hostname = "vm2"
        vm2.ip_address = "10.0.1.10"  # Same IP as vm1
        vm2.disk_gb = 40
        vm2.network_id = vm1.network_id  # Same network
        vm2.template_id = mock_template.id
        vm2.snapshot_id = None
        vm2.linux_distro = None
        vm2.windows_version = None

        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [vm1, vm2]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = vm1.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should have error about duplicate IP
        errors = [r.message for r in result.errors]
        assert any("duplicate" in msg.lower() for msg in errors)

    @pytest.mark.asyncio
    async def test_validate_network_ip_outside_subnet(
        self, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test network validation detects IP outside subnet."""
        mock_vm.ip_address = "192.168.1.10"  # Outside 10.0.1.0/24
        mock_template.id = mock_vm.template_id
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should have error about IP outside subnet
        errors = [r.message for r in result.errors]
        assert any("outside" in msg.lower() for msg in errors)

    @pytest.mark.asyncio
    async def test_validate_network_valid_configuration(
        self, mock_db, mock_docker, mock_range, mock_vm, mock_template
    ):
        """Test network validation passes with valid configuration."""
        mock_vm.ip_address = "10.0.1.50"  # Valid IP in subnet
        mock_template.id = mock_vm.template_id
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [mock_vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = mock_vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = mock_template
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should not have network-related errors
        errors = [r.message for r in result.errors]
        assert not any("duplicate" in msg.lower() or "outside" in msg.lower() for msg in errors)

    @pytest.mark.asyncio
    async def test_validate_empty_range(self, mock_db, mock_docker, mock_range):
        """Test validation handles ranges with no VMs."""
        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries to return empty lists
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = []
            elif "Network" in str(model):
                query_mock.filter.return_value.all.return_value = []
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should be valid with info messages
        assert result.valid is True
        info_messages = [r.message for r in result.info]
        assert any("no vm" in msg.lower() for msg in info_messages)

    @pytest.mark.asyncio
    async def test_validate_snapshot_based_vm(self, mock_db, mock_docker, mock_range):
        """Test validation works for snapshot-based VMs."""
        # Create snapshot-based VM
        vm = MagicMock()
        vm.id = uuid4()
        vm.hostname = "snapshot-vm"
        vm.ip_address = "10.0.1.20"
        vm.disk_gb = 40
        vm.network_id = uuid4()
        vm.template_id = None
        vm.snapshot_id = uuid4()
        vm.linux_distro = None
        vm.windows_version = None

        snapshot = MagicMock()
        snapshot.id = vm.snapshot_id
        snapshot.name = "Test Snapshot"
        snapshot.docker_image_tag = "cyroid-snapshot:test-v1"
        snapshot.docker_image_id = "sha256:abc123"

        mock_docker.client.images.get.return_value = MagicMock()

        # Setup db queries
        def mock_query(model):
            query_mock = MagicMock()
            if "Range" in str(model):
                query_mock.filter.return_value.first.return_value = mock_range
            elif "VM" in str(model):
                query_mock.filter.return_value.all.return_value = [vm]
            elif "Network" in str(model):
                mock_net = MagicMock()
                mock_net.id = vm.network_id
                mock_net.name = "test-net"
                mock_net.subnet = "10.0.1.0/24"
                query_mock.filter.return_value.all.return_value = [mock_net]
            elif "Snapshot" in str(model):
                query_mock.filter.return_value.first.return_value = snapshot
            elif "VMTemplate" in str(model):
                query_mock.filter.return_value.first.return_value = None
            return query_mock

        mock_db.query.side_effect = mock_query

        validator = DeploymentValidator(mock_db, mock_docker)
        result = await validator.validate_range(mock_range.id)

        # Should succeed with snapshot-based VM
        info_messages = [r.message for r in result.info]
        assert any("available" in msg for msg in info_messages)
