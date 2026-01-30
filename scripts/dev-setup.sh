#!/bin/bash
# CYROID Development Environment Setup
#
# Run this script when setting up a new development environment or worktree.
# It ensures all required local files exist that aren't tracked in git.
#
# Usage:
#   ./scripts/dev-setup.sh
#
# What it does:
#   1. Generates self-signed SSL certs for localhost (if missing)
#   2. Creates docker-compose.override.yml for macOS (if on macOS and missing)
#   3. Creates required data directories

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo -e "${BLUE}=== CYROID Development Setup ===${NC}"
echo ""

# -----------------------------------------------------------------------------
# 1. Generate SSL certificates for localhost
# -----------------------------------------------------------------------------
CERTS_DIR="$PROJECT_ROOT/certs"

if [ -f "$CERTS_DIR/cert.pem" ] && [ -f "$CERTS_DIR/key.pem" ]; then
    echo -e "${GREEN}✓${NC} SSL certificates exist"
else
    echo -e "${YELLOW}→${NC} Generating SSL certificates for localhost..."
    mkdir -p "$CERTS_DIR"

    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$CERTS_DIR/key.pem" \
        -out "$CERTS_DIR/cert.pem" \
        -subj "/CN=localhost/O=CYROID/OU=Development" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
        -addext "keyUsage=digitalSignature,keyEncipherment" \
        -addext "extendedKeyUsage=serverAuth" \
        2>/dev/null

    chmod 644 "$CERTS_DIR/cert.pem"
    chmod 600 "$CERTS_DIR/key.pem"

    echo -e "${GREEN}✓${NC} SSL certificates generated"
fi

# -----------------------------------------------------------------------------
# 2. Set up macOS docker-compose override (if on macOS)
# -----------------------------------------------------------------------------
if [[ "$(uname)" == "Darwin" ]]; then
    if [ -f "$PROJECT_ROOT/docker-compose.override.yml" ]; then
        echo -e "${GREEN}✓${NC} docker-compose.override.yml exists"
    elif [ -f "$PROJECT_ROOT/docker-compose.override.macos.yml" ]; then
        echo -e "${YELLOW}→${NC} Copying macOS docker-compose override..."
        cp "$PROJECT_ROOT/docker-compose.override.macos.yml" "$PROJECT_ROOT/docker-compose.override.yml"
        echo -e "${GREEN}✓${NC} docker-compose.override.yml created from macOS template"
    else
        echo -e "${YELLOW}!${NC} No docker-compose.override.macos.yml template found"
    fi
fi

# -----------------------------------------------------------------------------
# 3. Create required data directories
# -----------------------------------------------------------------------------
DATA_DIRS=(
    "data/cyroid/iso-cache"
    "data/cyroid/template-storage"
    "data/cyroid/vm-storage"
    "data/cyroid/shared"
    "data/cyroid/catalogs"
    "data/cyroid/scenarios"
    "data/cyroid/images"
)

echo -e "${YELLOW}→${NC} Ensuring data directories exist..."
for dir in "${DATA_DIRS[@]}"; do
    mkdir -p "$PROJECT_ROOT/$dir"
done
echo -e "${GREEN}✓${NC} Data directories ready"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "You can now start the development environment with:"
echo ""
if [[ "$(uname)" == "Darwin" ]]; then
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.yml up -d --build"
else
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build"
fi
echo ""
echo "Access the application at: https://localhost"
echo "(You'll see a browser warning for the self-signed certificate - this is expected)"
echo ""
