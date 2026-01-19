# backend/tests/unit/test_vm_schema.py
"""Unit tests for VM schema validation."""
import pytest
from pydantic import ValidationError

from cyroid.schemas.vm import VMCreate


class TestVMCreateValidation:
    """Tests for VM creation schema validation."""

    def test_requires_template_or_snapshot(self):
        """Must provide exactly one of template_id or snapshot_id."""
        with pytest.raises(ValidationError) as exc_info:
            VMCreate(
                range_id="00000000-0000-0000-0000-000000000001",
                network_id="00000000-0000-0000-0000-000000000002",
                hostname="test-vm",
                ip_address="10.0.1.10",
                cpu=2,
                ram_mb=4096,
                disk_gb=40,
            )
        error_str = str(exc_info.value).lower()
        assert "template_id or snapshot_id" in error_str or "must provide" in error_str

    def test_rejects_both_template_and_snapshot(self):
        """Cannot provide both template_id and snapshot_id."""
        with pytest.raises(ValidationError) as exc_info:
            VMCreate(
                range_id="00000000-0000-0000-0000-000000000001",
                network_id="00000000-0000-0000-0000-000000000002",
                template_id="00000000-0000-0000-0000-000000000003",
                snapshot_id="00000000-0000-0000-0000-000000000004",
                hostname="test-vm",
                ip_address="10.0.1.10",
                cpu=2,
                ram_mb=4096,
                disk_gb=40,
            )
        error_str = str(exc_info.value).lower()
        assert "cannot specify both" in error_str or "both" in error_str

    def test_accepts_template_only(self):
        """Should accept template_id without snapshot_id."""
        vm = VMCreate(
            range_id="00000000-0000-0000-0000-000000000001",
            network_id="00000000-0000-0000-0000-000000000002",
            template_id="00000000-0000-0000-0000-000000000003",
            hostname="test-vm",
            ip_address="10.0.1.10",
            cpu=2,
            ram_mb=4096,
            disk_gb=40,
        )
        assert vm.template_id is not None
        assert vm.snapshot_id is None

    def test_accepts_snapshot_only(self):
        """Should accept snapshot_id without template_id."""
        vm = VMCreate(
            range_id="00000000-0000-0000-0000-000000000001",
            network_id="00000000-0000-0000-0000-000000000002",
            snapshot_id="00000000-0000-0000-0000-000000000004",
            hostname="test-vm",
            ip_address="10.0.1.10",
            cpu=2,
            ram_mb=4096,
            disk_gb=40,
        )
        assert vm.template_id is None
        assert vm.snapshot_id is not None
