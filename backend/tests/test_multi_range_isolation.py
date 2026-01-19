#!/usr/bin/env python3
"""
Test multi-range network isolation to verify:
1. Each VyOS router gets a unique management IP
2. Blueprint offset system correctly separates private IP spaces
3. No IP conflicts when deploying multiple instances of the same blueprint
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cyroid.services.blueprint_service import apply_subnet_offset, extract_subnet_prefix


def test_subnet_offset_function():
    """Test the apply_subnet_offset function for correctness."""
    print("\n=== Testing Subnet Offset Function ===")

    test_cases = [
        # (ip_or_subnet, base_prefix, offset, expected)
        ("10.100.0.10", "10.100", 0, "10.100.0.10"),
        ("10.100.0.10", "10.100", 1, "10.101.0.10"),
        ("10.100.0.10", "10.100", 2, "10.102.0.10"),
        ("10.100.0.10", "10.100", 50, "10.150.0.10"),
        ("10.100.1.0/24", "10.100", 0, "10.100.1.0/24"),
        ("10.100.1.0/24", "10.100", 1, "10.101.1.0/24"),
        ("10.100.1.0/24", "10.100", 5, "10.105.1.0/24"),
        # Multiple networks in same range
        ("10.100.0.0/24", "10.100", 3, "10.103.0.0/24"),
        ("10.100.1.0/24", "10.100", 3, "10.103.1.0/24"),
        ("10.100.2.0/24", "10.100", 3, "10.103.2.0/24"),
        # Different base prefix
        ("10.50.0.10", "10.50", 1, "10.51.0.10"),
        ("192.168.0.10", "192.168", 1, "192.169.0.10"),
    ]

    all_passed = True
    for ip_or_subnet, base_prefix, offset, expected in test_cases:
        result = apply_subnet_offset(ip_or_subnet, base_prefix, offset)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} apply_subnet_offset('{ip_or_subnet}', '{base_prefix}', {offset})")
        print(f"      Expected: {expected}")
        print(f"      Got:      {result}")

    return all_passed


def test_extract_subnet_prefix():
    """Test the extract_subnet_prefix function."""
    print("\n=== Testing Extract Subnet Prefix ===")

    test_cases = [
        ("10.100.0.0/24", "10.100"),
        ("10.100.1.0/24", "10.100"),
        ("192.168.50.0/24", "192.168"),
        ("172.16.0.0/16", "172.16"),
    ]

    all_passed = True
    for subnet, expected in test_cases:
        result = extract_subnet_prefix(subnet)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} extract_subnet_prefix('{subnet}') = '{result}' (expected: '{expected}')")

    return all_passed


def simulate_multi_instance_deployment():
    """Simulate deploying multiple instances of a blueprint."""
    print("\n=== Simulating Multi-Instance Deployment ===")

    # Simulated blueprint config
    base_prefix = "10.100"
    networks = [
        {"name": "corporate", "subnet": "10.100.0.0/24", "gateway": "10.100.0.1"},
        {"name": "dmz", "subnet": "10.100.1.0/24", "gateway": "10.100.1.1"},
        {"name": "industrial", "subnet": "10.100.2.0/24", "gateway": "10.100.2.1"},
    ]
    vms = [
        {"hostname": "dc01", "ip": "10.100.0.10", "network": "corporate"},
        {"hostname": "web01", "ip": "10.100.1.10", "network": "dmz"},
        {"hostname": "plc01", "ip": "10.100.2.10", "network": "industrial"},
    ]

    print(f"\nBlueprint base prefix: {base_prefix}")
    print(f"Networks: {[n['name'] for n in networks]}")
    print(f"VMs: {[v['hostname'] for v in vms]}")

    # Simulate 5 instance deployments
    all_subnets = set()
    all_vm_ips = set()
    conflicts_found = False

    for instance_offset in range(5):
        print(f"\n--- Instance {instance_offset + 1} (offset={instance_offset}) ---")

        instance_subnets = []
        instance_vm_ips = []

        for net in networks:
            adjusted_subnet = apply_subnet_offset(net["subnet"], base_prefix, instance_offset)
            adjusted_gateway = apply_subnet_offset(net["gateway"], base_prefix, instance_offset)

            # Check for conflicts
            if adjusted_subnet in all_subnets:
                print(f"  ✗ CONFLICT: Subnet {adjusted_subnet} already used!")
                conflicts_found = True
            else:
                all_subnets.add(adjusted_subnet)
                instance_subnets.append(adjusted_subnet)

            print(f"  Network '{net['name']}': {adjusted_subnet} (gateway: {adjusted_gateway})")

        for vm in vms:
            adjusted_ip = apply_subnet_offset(vm["ip"], base_prefix, instance_offset)

            # Check for conflicts
            if adjusted_ip in all_vm_ips:
                print(f"  ✗ CONFLICT: VM IP {adjusted_ip} already used!")
                conflicts_found = True
            else:
                all_vm_ips.add(adjusted_ip)
                instance_vm_ips.append(adjusted_ip)

            print(f"  VM '{vm['hostname']}': {adjusted_ip}")

    print(f"\n=== Summary ===")
    print(f"Total unique subnets: {len(all_subnets)}")
    print(f"Total unique VM IPs: {len(all_vm_ips)}")
    print(f"Conflicts found: {conflicts_found}")

    return not conflicts_found


def test_management_ip_allocation():
    """Test management IP allocation logic."""
    print("\n=== Testing Management IP Allocation Logic ===")

    # Simulate the allocation logic from VyOSService.allocate_management_ip()
    import ipaddress

    management_subnet = "10.0.0.0/16"
    management_gateway = "10.0.0.1"

    # Simulate existing containers
    used_ips = set()

    def allocate_next_ip(used_ips_set):
        subnet = ipaddress.ip_network(management_subnet, strict=False)
        for host in subnet.hosts():
            ip_str = str(host)
            if ip_str == management_gateway:
                continue
            if ip_str in used_ips_set:
                continue
            return ip_str
        return None

    print(f"Management subnet: {management_subnet}")
    print(f"Gateway: {management_gateway}")
    print("\nSimulating VyOS router allocation for 10 ranges:")

    allocated_ips = []
    for i in range(10):
        ip = allocate_next_ip(used_ips)
        if ip:
            used_ips.add(ip)
            allocated_ips.append(ip)
            print(f"  Range {i+1} VyOS router: {ip}")

    # Verify they're all unique and sequential
    expected = [f"10.0.0.{i}" for i in range(2, 12)]

    print(f"\nExpected: {expected}")
    print(f"Actual:   {allocated_ips}")

    all_unique = len(allocated_ips) == len(set(allocated_ips))
    sequential = allocated_ips == expected

    print(f"\nAll IPs unique: {'✓' if all_unique else '✗'}")
    print(f"Sequential allocation: {'✓' if sequential else '✗'}")

    return all_unique and sequential


def test_edge_cases():
    """Test edge cases for the offset system."""
    print("\n=== Testing Edge Cases ===")

    all_passed = True

    # Test maximum offset
    print("\n1. Maximum offset (should work up to 155 for 10.100 base):")
    result = apply_subnet_offset("10.100.0.0/24", "10.100", 155)
    expected = "10.255.0.0/24"
    status = "✓" if result == expected else "✗"
    if result != expected:
        all_passed = False
    print(f"   {status} Offset 155: {result} (expected: {expected})")

    # Test offset that would exceed 255
    print("\n2. Offset exceeding 255 (should raise ValueError):")
    try:
        result = apply_subnet_offset("10.100.0.0/24", "10.100", 156)
        print(f"   ✗ Should have raised ValueError but got: {result}")
        all_passed = False
    except ValueError as e:
        print(f"   ✓ Correctly raised ValueError: {e}")

    # Test with different third octets (multi-network scenarios)
    print("\n3. Multiple networks with different third octets in same range:")
    base = "10.100"
    offset = 10
    networks = ["10.100.0.0/24", "10.100.1.0/24", "10.100.10.0/24", "10.100.255.0/24"]
    expected_results = ["10.110.0.0/24", "10.110.1.0/24", "10.110.10.0/24", "10.110.255.0/24"]

    for net, exp in zip(networks, expected_results):
        result = apply_subnet_offset(net, base, offset)
        status = "✓" if result == exp else "✗"
        if result != exp:
            all_passed = False
        print(f"   {status} {net} + offset {offset} = {result} (expected: {exp})")

    return all_passed


def main():
    print("=" * 60)
    print("CYROID Multi-Range Network Isolation Tests")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Subnet Offset Function", test_subnet_offset_function()))
    results.append(("Extract Subnet Prefix", test_extract_subnet_prefix()))
    results.append(("Multi-Instance Deployment Simulation", simulate_multi_instance_deployment()))
    results.append(("Management IP Allocation", test_management_ip_allocation()))
    results.append(("Edge Cases", test_edge_cases()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            all_passed = False
        print(f"  {status}: {test_name}")

    print("=" * 60)
    if all_passed:
        print("All tests passed! ✓")
        return 0
    else:
        print("Some tests failed! ✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
