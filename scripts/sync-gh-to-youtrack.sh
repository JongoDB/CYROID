#!/usr/bin/env bash
#
# GitHub to YouTrack Issue Sync Script
#
# Syncs GitHub issues from CYROID repo to YouTrack Training Development project.
# Maintains state between syncs to detect new, updated, and deleted issues.
#
# Usage:
#   ./scripts/sync-gh-to-youtrack.sh [--dry-run] [--full-sync]
#
# Options:
#   --dry-run    Show what would be done without making changes
#   --full-sync  Ignore last sync state and process all issues
#
# Requirements:
#   - gh CLI authenticated
#   - curl, jq installed
#   - YOUTRACK_TOKEN environment variable set
#
# Assignee Mapping:
#   - GitHub: JongoDB    → YouTrack: jon
#   - GitHub: morbidsteve → YouTrack: steve
#

set -eo pipefail

# Configuration
YOUTRACK_URL="https://youtrack.fightingsmartcyber.com"
YOUTRACK_PROJECT_ID="0-6"
YOUTRACK_PROJECT_SHORT="TRG"
CYROID_TAG_ID="10-5"
SYNC_STATE_FILE="${SYNC_STATE_FILE:-$HOME/.cyroid-youtrack-sync.json}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
FULL_SYNC=false
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --full-sync)
            FULL_SYNC=true
            ;;
        --help|-h)
            head -30 "$0" | tail -28
            exit 0
            ;;
    esac
done

# Check for token
if [[ -z "${YOUTRACK_TOKEN:-}" ]]; then
    echo -e "${RED}Error: YOUTRACK_TOKEN environment variable not set${NC}"
    echo "Export your YouTrack permanent token:"
    echo "  export YOUTRACK_TOKEN='perm:xxx'"
    exit 1
fi

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_dry() { echo -e "${YELLOW}[DRY-RUN]${NC} $1"; }

# User mapping functions
get_yt_user() {
    local gh_author="$1"
    case "$gh_author" in
        JongoDB) echo "jon" ;;
        morbidsteve) echo "steve" ;;
        *) echo "" ;;
    esac
}

get_yt_user_id() {
    local yt_user="$1"
    case "$yt_user" in
        jon) echo "2-3" ;;
        steve) echo "2-4" ;;
        *) echo "" ;;
    esac
}

# YouTrack API helper
yt_api() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"

    local args=(-s -X "$method" "${YOUTRACK_URL}/api${endpoint}")
    args+=(-H "Authorization: Bearer $YOUTRACK_TOKEN")
    args+=(-H "Accept: application/json")

    if [[ -n "$data" ]]; then
        args+=(-H "Content-Type: application/json")
        args+=(-d "$data")
    fi

    curl "${args[@]}"
}

# Map GitHub state to YouTrack state
gh_state_to_yt() {
    case "$1" in
        OPEN) echo "Open" ;;
        CLOSED) echo "Done" ;;
        *) echo "Open" ;;
    esac
}

# Load last sync state
load_sync_state() {
    if [[ -f "$SYNC_STATE_FILE" ]] && [[ "$FULL_SYNC" == "false" ]]; then
        cat "$SYNC_STATE_FILE"
    else
        echo '{"issues": {}, "gh_to_yt": {}, "last_sync": null}'
    fi
}

# Save sync state
save_sync_state() {
    local state="$1"
    if [[ "$DRY_RUN" == "false" ]]; then
        echo "$state" > "$SYNC_STATE_FILE"
        log_info "Sync state saved to $SYNC_STATE_FILE"
    fi
}

# Create a new YouTrack issue
create_yt_issue() {
    local gh_number="$1"
    local title="$2"
    local body="$3"
    local gh_author="$4"
    local gh_state="$5"

    local yt_assignee=$(get_yt_user "$gh_author")
    local yt_state=$(gh_state_to_yt "$gh_state")

    # Prepare description with GitHub reference
    local description="**GitHub Issue:** #${gh_number}

${body}"

    # Escape for JSON
    local json_desc=$(echo "$description" | jq -Rs .)
    local json_title=$(echo "$title" | jq -Rs .)

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would create: GH#$gh_number → '$title' (assignee: ${yt_assignee:-none}, state: $yt_state)"
        echo "DRY-RUN-ID"
        return
    fi

    # Create the issue
    local payload="{\"project\": {\"id\": \"$YOUTRACK_PROJECT_ID\"}, \"summary\": $json_title, \"description\": $json_desc}"
    local response=$(yt_api POST "/issues?fields=id,idReadable" "$payload")

    local yt_id=$(echo "$response" | jq -r '.id // empty')
    local yt_readable=$(echo "$response" | jq -r '.idReadable // empty')

    if [[ -z "$yt_id" ]]; then
        log_error "Failed to create issue for GH#$gh_number: $response"
        return 1
    fi

    # Apply tag
    yt_api POST "/issues/$yt_id/tags?fields=id" "{\"id\": \"$CYROID_TAG_ID\"}" > /dev/null

    # Set assignee and state via command
    if [[ -n "$yt_assignee" ]]; then
        yt_api POST "/commands" "{\"query\": \"Assignee $yt_assignee State $yt_state\", \"issues\": [{\"idReadable\": \"$yt_readable\"}]}" > /dev/null
    else
        yt_api POST "/commands" "{\"query\": \"State $yt_state\", \"issues\": [{\"idReadable\": \"$yt_readable\"}]}" > /dev/null
    fi

    log_success "Created $yt_readable: GH#$gh_number → '$title' (assignee: ${yt_assignee:-none}, state: $yt_state)"
    echo "$yt_readable"
}

# Update YouTrack issue state
update_yt_state() {
    local yt_id="$1"
    local new_state="$2"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would update $yt_id state to: $new_state"
        return
    fi

    yt_api POST "/commands" "{\"query\": \"State $new_state\", \"issues\": [{\"idReadable\": \"$yt_id\"}]}" > /dev/null
    log_success "Updated $yt_id state to: $new_state"
}

# Mark YouTrack issue as obsolete (for deleted GH issues)
mark_yt_obsolete() {
    local yt_id="$1"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would mark $yt_id as Obsolete (GH issue deleted)"
        return
    fi

    yt_api POST "/commands" "{\"query\": \"State Obsolete\", \"issues\": [{\"idReadable\": \"$yt_id\"}]}" > /dev/null
    log_success "Marked $yt_id as Obsolete (GH issue deleted)"
}

# Update YouTrack issue title
update_yt_title() {
    local yt_id="$1"
    local new_title="$2"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_dry "Would update $yt_id title to: $new_title"
        return
    fi

    local json_title=$(echo "$new_title" | jq -Rs .)
    yt_api POST "/issues/$yt_id?fields=id" "{\"summary\": $json_title}" > /dev/null
    log_success "Updated $yt_id title"
}

# Main sync logic
main() {
    log_info "Starting GitHub → YouTrack sync"
    [[ "$DRY_RUN" == "true" ]] && log_warn "DRY RUN MODE - No changes will be made"
    [[ "$FULL_SYNC" == "true" ]] && log_warn "FULL SYNC MODE - Ignoring previous state"

    # Load previous state
    local prev_state=$(load_sync_state)
    local prev_issues=$(echo "$prev_state" | jq -r '.issues // {}')
    local gh_to_yt=$(echo "$prev_state" | jq -r '.gh_to_yt // {}')

    # Get current GitHub issues
    log_info "Fetching GitHub issues..."
    local current_issues=$(gh issue list --state all --limit 500 --json number,title,body,state,author,labels,createdAt,closedAt,updatedAt | \
        jq -c 'map({
            number: .number,
            title: .title,
            body: (.body // ""),
            state: .state,
            author: .author.login,
            labels: [.labels[].name],
            createdAt: .createdAt,
            closedAt: .closedAt,
            updatedAt: .updatedAt
        })')
    local current_count=$(echo "$current_issues" | jq 'length')
    log_info "Found $current_count GitHub issues"

    # Track stats
    local created=0
    local updated=0
    local deleted=0
    local unchanged=0

    # Build current issue map
    local current_map=$(echo "$current_issues" | jq -c 'map({(.number | tostring): .}) | add // {}')

    # Process each current GitHub issue
    while IFS= read -r issue; do
        local gh_num=$(echo "$issue" | jq -r '.number')
        local gh_title=$(echo "$issue" | jq -r '.title')
        local gh_body=$(echo "$issue" | jq -r '.body')
        local gh_state=$(echo "$issue" | jq -r '.state')
        local gh_author=$(echo "$issue" | jq -r '.author')

        # Check if we've seen this issue before
        local prev_issue=$(echo "$prev_issues" | jq -r ".[\"$gh_num\"] // empty")
        local yt_id=$(echo "$gh_to_yt" | jq -r ".[\"$gh_num\"] // empty")

        if [[ -z "$prev_issue" ]] || [[ -z "$yt_id" ]]; then
            # New issue - create in YouTrack
            local new_yt_id=$(create_yt_issue "$gh_num" "$gh_title" "$gh_body" "$gh_author" "$gh_state")
            if [[ -n "$new_yt_id" ]] && [[ "$new_yt_id" != "DRY-RUN-ID" ]]; then
                gh_to_yt=$(echo "$gh_to_yt" | jq --arg num "$gh_num" --arg yt "$new_yt_id" '. + {($num): $yt}')
            fi
            created=$((created + 1))
        else
            # Existing issue - check for updates
            local prev_gh_state=$(echo "$prev_issue" | jq -r '.state')
            local prev_title=$(echo "$prev_issue" | jq -r '.title')
            local needs_update=false

            # Check state change
            if [[ "$gh_state" != "$prev_gh_state" ]]; then
                local yt_state=$(gh_state_to_yt "$gh_state")
                update_yt_state "$yt_id" "$yt_state"
                needs_update=true
            fi

            # Check title change
            if [[ "$gh_title" != "$prev_title" ]]; then
                update_yt_title "$yt_id" "$gh_title"
                needs_update=true
            fi

            if [[ "$needs_update" == "true" ]]; then
                updated=$((updated + 1))
            else
                unchanged=$((unchanged + 1))
            fi
        fi
    done < <(echo "$current_issues" | jq -c '.[]')

    # Check for deleted GitHub issues
    local prev_numbers=$(echo "$prev_issues" | jq -r 'keys[]')
    for gh_num in $prev_numbers; do
        local still_exists=$(echo "$current_map" | jq -r ".[\"$gh_num\"] // empty")
        if [[ -z "$still_exists" ]]; then
            local yt_id=$(echo "$gh_to_yt" | jq -r ".[\"$gh_num\"] // empty")
            if [[ -n "$yt_id" ]]; then
                mark_yt_obsolete "$yt_id"
                deleted=$((deleted + 1))
            fi
        fi
    done

    # Save new state
    local new_state=$(jq -n \
        --argjson issues "$current_map" \
        --argjson mapping "$gh_to_yt" \
        --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        '{issues: $issues, gh_to_yt: $mapping, last_sync: $timestamp}')

    save_sync_state "$new_state"

    # Print summary
    echo ""
    log_info "=== Sync Summary ==="
    echo -e "  Created:   ${GREEN}$created${NC}"
    echo -e "  Updated:   ${YELLOW}$updated${NC}"
    echo -e "  Deleted:   ${RED}$deleted${NC}"
    echo -e "  Unchanged: $unchanged"
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "This was a dry run. Run without --dry-run to apply changes."
    else
        log_success "Sync complete!"
    fi
}

main
