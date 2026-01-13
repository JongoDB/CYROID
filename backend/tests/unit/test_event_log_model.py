# backend/tests/unit/test_event_log_model.py
import pytest
from uuid import uuid4
from cyroid.models.event_log import EventLog, EventType


def test_event_log_creation():
    event = EventLog(
        range_id=uuid4(),
        event_type=EventType.VM_STARTED,
        message="VM ubuntu-01 started"
    )
    assert event.event_type == EventType.VM_STARTED
    assert "ubuntu-01" in event.message


def test_event_type_enum():
    assert EventType.VM_STARTED.value == "vm_started"
    assert EventType.RANGE_DEPLOYED.value == "range_deployed"
    assert EventType.INJECT_EXECUTED.value == "inject_executed"
