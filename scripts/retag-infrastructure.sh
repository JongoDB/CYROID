#!/bin/bash
# retag-infrastructure.sh
#
# Pulls and retags CYROID infrastructure images with cyroid- prefix.
# This allows them to be identified as platform services in the Image Cache UI.
#
# Usage: ./scripts/retag-infrastructure.sh

set -e

echo "=== CYROID Infrastructure Image Retag ==="
echo ""

# Traefik -> cyroid-proxy
echo "Pulling traefik:v2.11..."
docker pull traefik:v2.11
echo "Tagging as cyroid-proxy:latest..."
docker tag traefik:v2.11 cyroid-proxy:latest
echo ""

# Docker DinD -> cyroid-dind
echo "Pulling docker:24-dind..."
docker pull docker:24-dind
echo "Tagging as cyroid-dind:latest..."
docker tag docker:24-dind cyroid-dind:latest
echo ""

# MinIO -> cyroid-storage
echo "Pulling minio/minio:latest..."
docker pull minio/minio:latest
echo "Tagging as cyroid-storage:latest..."
docker tag minio/minio:latest cyroid-storage:latest
echo ""

echo "=== Done! Retagged images: ==="
docker images | grep -E "^cyroid-" | sort
echo ""
echo "You can now run 'docker-compose up -d' to use the new image names."
