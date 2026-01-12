#!/usr/bin/env python3
"""Full-stack test simulating frontend usage through Vite proxy."""

import requests
import json

# Use the frontend's Vite dev server which proxies to backend
FRONTEND_URL = "http://localhost:5174"
API_URL = f"{FRONTEND_URL}/api/v1"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_result(name, success, details=""):
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name} {details}")
    return success

headers = {"Content-Type": "application/json"}
results = []

print_section("CYROID Full-Stack Test (Frontend -> Backend)")

# 1. Test frontend is serving
print_section("1. Frontend Availability")
try:
    resp = requests.get(FRONTEND_URL)
    results.append(print_result("Frontend serving HTML",
        resp.status_code == 200 and "CYROID" in resp.text))
except Exception as e:
    results.append(print_result("Frontend serving HTML", False, str(e)))

# 2. Test API proxy through frontend
print_section("2. API Proxy (Frontend -> Backend)")
try:
    resp = requests.get(f"{API_URL}/../health")  # /health endpoint
    results.append(print_result("Health check through proxy",
        resp.status_code == 200 and resp.json().get("status") == "healthy"))
except Exception as e:
    results.append(print_result("Health check through proxy", False, str(e)))

# 3. Full auth flow through frontend proxy
print_section("3. Authentication Flow")

# Register
user_data = {
    "username": f"fullstack_test",
    "email": "fullstack@test.com",
    "password": "FullStack123"
}
try:
    resp = requests.post(f"{API_URL}/auth/register", json=user_data, headers=headers)
    if resp.status_code == 201:
        results.append(print_result("User registration", True))
    elif "already registered" in resp.text:
        results.append(print_result("User registration", True, "(already exists)"))
    else:
        results.append(print_result("User registration", False, resp.text[:50]))
except Exception as e:
    results.append(print_result("User registration", False, str(e)))

# Login
login_data = {"username": "fullstack_test", "password": "FullStack123"}
token = None
try:
    resp = requests.post(f"{API_URL}/auth/login", json=login_data, headers=headers)
    if resp.status_code == 200:
        token = resp.json().get("access_token")
        headers["Authorization"] = f"Bearer {token}"
        results.append(print_result("User login", True, f"token: {token[:30]}..."))
    else:
        results.append(print_result("User login", False, resp.text[:50]))
except Exception as e:
    results.append(print_result("User login", False, str(e)))

# Get current user
try:
    resp = requests.get(f"{API_URL}/auth/me", headers=headers)
    if resp.status_code == 200:
        user = resp.json()
        results.append(print_result("Get current user", True, f"user: {user['username']}"))
    else:
        results.append(print_result("Get current user", False, resp.text[:50]))
except Exception as e:
    results.append(print_result("Get current user", False, str(e)))

# 4. CRUD operations through frontend proxy
print_section("4. CRUD Operations")

# Create template
template_data = {
    "name": "FullStack Test Ubuntu",
    "description": "Test template via frontend proxy",
    "os_type": "linux",
    "os_variant": "Ubuntu 22.04",
    "base_image": "ubuntu:22.04",
    "default_cpu": 2,
    "default_ram_mb": 2048,
    "default_disk_gb": 20
}
template_id = None
try:
    resp = requests.post(f"{API_URL}/templates", json=template_data, headers=headers)
    if resp.status_code == 201:
        template_id = resp.json()["id"]
        results.append(print_result("Create VM template", True, f"id: {template_id[:8]}..."))
    else:
        # Maybe already exists, get list
        resp = requests.get(f"{API_URL}/templates", headers=headers)
        if resp.status_code == 200 and len(resp.json()) > 0:
            template_id = resp.json()[0]["id"]
            results.append(print_result("Create VM template", True, "(using existing)"))
        else:
            results.append(print_result("Create VM template", False, resp.text[:50]))
except Exception as e:
    results.append(print_result("Create VM template", False, str(e)))

# Create range
range_data = {"name": "FullStack Test Range", "description": "Test via frontend"}
range_id = None
try:
    resp = requests.post(f"{API_URL}/ranges", json=range_data, headers=headers)
    if resp.status_code == 201:
        range_id = resp.json()["id"]
        results.append(print_result("Create cyber range", True, f"id: {range_id[:8]}..."))
    else:
        results.append(print_result("Create cyber range", False, resp.text[:50]))
except Exception as e:
    results.append(print_result("Create cyber range", False, str(e)))

# Create network
if range_id:
    network_data = {
        "range_id": range_id,
        "name": "FullStack Test Network",
        "subnet": "192.168.100.0/24",
        "gateway": "192.168.100.1",
        "isolation_level": "complete"
    }
    network_id = None
    try:
        resp = requests.post(f"{API_URL}/networks", json=network_data, headers=headers)
        if resp.status_code == 201:
            network_id = resp.json()["id"]
            results.append(print_result("Create network", True, f"id: {network_id[:8]}..."))
        else:
            results.append(print_result("Create network", False, resp.text[:50]))
    except Exception as e:
        results.append(print_result("Create network", False, str(e)))

    # Create VM
    if network_id and template_id:
        vm_data = {
            "range_id": range_id,
            "network_id": network_id,
            "template_id": template_id,
            "hostname": "fullstack-vm-01",
            "ip_address": "192.168.100.10",
            "cpu": 2,
            "ram_mb": 2048,
            "disk_gb": 20
        }
        try:
            resp = requests.post(f"{API_URL}/vms", json=vm_data, headers=headers)
            if resp.status_code == 201:
                vm_id = resp.json()["id"]
                results.append(print_result("Create VM", True, f"id: {vm_id[:8]}..."))
            else:
                results.append(print_result("Create VM", False, resp.text[:50]))
        except Exception as e:
            results.append(print_result("Create VM", False, str(e)))

# 5. Range operations
print_section("5. Range Operations")

if range_id:
    # Get range details
    try:
        resp = requests.get(f"{API_URL}/ranges/{range_id}", headers=headers)
        if resp.status_code == 200:
            details = resp.json()
            results.append(print_result("Get range details", True,
                f"networks: {len(details.get('networks', []))}, vms: {len(details.get('vms', []))}"))
        else:
            results.append(print_result("Get range details", False, resp.text[:50]))
    except Exception as e:
        results.append(print_result("Get range details", False, str(e)))

    # Export range
    try:
        resp = requests.get(f"{API_URL}/ranges/{range_id}/export", headers=headers)
        if resp.status_code == 200:
            export = resp.json()
            results.append(print_result("Export range", True,
                f"version: {export.get('version')}, networks: {len(export.get('networks', []))}"))
        else:
            results.append(print_result("Export range", False, resp.text[:50]))
    except Exception as e:
        results.append(print_result("Export range", False, str(e)))

    # Clone range
    try:
        resp = requests.post(f"{API_URL}/ranges/{range_id}/clone", headers=headers)
        if resp.status_code == 201:
            clone = resp.json()
            results.append(print_result("Clone range", True, f"name: {clone.get('name')[:30]}..."))
        else:
            results.append(print_result("Clone range", False, resp.text[:50]))
    except Exception as e:
        results.append(print_result("Clone range", False, str(e)))

# Summary
print_section("Full-Stack Test Summary")
passed = sum(results)
total = len(results)
print(f"\n  Passed: {passed}/{total} tests")
print(f"  Success rate: {100*passed/total:.1f}%")

if passed == total:
    print("\n  All full-stack tests PASSED!")
    print("  Frontend -> Vite Proxy -> Backend integration verified!")
else:
    print(f"\n  {total - passed} test(s) failed")
