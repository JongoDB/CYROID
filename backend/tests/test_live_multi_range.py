#!/usr/bin/env python3
"""
Live integration test for multi-range network isolation.
This test creates actual ranges and verifies VyOS routers and networks
are correctly isolated with different IP addresses.

Run this against a running CYROID instance.
"""
import requests
import time
import sys
import os

# Configuration
API_BASE = os.environ.get("CYROID_API_URL", "http://localhost:8000/api/v1")
USERNAME = os.environ.get("CYROID_USERNAME", "admin")
PASSWORD = os.environ.get("CYROID_PASSWORD", "admin")


def get_token():
    """Authenticate and get JWT token."""
    print("Authenticating...")
    resp = requests.post(
        f"{API_BASE}/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code} - {resp.text}")
        sys.exit(1)

    token = resp.json().get("access_token")
    print(f"  ✓ Authenticated as {USERNAME}")
    return token


def headers(token):
    """Build headers with auth token."""
    return {"Authorization": f"Bearer {token}"}


def create_test_range(token, name, subnet_base):
    """Create a test range with networks."""
    print(f"\nCreating range: {name}")

    # Create range
    resp = requests.post(
        f"{API_BASE}/ranges",
        headers=headers(token),
        json={
            "name": name,
            "description": f"Test range for multi-instance isolation testing"
        }
    )
    if resp.status_code not in [200, 201]:
        print(f"  ✗ Failed to create range: {resp.status_code} - {resp.text}")
        return None

    range_data = resp.json()
    range_id = range_data["id"]
    print(f"  ✓ Created range: {range_id}")

    # Create networks
    networks = [
        {"name": "corporate", "subnet": f"{subnet_base}.0.0/24", "gateway": f"{subnet_base}.0.1"},
        {"name": "dmz", "subnet": f"{subnet_base}.1.0/24", "gateway": f"{subnet_base}.1.1"},
    ]

    for net in networks:
        resp = requests.post(
            f"{API_BASE}/ranges/{range_id}/networks",
            headers=headers(token),
            json={
                "name": net["name"],
                "subnet": net["subnet"],
                "gateway": net["gateway"],
                "is_isolated": False
            }
        )
        if resp.status_code not in [200, 201]:
            print(f"  ✗ Failed to create network {net['name']}: {resp.status_code} - {resp.text}")
        else:
            print(f"  ✓ Created network: {net['name']} ({net['subnet']})")

    return range_id


def create_blueprint_from_range(token, range_id, name, subnet_prefix):
    """Create a blueprint from a range."""
    print(f"\nCreating blueprint: {name}")

    resp = requests.post(
        f"{API_BASE}/blueprints",
        headers=headers(token),
        json={
            "name": name,
            "description": "Test blueprint for multi-instance isolation",
            "range_id": range_id,
            "base_subnet_prefix": subnet_prefix
        }
    )
    if resp.status_code not in [200, 201]:
        print(f"  ✗ Failed to create blueprint: {resp.status_code} - {resp.text}")
        return None

    blueprint_data = resp.json()
    blueprint_id = blueprint_data["id"]
    print(f"  ✓ Created blueprint: {blueprint_id}")
    print(f"      Base subnet prefix: {blueprint_data.get('base_subnet_prefix')}")
    print(f"      Next offset: {blueprint_data.get('next_offset')}")

    return blueprint_id


def deploy_blueprint_instance(token, blueprint_id, instance_name, auto_deploy=False):
    """Deploy an instance of a blueprint."""
    print(f"\nDeploying instance: {instance_name}")

    resp = requests.post(
        f"{API_BASE}/blueprints/{blueprint_id}/deploy",
        headers=headers(token),
        json={
            "name": instance_name,
            "auto_deploy": auto_deploy
        }
    )
    if resp.status_code not in [200, 201]:
        print(f"  ✗ Failed to deploy instance: {resp.status_code} - {resp.text}")
        return None

    instance_data = resp.json()
    instance_id = instance_data["id"]
    range_id = instance_data["range_id"]
    offset = instance_data["subnet_offset"]

    print(f"  ✓ Deployed instance: {instance_id}")
    print(f"      Range ID: {range_id}")
    print(f"      Subnet offset: {offset}")

    return {
        "instance_id": instance_id,
        "range_id": range_id,
        "offset": offset
    }


def get_range_networks(token, range_id):
    """Get networks for a range."""
    resp = requests.get(
        f"{API_BASE}/ranges/{range_id}/networks",
        headers=headers(token)
    )
    if resp.status_code != 200:
        print(f"  ✗ Failed to get networks: {resp.status_code}")
        return []

    return resp.json()


def get_blueprint(token, blueprint_id):
    """Get blueprint details."""
    resp = requests.get(
        f"{API_BASE}/blueprints/{blueprint_id}",
        headers=headers(token)
    )
    if resp.status_code != 200:
        print(f"  ✗ Failed to get blueprint: {resp.status_code}")
        return None

    return resp.json()


def delete_range(token, range_id):
    """Delete a range."""
    resp = requests.delete(
        f"{API_BASE}/ranges/{range_id}",
        headers=headers(token)
    )
    return resp.status_code in [200, 204]


def delete_blueprint(token, blueprint_id):
    """Delete a blueprint."""
    resp = requests.delete(
        f"{API_BASE}/blueprints/{blueprint_id}",
        headers=headers(token)
    )
    return resp.status_code in [200, 204]


def main():
    print("=" * 60)
    print("CYROID Live Multi-Range Isolation Test")
    print("=" * 60)
    print(f"API: {API_BASE}")

    # Authenticate
    token = get_token()

    # Track created resources for cleanup
    created_ranges = []
    created_blueprints = []

    try:
        # Step 1: Create a source range
        source_range_id = create_test_range(token, "isolation-test-source", "10.100")
        if not source_range_id:
            print("\n✗ Failed to create source range")
            return 1
        created_ranges.append(source_range_id)

        # Step 2: Create a blueprint from the range
        blueprint_id = create_blueprint_from_range(
            token, source_range_id, "isolation-test-blueprint", "10.100"
        )
        if not blueprint_id:
            print("\n✗ Failed to create blueprint")
            return 1
        created_blueprints.append(blueprint_id)

        # Step 3: Deploy multiple instances (without actually deploying VMs)
        instances = []
        for i in range(3):
            instance = deploy_blueprint_instance(
                token, blueprint_id, f"isolation-test-instance-{i+1}", auto_deploy=False
            )
            if instance:
                instances.append(instance)
                created_ranges.append(instance["range_id"])

        if len(instances) < 3:
            print(f"\n✗ Only created {len(instances)} instances, expected 3")
            return 1

        # Step 4: Verify subnet offsets are correct
        print("\n" + "=" * 60)
        print("Verification Results")
        print("=" * 60)

        # Check blueprint next_offset
        blueprint = get_blueprint(token, blueprint_id)
        expected_next_offset = 3  # After deploying 3 instances
        actual_next_offset = blueprint.get("next_offset", 0)

        print(f"\nBlueprint next_offset:")
        print(f"  Expected: {expected_next_offset}")
        print(f"  Actual: {actual_next_offset}")
        print(f"  {'✓ PASS' if actual_next_offset == expected_next_offset else '✗ FAIL'}")

        # Verify each instance has correct offset
        print(f"\nInstance subnet offsets:")
        all_offsets_correct = True
        for i, inst in enumerate(instances):
            expected_offset = i
            actual_offset = inst["offset"]
            match = expected_offset == actual_offset
            if not match:
                all_offsets_correct = False
            print(f"  Instance {i+1}: offset={actual_offset} (expected {expected_offset}) {'✓' if match else '✗'}")

        # Verify networks have correct subnets
        print(f"\nNetwork subnets per instance:")
        all_subnets = set()
        subnet_conflicts = False

        for i, inst in enumerate(instances):
            networks = get_range_networks(token, inst["range_id"])
            expected_second_octet = 100 + inst["offset"]

            print(f"\n  Instance {i+1} (offset={inst['offset']}):")
            for net in networks:
                subnet = net.get("subnet", "unknown")
                gateway = net.get("gateway", "unknown")

                # Check for duplicates
                if subnet in all_subnets:
                    print(f"    ✗ CONFLICT: {net['name']}: {subnet} (already used!)")
                    subnet_conflicts = True
                else:
                    all_subnets.add(subnet)

                # Check second octet is correct
                parts = subnet.split(".")
                if len(parts) >= 2:
                    actual_second_octet = int(parts[1])
                    if actual_second_octet == expected_second_octet:
                        print(f"    ✓ {net['name']}: {subnet} (gateway: {gateway})")
                    else:
                        print(f"    ✗ {net['name']}: {subnet} - expected 10.{expected_second_octet}.x.x")
                        all_offsets_correct = False

        # Final summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        tests_passed = all([
            actual_next_offset == expected_next_offset,
            all_offsets_correct,
            not subnet_conflicts,
            len(all_subnets) == len(instances) * 2  # 2 networks per instance
        ])

        print(f"  Blueprint offset tracking: {'✓' if actual_next_offset == expected_next_offset else '✗'}")
        print(f"  Instance offsets correct: {'✓' if all_offsets_correct else '✗'}")
        print(f"  No subnet conflicts: {'✓' if not subnet_conflicts else '✗'}")
        print(f"  Unique subnets: {len(all_subnets)} (expected {len(instances) * 2})")
        print("=" * 60)

        if tests_passed:
            print("All tests passed! ✓")
        else:
            print("Some tests failed! ✗")

        return 0 if tests_passed else 1

    finally:
        # Cleanup
        print("\n" + "=" * 60)
        print("Cleanup")
        print("=" * 60)

        # Delete blueprints first (they reference ranges)
        for bp_id in created_blueprints:
            # First delete instances
            resp = requests.get(
                f"{API_BASE}/blueprints/{bp_id}/instances",
                headers=headers(token)
            )
            if resp.status_code == 200:
                for inst in resp.json():
                    # Delete the instance's range
                    if delete_range(token, inst["range_id"]):
                        print(f"  ✓ Deleted instance range: {inst['range_id'][:8]}...")

            # Now delete blueprint
            if delete_blueprint(token, bp_id):
                print(f"  ✓ Deleted blueprint: {bp_id[:8]}...")

        # Delete remaining ranges
        for range_id in created_ranges:
            if delete_range(token, range_id):
                print(f"  ✓ Deleted range: {range_id[:8]}...")


if __name__ == "__main__":
    sys.exit(main())
