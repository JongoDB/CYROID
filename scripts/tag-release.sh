#!/bin/bash
# Create a release tag and update VERSION file
# Usage: ./scripts/tag-release.sh 0.25.3

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.25.3"
    exit 1
fi

VERSION="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$PROJECT_ROOT/VERSION"

# Update VERSION file
echo "$VERSION" > "$VERSION_FILE"
echo "Updated VERSION to $VERSION"

# Commit the version change
git add VERSION
git commit -m "chore: bump version to $VERSION" || echo "No changes to commit"

# Create and push tag
git tag "v$VERSION"
git push origin master
git push origin "v$VERSION"

echo ""
echo "Released v$VERSION"
echo "- VERSION file updated"  
echo "- Tag v$VERSION created and pushed"
