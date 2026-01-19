#!/bin/bash
# scripts/tag-release.sh
# Automates version tagging: updates VERSION file, commits, tags, and pushes
#
# Usage:
#   ./scripts/tag-release.sh 0.9.12              # Tag specific version
#   ./scripts/tag-release.sh patch               # Auto-increment patch (0.9.11 -> 0.9.12)
#   ./scripts/tag-release.sh minor               # Auto-increment minor (0.9.11 -> 0.10.0)
#   ./scripts/tag-release.sh major               # Auto-increment major (0.9.11 -> 1.0.0)
#   ./scripts/tag-release.sh 0.9.12 "message"    # With custom message

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$PROJECT_ROOT/backend/VERSION"

usage() {
    echo "Usage: $0 <version|patch|minor|major> [message]"
    echo ""
    echo "Examples:"
    echo "  $0 0.9.12                    # Tag specific version"
    echo "  $0 patch                     # Auto-increment patch version"
    echo "  $0 minor                     # Auto-increment minor version"
    echo "  $0 major                     # Auto-increment major version"
    echo "  $0 0.9.12 \"feat: feature\"   # With custom message"
    exit 1
}

get_current_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        cat "$VERSION_FILE"
    else
        echo "0.0.0"
    fi
}

increment_version() {
    local version="$1"
    local part="$2"
    IFS='.' read -r major minor patch <<< "$version"

    case "$part" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
    esac

    echo "$major.$minor.$patch"
}

[[ $# -lt 1 ]] && usage

VERSION="$1"
MESSAGE="${2:-}"

# Handle auto-increment
CURRENT_VERSION=$(get_current_version)
case "$VERSION" in
    patch|minor|major)
        VERSION=$(increment_version "$CURRENT_VERSION" "$VERSION")
        echo -e "${YELLOW}Auto-incrementing from $CURRENT_VERSION to $VERSION${NC}"
        ;;
esac

# Strip 'v' prefix if provided
VERSION="${VERSION#v}"

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid version format. Use x.y.z (e.g., 0.9.12)${NC}"
    exit 1
fi

# Check if tag exists
if git tag -l "v$VERSION" | grep -q "v$VERSION"; then
    echo -e "${RED}Error: Tag v$VERSION already exists${NC}"
    exit 1
fi

# Default message
[[ -z "$MESSAGE" ]] && MESSAGE="Release v$VERSION"

echo -e "${GREEN}Releasing version $VERSION${NC}"
echo "  Current: $CURRENT_VERSION"
echo "  New:     $VERSION"
echo "  Message: $MESSAGE"
echo ""

read -p "Continue? [y/N] " -n 1 -r
echo
[[ ! $REPLY =~ ^[Yy]$ ]] && { echo "Aborted."; exit 1; }

# Update VERSION file
echo "$VERSION" > "$VERSION_FILE"
echo -e "${GREEN}✓ Updated VERSION file${NC}"

# Commit
git add "$VERSION_FILE"
git commit -m "chore: bump version to $VERSION

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
echo -e "${GREEN}✓ Committed version bump${NC}"

# Tag
git tag -a "v$VERSION" -m "$MESSAGE"
echo -e "${GREEN}✓ Created tag v$VERSION${NC}"

# Push
git push origin HEAD
git push origin "v$VERSION"
echo -e "${GREEN}✓ Pushed to remote${NC}"

echo ""
echo -e "${GREEN}Successfully released v$VERSION${NC}"
echo ""
echo "Restart containers to pick up new version:"
echo "  docker-compose restart api"
