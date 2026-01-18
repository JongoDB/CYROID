#!/bin/bash
# Usage: ./scripts/tag-release.sh v0.10.0 "Release notes here"
#
# Creates a git tag and updates the VERSION file automatically.

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <version> [message]"
    echo "Example: $0 v0.10.0 \"Added new feature X\""
    exit 1
fi

VERSION="$1"
MESSAGE="${2:-Release $VERSION}"

# Strip 'v' prefix for VERSION file
VERSION_NUM="${VERSION#v}"

# Update VERSION file
echo "$VERSION_NUM" > backend/VERSION
echo "Updated backend/VERSION to $VERSION_NUM"

# Commit VERSION file change
git add backend/VERSION
git commit -m "chore: bump version to $VERSION_NUM"

# Create annotated tag
git tag -a "$VERSION" -m "$MESSAGE"

echo ""
echo "Created tag $VERSION"
echo "To push: git push origin master && git push origin $VERSION"
