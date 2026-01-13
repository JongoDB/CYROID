# backend/tests/unit/test_msel_parser.py
import pytest
from cyroid.services.msel_parser import MSELParser

SAMPLE_MSEL = """# Exercise MSEL

## T+0:00 - Initial Setup
Deploy baseline artifacts to all workstations.

**Actions:**
- Place file: malware.exe on WS-01 at C:\\Users\\Public\\malware.exe
- Run command on WS-01: whoami

## T+0:30 - First Inject
Simulate phishing attack.

**Actions:**
- Place file: phishing.docx on WS-02 at C:\\Users\\victim\\Documents\\invoice.docx
"""


def test_parse_msel_extracts_injects():
    parser = MSELParser()
    injects = parser.parse(SAMPLE_MSEL)

    assert len(injects) == 2
    assert injects[0]['title'] == 'Initial Setup'
    assert injects[0]['inject_time_minutes'] == 0
    assert injects[1]['title'] == 'First Inject'
    assert injects[1]['inject_time_minutes'] == 30


def test_parse_msel_extracts_actions():
    parser = MSELParser()
    injects = parser.parse(SAMPLE_MSEL)

    assert len(injects[0]['actions']) == 2
    assert injects[0]['actions'][0]['action_type'] == 'place_file'
    assert injects[0]['actions'][1]['action_type'] == 'run_command'


def test_parse_msel_extracts_place_file_params():
    parser = MSELParser()
    injects = parser.parse(SAMPLE_MSEL)

    place_action = injects[0]['actions'][0]
    assert place_action['parameters']['filename'] == 'malware.exe'
    assert place_action['parameters']['target_vm'] == 'WS-01'
    assert 'C:\\Users\\Public\\malware.exe' in place_action['parameters']['target_path']


def test_parse_msel_extracts_run_command_params():
    parser = MSELParser()
    injects = parser.parse(SAMPLE_MSEL)

    cmd_action = injects[0]['actions'][1]
    assert cmd_action['parameters']['target_vm'] == 'WS-01'
    assert cmd_action['parameters']['command'] == 'whoami'


def test_parse_msel_with_hours():
    msel = """# Test MSEL

## T+1:30 - Hourly Inject
Test hourly timing.

**Actions:**
- Run command on VM-01: date
"""
    parser = MSELParser()
    injects = parser.parse(msel)

    assert len(injects) == 1
    assert injects[0]['inject_time_minutes'] == 90  # 1 hour + 30 minutes


def test_parse_empty_msel():
    parser = MSELParser()
    injects = parser.parse("# Just a title")

    assert len(injects) == 0
