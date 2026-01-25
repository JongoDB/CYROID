#!/bin/bash
# CYROID Self-Signed Certificate Generator
#
# Generates a self-signed certificate for HTTPS access when not using
# Let's Encrypt (e.g., for IP-only deployments or internal use).
#
# Usage:
#   ./scripts/generate-certs.sh                    # Interactive
#   ./scripts/generate-certs.sh example.com        # Domain
#   ./scripts/generate-certs.sh 192.168.1.100      # IP address
#
# Output:
#   ./certs/cert.pem  - Certificate
#   ./certs/key.pem   - Private key

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="$PROJECT_ROOT/certs"

echo -e "${GREEN}=== CYROID Certificate Generator ===${NC}"
echo ""

# Get hostname/IP from argument or prompt
if [ $# -ge 1 ]; then
    HOSTNAME="$1"
else
    echo -e "${YELLOW}Enter the hostname or IP address for the certificate:${NC}"
    read -p "> " HOSTNAME
fi

# Validate input
if [ -z "$HOSTNAME" ]; then
    echo -e "${RED}Error: Hostname/IP cannot be empty${NC}"
    exit 1
fi

# Create certs directory
mkdir -p "$CERTS_DIR"

# Check if certificates already exist
if [ -f "$CERTS_DIR/cert.pem" ] && [ -f "$CERTS_DIR/key.pem" ]; then
    echo -e "${YELLOW}Existing certificates found in $CERTS_DIR${NC}"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
fi

echo ""
echo "Generating self-signed certificate for: $HOSTNAME"
echo ""

# Determine if input is an IP address or domain
if [[ "$HOSTNAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # IP address
    SAN="IP:$HOSTNAME"
    CN="$HOSTNAME"
else
    # Domain name
    SAN="DNS:$HOSTNAME,DNS:*.$HOSTNAME"
    CN="$HOSTNAME"
fi

# Generate certificate with proper SAN extension
openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$CERTS_DIR/key.pem" \
    -out "$CERTS_DIR/cert.pem" \
    -subj "/CN=$CN/O=CYROID/OU=Cyber Range" \
    -addext "subjectAltName=$SAN" \
    -addext "keyUsage=digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" \
    2>/dev/null

# Set permissions
chmod 644 "$CERTS_DIR/cert.pem"
chmod 600 "$CERTS_DIR/key.pem"

echo -e "${GREEN}Certificate generated successfully!${NC}"
echo ""
echo "Files created:"
echo "  - $CERTS_DIR/cert.pem (certificate)"
echo "  - $CERTS_DIR/key.pem (private key)"
echo ""
echo "Certificate details:"
openssl x509 -in "$CERTS_DIR/cert.pem" -noout -subject -dates 2>/dev/null | sed 's/^/  /'
echo ""
echo -e "${YELLOW}Note: This is a self-signed certificate. Browsers will show a security warning.${NC}"
echo "Users can bypass the warning or install the certificate to trust it."
