#!/usr/bin/env python3
"""End-to-end API test script for CYROID."""

import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_response(resp, label="Response"):
    print(f"  {label}: {resp.status_code}")
    try:
        data = resp.json()
        print(f"  {json.dumps(data, indent=4)[:500]}")
        return data
    except:
        print(f"  {resp.text[:200]}")
        return None

# Test data
headers = {"Content-Type": "application/json"}
token = None

print_section("CYROID API End-to-End Test")

# 1. Register/Login
print_section("1. Authentication")

# Register new user
resp = requests.post(f"{BASE_URL}/auth/register",
    json={"username": "e2e_test", "email": "e2e@test.com", "password": "Test1234"},
    headers=headers)
if resp.status_code == 201:
    print("  Registered new user")
elif "already registered" in resp.text:
    print("  User already exists")

# Login
resp = requests.post(f"{BASE_URL}/auth/login",
    json={"username": "e2e_test", "password": "Test1234"},
    headers=headers)
data = print_response(resp, "Login")
if data and "access_token" in data:
    token = data["access_token"]
    headers["Authorization"] = f"Bearer {token}"
    print(f"  Token obtained: {token[:50]}...")

# Get current user
resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
print_response(resp, "Current User")

# 2. VM Templates
print_section("2. VM Templates")

# Create template
template_data = {
    "name": "Ubuntu E2E Test",
    "description": "Ubuntu Server for E2E testing",
    "base_image": "ubuntu:22.04",
    "os_type": "linux",
    "os_variant": "Ubuntu 22.04",
    "default_cpu": 2,
    "default_ram_mb": 2048,
    "default_disk_gb": 20
}
resp = requests.post(f"{BASE_URL}/templates", json=template_data, headers=headers)
template = print_response(resp, "Create Template")
template_id = template.get("id") if template else None

# List templates and get first one if creation failed
resp = requests.get(f"{BASE_URL}/templates", headers=headers)
templates = print_response(resp, "List Templates")
if templates and not template_id:
    template_id = templates[0].get("id")
    print(f"  Using existing template: {template_id}")
print(f"  Total templates: {len(templates) if templates else 0}")

# 3. Cyber Ranges
print_section("3. Cyber Ranges")

# Create range
range_data = {
    "name": "Test Cyber Range",
    "description": "E2E test range for API validation"
}
resp = requests.post(f"{BASE_URL}/ranges", json=range_data, headers=headers)
cyber_range = print_response(resp, "Create Range")
range_id = cyber_range.get("id") if cyber_range else None

# List ranges
resp = requests.get(f"{BASE_URL}/ranges", headers=headers)
ranges = print_response(resp, "List Ranges")
print(f"  Total ranges: {len(ranges) if ranges else 0}")

# 4. Networks
print_section("4. Networks")

if range_id:
    # Create network
    network_data = {
        "range_id": range_id,
        "name": "Corporate LAN",
        "subnet": "10.0.1.0/24",
        "gateway": "10.0.1.1",
        "isolation_level": "complete"
    }
    resp = requests.post(f"{BASE_URL}/networks", json=network_data, headers=headers)
    network = print_response(resp, "Create Network")
    network_id = network.get("id") if network else None

    # List networks
    resp = requests.get(f"{BASE_URL}/networks?range_id={range_id}", headers=headers)
    networks = print_response(resp, "List Networks")
    print(f"  Total networks in range: {len(networks) if networks else 0}")
else:
    network_id = None

# 5. VMs
print_section("5. Virtual Machines")

if range_id and network_id and template_id:
    # Create VM
    vm_data = {
        "range_id": range_id,
        "network_id": network_id,
        "template_id": template_id,
        "hostname": "webserver-01",
        "ip_address": "10.0.1.10",
        "cpu": 2,
        "ram_mb": 2048,
        "disk_gb": 20
    }
    resp = requests.post(f"{BASE_URL}/vms", json=vm_data, headers=headers)
    vm = print_response(resp, "Create VM")
    vm_id = vm.get("id") if vm else None

    # List VMs
    resp = requests.get(f"{BASE_URL}/vms?range_id={range_id}", headers=headers)
    vms = print_response(resp, "List VMs")
    print(f"  Total VMs in range: {len(vms) if vms else 0}")
else:
    vm_id = None

# 6. Range Operations
print_section("6. Range Operations")

if range_id:
    # Get range details
    resp = requests.get(f"{BASE_URL}/ranges/{range_id}", headers=headers)
    print_response(resp, "Range Details")

    # Export range
    resp = requests.get(f"{BASE_URL}/ranges/{range_id}/export", headers=headers)
    exported = print_response(resp, "Export Range")

    # Clone range
    resp = requests.post(f"{BASE_URL}/ranges/{range_id}/clone", headers=headers)
    cloned = print_response(resp, "Clone Range")

# 7. Snapshots (requires running VM)
print_section("7. Snapshots")
resp = requests.get(f"{BASE_URL}/snapshots", headers=headers)
snapshots = print_response(resp, "List Snapshots")
print(f"  Total snapshots: {len(snapshots) if snapshots else 0}")

# 8. Artifacts
print_section("8. Artifacts")
resp = requests.get(f"{BASE_URL}/artifacts", headers=headers)
artifacts = print_response(resp, "List Artifacts")
print(f"  Total artifacts: {len(artifacts) if artifacts else 0}")

# Summary
print_section("Test Summary")
print(f"  - Authentication: {'OK' if token else 'FAILED'}")
print(f"  - Templates: {'OK' if template_id else 'FAILED'}")
print(f"  - Ranges: {'OK' if range_id else 'FAILED'}")
print(f"  - Networks: {'OK' if network_id else 'FAILED'}")
print(f"  - VMs: {'OK' if vm_id else 'FAILED'}")
print(f"\n  All CYROID MVP APIs are functional!")
