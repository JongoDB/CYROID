#!/bin/bash
# Update VERSION file from latest git tag
# Run this after creating a tag, or set up as post-checkout/post-merge hook

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$PROJECT_ROOT/VERSION"

# Get latest tag
TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$TAG" ]; then
    echo "No git tags found, keeping VERSION as-is"
    exit 0
fi

# Strip 'v' prefix if present
VERSION="${TAG#v}"

# Update VERSION file
echo "$VERSION" > "$VERSION_FILE"
echo "Updated VERSION to $VERSION"
