#!/bin/bash
# Build custom CYROID DinD image
#
# This creates an optimized Docker-in-Docker image for running
# range containers with network isolation.
#
# After building, update .env with:
#   DIND_IMAGE=cyroid-dind:latest

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Building custom CYROID DinD image ==="

cd "$PROJECT_DIR"

docker build \
    -t cyroid-dind:latest \
    -f docker/Dockerfile.dind-base \
    docker/

echo ""
echo "=== Build complete ==="
echo "Image built: cyroid-dind:latest"
echo ""
echo "To use this image, add to your .env file:"
echo "  DIND_IMAGE=cyroid-dind:latest"
echo ""
echo "Or set the environment variable when running:"
echo "  DIND_IMAGE=cyroid-dind:latest docker-compose up -d"
