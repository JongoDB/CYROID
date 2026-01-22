#!/bin/bash
# CYROID Network Initialization Script
#
# Creates the required Docker networks for CYROID infrastructure.
# Run this before starting docker-compose if networks don't exist.
#
# Networks:
#   - cyroid-mgmt (172.30.0.0/24): CYROID infrastructure services
#   - cyroid-ranges (172.30.1.0/24): Range DinD containers

set -euo pipefail

echo "=== Initializing CYROID Networks ==="

# Create management network if not exists
if ! docker network inspect cyroid-mgmt &>/dev/null; then
    echo "Creating cyroid-mgmt network..."
    docker network create \
        --driver bridge \
        --subnet 172.30.0.0/24 \
        --gateway 172.30.0.1 \
        cyroid-mgmt
    echo "Created cyroid-mgmt (172.30.0.0/24)"
else
    echo "cyroid-mgmt network already exists"
fi

# Create ranges network if not exists
if ! docker network inspect cyroid-ranges &>/dev/null; then
    echo "Creating cyroid-ranges network..."
    docker network create \
        --driver bridge \
        --subnet 172.30.1.0/24 \
        --gateway 172.30.1.1 \
        cyroid-ranges
    echo "Created cyroid-ranges (172.30.1.0/24)"
else
    echo "cyroid-ranges network already exists"
fi

echo ""
echo "=== Networks initialized ==="
docker network ls | grep cyroid
echo ""
echo "Ready to start CYROID with: docker-compose up -d"
