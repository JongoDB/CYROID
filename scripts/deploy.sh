#!/bin/bash
# CYROID Production Deployment Script
#
# Full TUI for deploying and managing CYROID in production.
# Uses 'gum' for beautiful terminal interfaces (auto-installs on macOS).
#
# This script works TWO ways:
#   1. From git clone: git clone https://github.com/JongoDB/CYROID && cd CYROID && ./scripts/deploy.sh
#   2. Standalone:     curl -fsSL https://raw.githubusercontent.com/JongoDB/CYROID/master/scripts/deploy.sh -o deploy.sh && bash deploy.sh
#
# Usage:
#   ./scripts/deploy.sh                                    # Interactive TUI setup
#   ./scripts/deploy.sh --domain example.com              # Domain with Let's Encrypt
#   ./scripts/deploy.sh --ip 192.168.1.100                # IP with self-signed cert
#   ./scripts/deploy.sh --update                          # Update (choose version)
#   ./scripts/deploy.sh --update --version v0.30.0        # Update to specific version
#   ./scripts/deploy.sh --start                           # Start stopped deployment
#   ./scripts/deploy.sh --stop                            # Stop all services
#   ./scripts/deploy.sh --restart                         # Restart all services
#   ./scripts/deploy.sh --status                          # Show service status
#
# Options:
#   --domain DOMAIN    Domain name for the server
#   --ip IP            IP address for the server
#   --email EMAIL      Email for Let's Encrypt (optional with --domain)
#   --ssl MODE         SSL mode: letsencrypt, selfsigned, manual (default: auto)
#   --version VER      CYROID version to deploy/update to (default: interactive)
#   --update           Update deployment (interactive version selection)
#   --start            Start a stopped deployment
#   --stop             Stop all services
#   --restart          Stop and start all services
#   --status           Show service status and health
#   --help             Show this help message

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory and project root
# Handle both normal execution and piped execution (curl | bash)
if [ -n "${BASH_SOURCE[0]}" ] && [ "${BASH_SOURCE[0]}" != "/dev/stdin" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Check if script is in a "scripts/" subdirectory (standard repo layout)
    PARENT_DIR="$(dirname "$SCRIPT_DIR")"
    SCRIPT_BASENAME="$(basename "$SCRIPT_DIR")"

    if [ "$SCRIPT_BASENAME" = "scripts" ] && [ -f "$PARENT_DIR/docker-compose.yml" ]; then
        # Script is at PROJECT_ROOT/scripts/deploy.sh
        PROJECT_ROOT="$PARENT_DIR"
    elif [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
        # Script is at PROJECT_ROOT/deploy.sh (same dir has docker-compose.yml)
        PROJECT_ROOT="$SCRIPT_DIR"
    else
        # Standalone mode - script dir becomes project root, will bootstrap files
        PROJECT_ROOT="$SCRIPT_DIR"
    fi
else
    # Running via curl | bash or similar - use current directory or home
    if [ -f "./docker-compose.yml" ]; then
        PROJECT_ROOT="$(pwd)"
    else
        PROJECT_ROOT="$HOME/cyroid"
    fi
    SCRIPT_DIR="$PROJECT_ROOT/scripts"
fi
ENV_FILE="$PROJECT_ROOT/.env.prod"

# Default values
DOMAIN=""
IP=""
EMAIL=""
SSL_MODE=""
VERSION="latest"
ACTION="deploy"
DATA_DIR=""  # Set after OS detection

# Admin user credentials (set during create_initial_admin)
ADMIN_USERNAME=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""

# GitHub repository for downloading files
GITHUB_REPO="JongoDB/CYROID"
GITHUB_BRANCH="master"
GITHUB_RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

# =============================================================================
# Bootstrap Functions (for standalone script mode)
# =============================================================================

download_file() {
    local url="$1"
    local dest="$2"
    local desc="${3:-file}"

    mkdir -p "$(dirname "$dest")"

    if command -v curl &> /dev/null; then
        if curl -fsSL "$url" -o "$dest" 2>/dev/null; then
            return 0
        fi
    elif command -v wget &> /dev/null; then
        if wget -q "$url" -O "$dest" 2>/dev/null; then
            return 0
        fi
    fi

    echo -e "${RED}[ERROR]${NC} Failed to download $desc"
    return 1
}

bootstrap_standalone() {
    # Check if we're in a proper CYROID directory with required files
    # If not, download them from GitHub

    local missing_files=()

    # Check for required compose files
    if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        missing_files+=("docker-compose.yml")
    fi
    if [ ! -f "$PROJECT_ROOT/docker-compose.prod.yml" ]; then
        missing_files+=("docker-compose.prod.yml")
    fi

    # If no files are missing, we're in a proper repo - continue normally
    if [ ${#missing_files[@]} -eq 0 ]; then
        return 0
    fi

    echo -e "${CYAN}"
    echo "  ██████╗██╗   ██╗██████╗  ██████╗ ██╗██████╗ "
    echo " ██╔════╝╚██╗ ██╔╝██╔══██╗██╔═══██╗██║██╔══██╗"
    echo " ██║      ╚████╔╝ ██████╔╝██║   ██║██║██║  ██║"
    echo " ██║       ╚██╔╝  ██╔══██╗██║   ██║██║██║  ██║"
    echo " ╚██████╗   ██║   ██║  ██║╚██████╔╝██║██████╔╝"
    echo "  ╚═════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝╚═════╝ "
    echo -e "${NC}"
    echo -e "${BOLD}Cyber Range Orchestrator In Docker${NC}"
    echo ""
    echo -e "${YELLOW}Standalone mode detected - downloading required files...${NC}"
    echo ""

    # Check for curl or wget
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Neither curl nor wget found. Please install one of them."
        exit 1
    fi

    # Create CYROID directory if running from arbitrary location
    if [ ! -d "$PROJECT_ROOT" ] || [ "$PROJECT_ROOT" = "/" ]; then
        PROJECT_ROOT="$HOME/cyroid"
        SCRIPT_DIR="$PROJECT_ROOT/scripts"
        ENV_FILE="$PROJECT_ROOT/.env.prod"
        echo -e "${GREEN}[INFO]${NC} Creating CYROID directory at: $PROJECT_ROOT"
        mkdir -p "$PROJECT_ROOT/scripts"
    fi

    # Download required files
    local files_to_download=(
        "docker-compose.yml"
        "docker-compose.prod.yml"
        "traefik/dynamic/base.yml"
        "traefik/dynamic/production.yml"
    )

    for file in "${files_to_download[@]}"; do
        local dest="$PROJECT_ROOT/$file"
        if [ ! -f "$dest" ]; then
            echo -e "${GREEN}[INFO]${NC} Downloading $file..."
            if ! download_file "${GITHUB_RAW_BASE}/$file" "$dest" "$file"; then
                echo -e "${RED}[ERROR]${NC} Failed to download $file"
                echo -e "${YELLOW}[HINT]${NC} Try: git clone https://github.com/${GITHUB_REPO}.git"
                exit 1
            fi
        fi
    done

    # Copy this script to the project if not already there
    if [ ! -f "$PROJECT_ROOT/scripts/deploy.sh" ]; then
        cp "${BASH_SOURCE[0]}" "$PROJECT_ROOT/scripts/deploy.sh" 2>/dev/null || true
        chmod +x "$PROJECT_ROOT/scripts/deploy.sh" 2>/dev/null || true
    fi

    echo ""
    echo -e "${GREEN}[INFO]${NC} Required files downloaded to: $PROJECT_ROOT"
    echo -e "${GREEN}[INFO]${NC} Continuing with deployment..."
    echo ""

    # Update paths for the new location
    cd "$PROJECT_ROOT"
}

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    echo "  ██████╗██╗   ██╗██████╗  ██████╗ ██╗██████╗ "
    echo " ██╔════╝╚██╗ ██╔╝██╔══██╗██╔═══██╗██║██╔══██╗"
    echo " ██║      ╚████╔╝ ██████╔╝██║   ██║██║██║  ██║"
    echo " ██║       ╚██╔╝  ██╔══██╗██║   ██║██║██║  ██║"
    echo " ╚██████╗   ██║   ██║  ██║╚██████╔╝██║██████╔╝"
    echo "  ╚═════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝╚═════╝ "
    echo -e "${NC}"
    echo -e "${BOLD}Cyber Range Orchestrator In Docker${NC}"
    echo ""
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${BLUE}==>${NC} ${BOLD}$1${NC}"
}

generate_secret() {
    # Generate a random 64-character secret
    openssl rand -base64 48 | tr -d '/+=' | head -c 64
}

# =============================================================================
# TUI Functions (using gum)
# =============================================================================

USE_TUI=true

# Auto-install gum (TUI tool) on macOS and Linux
install_gum() {
    local arch
    local os
    local gum_version="0.14.5"
    local download_url
    local tmp_dir

    # Detect architecture
    case "$(uname -m)" in
        x86_64|amd64) arch="x86_64" ;;
        arm64|aarch64) arch="arm64" ;;
        armv7l) arch="armv7" ;;
        *)
            echo -e "${RED}Unsupported architecture: $(uname -m)${NC}"
            return 1
            ;;
    esac

    # Detect OS
    case "$(uname -s)" in
        Darwin) os="Darwin" ;;
        Linux) os="Linux" ;;
        *)
            echo -e "${RED}Unsupported OS: $(uname -s)${NC}"
            return 1
            ;;
    esac

    download_url="https://github.com/charmbracelet/gum/releases/download/v${gum_version}/gum_${gum_version}_${os}_${arch}.tar.gz"
    tmp_dir=$(mktemp -d)

    echo -e "${CYAN}Downloading gum v${gum_version} for ${os}/${arch}...${NC}"

    if command -v curl &> /dev/null; then
        curl -fsSL "$download_url" -o "$tmp_dir/gum.tar.gz" || return 1
    elif command -v wget &> /dev/null; then
        wget -q "$download_url" -O "$tmp_dir/gum.tar.gz" || return 1
    else
        echo -e "${RED}Neither curl nor wget found${NC}"
        return 1
    fi

    # Extract and install
    tar -xzf "$tmp_dir/gum.tar.gz" -C "$tmp_dir" || return 1

    # Try to install to /usr/local/bin, fall back to ~/.local/bin
    if [ -w /usr/local/bin ]; then
        mv "$tmp_dir/gum" /usr/local/bin/gum
        chmod +x /usr/local/bin/gum
    elif [ -w ~/.local/bin ]; then
        mkdir -p ~/.local/bin
        mv "$tmp_dir/gum" ~/.local/bin/gum
        chmod +x ~/.local/bin/gum
        export PATH="$HOME/.local/bin:$PATH"
    else
        # Try with sudo
        echo -e "${YELLOW}Installing gum requires sudo access...${NC}"
        sudo mv "$tmp_dir/gum" /usr/local/bin/gum
        sudo chmod +x /usr/local/bin/gum
    fi

    rm -rf "$tmp_dir"

    if command -v gum &> /dev/null; then
        echo -e "${GREEN}gum installed successfully${NC}"
        return 0
    else
        return 1
    fi
}

check_gum() {
    if command -v gum &> /dev/null; then
        return 0
    fi

    echo -e "${YELLOW}Installing 'gum' for beautiful terminal interfaces...${NC}"

    detect_os

    # Try package manager first (preferred for updates)
    local installed=false

    if [ "$OS_TYPE" = "macos" ]; then
        if command -v brew &> /dev/null; then
            echo -e "${CYAN}Installing via Homebrew...${NC}"
            if brew install gum 2>/dev/null; then
                installed=true
            fi
        fi
    else
        # Linux - try various package managers
        if command -v apt-get &> /dev/null; then
            # Debian/Ubuntu - add charm repo if needed
            if ! apt-cache show gum &> /dev/null 2>&1; then
                echo -e "${CYAN}Adding Charm repository...${NC}"
                sudo mkdir -p /etc/apt/keyrings
                curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg 2>/dev/null || true
                echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list > /dev/null
                sudo apt-get update -qq 2>/dev/null || true
            fi
            echo -e "${CYAN}Installing via apt...${NC}"
            if sudo apt-get install -y gum 2>/dev/null; then
                installed=true
            fi
        elif command -v dnf &> /dev/null; then
            echo -e "${CYAN}Installing via dnf...${NC}"
            if sudo dnf install -y gum 2>/dev/null; then
                installed=true
            fi
        elif command -v yum &> /dev/null; then
            echo -e "${CYAN}Installing via yum...${NC}"
            if sudo yum install -y gum 2>/dev/null; then
                installed=true
            fi
        elif command -v pacman &> /dev/null; then
            echo -e "${CYAN}Installing via pacman...${NC}"
            if sudo pacman -S --noconfirm gum 2>/dev/null; then
                installed=true
            fi
        elif command -v zypper &> /dev/null; then
            echo -e "${CYAN}Installing via zypper...${NC}"
            if sudo zypper install -y gum 2>/dev/null; then
                installed=true
            fi
        elif command -v apk &> /dev/null; then
            echo -e "${CYAN}Installing via apk...${NC}"
            if sudo apk add gum 2>/dev/null; then
                installed=true
            fi
        fi
    fi

    # If package manager failed, try direct binary download
    if [ "$installed" = false ]; then
        echo -e "${YELLOW}Package manager install failed, trying direct download...${NC}"
        if install_gum; then
            installed=true
        fi
    fi

    # Final check
    if command -v gum &> /dev/null; then
        return 0
    fi

    # All install methods failed - fall back to non-TUI mode
    echo -e "${YELLOW}Could not install gum. Continuing without TUI...${NC}"
    USE_TUI=false
    return 1
}

tui_clear() {
    if [ "$USE_TUI" = true ]; then
        clear
    fi
}

tui_header() {
    if [ "$USE_TUI" = true ]; then
        gum style \
            --foreground 212 --border-foreground 212 --border double \
            --align center --width 60 --margin "1 2" --padding "1 2" \
            "$(echo -e "██████╗██╗   ██╗██████╗  ██████╗ ██╗██████╗ \n██╔════╝╚██╗ ██╔╝██╔══██╗██╔═══██╗██║██╔══██╗\n██║      ╚████╔╝ ██████╔╝██║   ██║██║██║  ██║\n██║       ╚██╔╝  ██╔══██╗██║   ██║██║██║  ██║\n╚██████╗   ██║   ██║  ██║╚██████╔╝██║██████╔╝\n ╚═════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝╚═════╝ ")"
        echo ""
        gum style --foreground 99 --bold "Cyber Range Orchestrator In Docker"
        echo ""
    else
        print_banner
    fi
}

tui_title() {
    if [ "$USE_TUI" = true ]; then
        gum style --foreground 212 --bold "$1"
    else
        echo -e "${BOLD}$1${NC}"
    fi
}

tui_choose() {
    local prompt="$1"
    shift
    if [ "$USE_TUI" = true ]; then
        gum choose --header "$prompt" "$@"
    else
        echo "$prompt"
        select opt in "$@"; do
            echo "$opt"
            break
        done
    fi
}

tui_input() {
    local prompt="$1"
    local placeholder="${2:-}"
    local default="${3:-}"
    if [ "$USE_TUI" = true ]; then
        gum input --placeholder "$placeholder" --value "$default" --header "$prompt"
    else
        read -p "$prompt [$default]: " value
        echo "${value:-$default}"
    fi
}

tui_confirm() {
    local prompt="$1"
    if [ "$USE_TUI" = true ]; then
        gum confirm "$prompt"
    else
        read -p "$prompt [Y/n]: " choice
        [[ ! "$choice" =~ ^[Nn] ]]
    fi
}

tui_spin() {
    local title="$1"
    shift
    if [ "$USE_TUI" = true ]; then
        gum spin --spinner dot --title "$title" -- "$@"
    else
        echo "$title"
        "$@"
    fi
}

tui_success() {
    if [ "$USE_TUI" = true ]; then
        gum style --foreground 82 --bold "✓ $1"
    else
        log_info "$1"
    fi
}

tui_error() {
    if [ "$USE_TUI" = true ]; then
        gum style --foreground 196 --bold "✗ $1"
    else
        log_error "$1"
    fi
}

tui_warn() {
    if [ "$USE_TUI" = true ]; then
        gum style --foreground 214 "⚠ $1"
    else
        log_warn "$1"
    fi
}

tui_info() {
    if [ "$USE_TUI" = true ]; then
        gum style --foreground 39 "→ $1"
    else
        log_info "$1"
    fi
}

tui_summary_box() {
    if [ "$USE_TUI" = true ]; then
        gum style \
            --border rounded --border-foreground 39 \
            --padding "1 2" --margin "1 0" \
            "$1"
    else
        echo ""
        echo "$1"
        echo ""
    fi
}

# =============================================================================
# Full-Screen TUI Framework (K9s-style)
# =============================================================================

# Terminal state
TERM_LINES=24
TERM_COLS=80
STATUS_MESSAGE=""
STATUS_TYPE="info"  # info, success, warn, error, progress
DEPLOYMENT_PHASE=""
DEPLOYMENT_PROGRESS=0
TUI_FULLSCREEN=false

# Save terminal state for cleanup
ORIGINAL_STTY=""

tui_init_fullscreen() {
    if [ "$USE_TUI" != true ]; then
        return
    fi

    # Save terminal settings
    ORIGINAL_STTY=$(stty -g 2>/dev/null) || true

    # Get terminal dimensions
    tui_update_dimensions

    # Set up cleanup trap
    trap 'tui_cleanup_fullscreen' EXIT INT TERM

    # Hide cursor during redraws
    tput civis 2>/dev/null || true

    TUI_FULLSCREEN=true

    # Initial draw
    tui_draw_screen
}

tui_cleanup_fullscreen() {
    if [ "$TUI_FULLSCREEN" = true ]; then
        # Show cursor
        tput cnorm 2>/dev/null || true

        # Restore terminal settings
        if [ -n "$ORIGINAL_STTY" ]; then
            stty "$ORIGINAL_STTY" 2>/dev/null || true
        fi

        # Move cursor to bottom and reset
        tput cup "$TERM_LINES" 0 2>/dev/null || true
        echo ""

        TUI_FULLSCREEN=false
    fi
}

tui_update_dimensions() {
    TERM_LINES=$(tput lines 2>/dev/null || echo 24)
    TERM_COLS=$(tput cols 2>/dev/null || echo 80)
}

tui_set_status() {
    local message="$1"
    local type="${2:-info}"  # info, success, warn, error, progress

    STATUS_MESSAGE="$message"
    STATUS_TYPE="$type"

    # Immediately update status bar if in fullscreen mode
    if [ "$TUI_FULLSCREEN" = true ]; then
        tui_draw_status_bar
    fi
}

tui_set_progress() {
    local phase="$1"
    local progress="$2"  # 0-100

    DEPLOYMENT_PHASE="$phase"
    DEPLOYMENT_PROGRESS="$progress"

    tui_set_status "$phase" "progress"
}

tui_draw_status_bar() {
    if [ "$USE_TUI" != true ]; then
        return
    fi

    # Update dimensions in case terminal was resized
    tui_update_dimensions

    # Save cursor position
    tput sc 2>/dev/null || true

    # Move to bottom line (leave 1 line for status bar)
    local status_line=$((TERM_LINES - 1))
    tput cup "$status_line" 0 2>/dev/null || true

    # Build status bar content
    local timestamp=$(date '+%H:%M:%S')
    local status_icon=""
    local status_color=""

    case "$STATUS_TYPE" in
        success)  status_icon="✓"; status_color="82" ;;
        warn)     status_icon="⚠"; status_color="214" ;;
        error)    status_icon="✗"; status_color="196" ;;
        progress) status_icon="◐"; status_color="39" ;;
        *)        status_icon="→"; status_color="245" ;;
    esac

    # Create progress bar if in progress mode
    local progress_bar=""
    if [ "$STATUS_TYPE" = "progress" ] && [ "$DEPLOYMENT_PROGRESS" -gt 0 ]; then
        local bar_width=20
        local filled=$((DEPLOYMENT_PROGRESS * bar_width / 100))
        local empty=$((bar_width - filled))
        progress_bar=" ["
        for ((i=0; i<filled; i++)); do progress_bar+="█"; done
        for ((i=0; i<empty; i++)); do progress_bar+="░"; done
        progress_bar+="] ${DEPLOYMENT_PROGRESS}%"
    fi

    # Build the full status line
    local left_content="$status_icon $STATUS_MESSAGE$progress_bar"
    local right_content="$timestamp"

    # Calculate padding
    local left_len=${#left_content}
    local right_len=${#right_content}
    local padding=$((TERM_COLS - left_len - right_len - 4))
    if [ $padding -lt 0 ]; then padding=0; fi

    # Clear the line and draw status bar
    printf "\033[48;5;236m\033[K"  # Dark gray background, clear line

    # Draw with colors
    printf "\033[38;5;${status_color}m %s\033[38;5;245m" "$status_icon"
    printf " %s" "$STATUS_MESSAGE"
    if [ -n "$progress_bar" ]; then
        printf "\033[38;5;39m%s\033[0m" "$progress_bar"
    fi

    # Right-align timestamp
    printf "%*s" "$padding" ""
    printf "\033[38;5;245m%s \033[0m" "$right_content"

    # Restore cursor position
    tput rc 2>/dev/null || true
}

tui_draw_header_bar() {
    if [ "$USE_TUI" != true ]; then
        return
    fi

    # Move to top
    tput cup 0 0 2>/dev/null || true

    # Build header bar
    local title="CYROID"
    local version="${VERSION:-latest}"
    local right_content="v$version"

    # Calculate padding
    local left_len=${#title}
    local right_len=${#right_content}
    local padding=$((TERM_COLS - left_len - right_len - 4))
    if [ $padding -lt 0 ]; then padding=0; fi

    # Draw header bar with cyan background
    printf "\033[48;5;24m\033[38;5;255m\033[K"  # Dark blue background, white text
    printf " %s" "$title"
    printf "%*s" "$padding" ""
    printf "%s \033[0m\n" "$right_content"
}

tui_draw_screen() {
    if [ "$USE_TUI" != true ]; then
        return
    fi

    # Clear screen
    clear

    # Draw header bar
    tui_draw_header_bar

    # Draw status bar at bottom
    tui_draw_status_bar

    # Position cursor for main content (line 3, after header)
    tput cup 2 0 2>/dev/null || true
}

tui_main_area() {
    # Position cursor in main content area
    if [ "$TUI_FULLSCREEN" = true ]; then
        tput cup 2 0 2>/dev/null || true
    fi
}

# Deployment progress helper
tui_deployment_step() {
    local step_name="$1"
    local step_num="$2"
    local total_steps="$3"

    local progress=$((step_num * 100 / total_steps))
    tui_set_progress "$step_name" "$progress"

    # Also print to main area
    tui_info "$step_name"
}

# Service status monitoring
tui_show_services_status() {
    if [ "$USE_TUI" != true ]; then
        return
    fi

    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    # Get service status
    local services=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null) || true

    if [ -n "$services" ]; then
        echo ""
        gum style --foreground 212 --bold "Services"
        echo "$services" | while IFS= read -r line; do
            if echo "$line" | grep -q "(healthy)"; then
                gum style --foreground 82 "  $line"
            elif echo "$line" | grep -q "Up"; then
                gum style --foreground 214 "  $line"
            elif echo "$line" | grep -q "NAME"; then
                gum style --foreground 245 "  $line"
            else
                gum style --foreground 196 "  $line"
            fi
        done
    fi
}

# Live status update (can be called periodically)
tui_refresh_status() {
    if [ "$TUI_FULLSCREEN" != true ]; then
        return
    fi

    # Update status bar with current time
    tui_draw_status_bar
}

# Background status updater
STATUS_UPDATER_PID=""

tui_start_status_updater() {
    if [ "$USE_TUI" != true ]; then
        return
    fi

    # Start background process to update status every 5 seconds
    (
        while true; do
            sleep 5
            tui_refresh_status
        done
    ) &
    STATUS_UPDATER_PID=$!
}

tui_stop_status_updater() {
    if [ -n "$STATUS_UPDATER_PID" ]; then
        kill "$STATUS_UPDATER_PID" 2>/dev/null || true
        STATUS_UPDATER_PID=""
    fi
}

# Live Dashboard (K9s-style)
tui_live_dashboard() {
    local compose_cmd="${1:-docker compose}"

    # Hide cursor
    tput civis 2>/dev/null || true

    # Trap to restore cursor on exit
    trap 'tput cnorm 2>/dev/null; return' INT TERM

    local refresh_interval=5
    local last_key=""

    while true; do
        # Get terminal dimensions
        local lines=$(tput lines 2>/dev/null || echo 24)
        local cols=$(tput cols 2>/dev/null || echo 80)

        # Clear screen
        clear

        # Draw header with prominent exit instructions
        printf "\033[48;5;24m\033[38;5;255m\033[K"
        printf " CYROID Live Dashboard"
        printf "%*s" $((cols - 60)) ""
        printf "\033[48;5;214m\033[38;5;0m q=quit \033[48;5;24m\033[38;5;255m r=refresh \033[0m\n"

        echo ""

        # Get service status
        local services=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null) || true
        local healthy=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
        local running=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "Up" || echo "0")
        local total=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -v "NAME" | grep -c "" || echo "0")

        # Summary bar
        local status_color="82"  # green
        local status_text="HEALTHY"
        if [ "$healthy" -lt 3 ]; then
            status_color="214"  # yellow
            status_text="DEGRADED"
        fi
        if [ "$running" -eq 0 ]; then
            status_color="196"  # red
            status_text="DOWN"
        fi

        gum style --foreground "$status_color" --bold "  Status: $status_text  |  Services: $running running, $healthy healthy"
        echo ""

        # Services table
        gum style --foreground 212 --bold "  Services"
        echo ""

        if [ -n "$services" ]; then
            echo "$services" | while IFS= read -r line; do
                if echo "$line" | grep -q "(healthy)"; then
                    printf "    \033[38;5;82m●\033[0m %s\n" "$line"
                elif echo "$line" | grep -q "Up"; then
                    printf "    \033[38;5;214m●\033[0m %s\n" "$line"
                elif echo "$line" | grep -q "NAME"; then
                    printf "    \033[38;5;245m  %s\033[0m\n" "$line"
                else
                    printf "    \033[38;5;196m●\033[0m %s\n" "$line"
                fi
            done
        else
            gum style --foreground 196 "    No services found"
        fi

        echo ""

        # Ranges section
        local range_containers=$(docker ps --filter "label=cyroid.type=dind" --format "{{.Names}}\t{{.Status}}" 2>/dev/null) || true
        local range_count=$(echo "$range_containers" | grep -c "" 2>/dev/null || echo "0")
        if [ -z "$range_containers" ]; then range_count=0; fi

        gum style --foreground 212 --bold "  Deployed Ranges ($range_count)"
        echo ""

        if [ -n "$range_containers" ] && [ "$range_count" -gt 0 ]; then
            echo "$range_containers" | while IFS=$'\t' read -r name status; do
                if [ -n "$name" ]; then
                    if echo "$status" | grep -q "Up"; then
                        printf "    \033[38;5;82m●\033[0m %-30s %s\n" "$name" "$status"
                    else
                        printf "    \033[38;5;196m●\033[0m %-30s %s\n" "$name" "$status"
                    fi
                fi
            done
        else
            gum style --foreground 245 "    No ranges deployed"
        fi

        echo ""

        # Resource usage (if docker stats available)
        gum style --foreground 212 --bold "  Resource Usage"
        echo ""

        local stats=$(docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | head -8) || true
        if [ -n "$stats" ]; then
            echo "$stats" | while IFS= read -r line; do
                printf "    %s\n" "$line"
            done
        else
            gum style --foreground 245 "    Stats unavailable"
        fi

        # Draw status bar at bottom
        tput cup $((lines - 1)) 0 2>/dev/null || true
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        printf "\033[48;5;236m\033[38;5;245m\033[K"
        printf " Auto-refresh: ${refresh_interval}s"
        printf "%*s" $((cols - 35)) ""
        printf "Last update: %s \033[0m" "$timestamp"

        # Wait for key or timeout
        if read -t "$refresh_interval" -n 1 key 2>/dev/null; then
            case "$key" in
                q|Q)
                    tput cnorm 2>/dev/null || true
                    clear
                    return
                    ;;
                r|R)
                    continue  # Immediate refresh
                    ;;
            esac
        fi
    done
}

check_prerequisites() {
    # Comprehensive pre-flight checks for all requirements
    local errors=0

    tui_info "Running pre-flight checks..."
    echo ""

    # Check Docker
    if ! command -v docker &> /dev/null; then
        tui_error "Docker is not installed"
        errors=$((errors + 1))
    elif ! docker info &> /dev/null 2>&1; then
        tui_warn "Docker is installed but not running"
    else
        tui_success "Docker is available"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
        tui_error "Docker Compose is not available"
        errors=$((errors + 1))
    else
        tui_success "Docker Compose is available"
    fi

    # Check curl or wget (needed for version fetching)
    if command -v curl &> /dev/null; then
        tui_success "curl is available"
    elif command -v wget &> /dev/null; then
        tui_success "wget is available"
    else
        tui_warn "Neither curl nor wget found (version fetching may fail)"
    fi

    # Check openssl (needed for self-signed certs)
    if command -v openssl &> /dev/null; then
        tui_success "OpenSSL is available"
    else
        tui_warn "OpenSSL not found (self-signed certs will fail)"
    fi

    # Check required files exist
    if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        tui_error "docker-compose.yml not found - is this the CYROID directory?"
        errors=$((errors + 1))
    else
        tui_success "docker-compose.yml found"
    fi

    if [ ! -f "$PROJECT_ROOT/docker-compose.prod.yml" ]; then
        tui_error "docker-compose.prod.yml not found"
        errors=$((errors + 1))
    else
        tui_success "docker-compose.prod.yml found"
    fi

    echo ""

    if [ $errors -gt 0 ]; then
        tui_error "Pre-flight checks failed with $errors error(s)"
        tui_info "Please fix the issues above and try again"
        exit 1
    fi

    tui_success "All pre-flight checks passed"
    echo ""
}

check_docker() {
    detect_os

    if ! command -v docker &> /dev/null; then
        tui_error "Docker is not installed"
        echo ""
        if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
            gum style --foreground 214 "How to fix:"
            if [ "$OS_TYPE" = "macos" ]; then
                gum style --foreground 245 "  1. Download Docker Desktop: https://docker.com/products/docker-desktop"
                gum style --foreground 245 "  2. Install and launch Docker Desktop"
                gum style --foreground 245 "  3. Run this script again"
            else
                gum style --foreground 245 "  Ubuntu/Debian: sudo apt install docker.io docker-compose-plugin"
                gum style --foreground 245 "  Fedora: sudo dnf install docker docker-compose-plugin"
                gum style --foreground 245 "  Arch: sudo pacman -S docker docker-compose"
                gum style --foreground 245 ""
                gum style --foreground 245 "  Then: sudo systemctl enable --now docker"
            fi
        else
            echo "How to fix:"
            if [ "$OS_TYPE" = "macos" ]; then
                echo "  1. Download Docker Desktop: https://docker.com/products/docker-desktop"
                echo "  2. Install and launch Docker Desktop"
                echo "  3. Run this script again"
            else
                echo "  Ubuntu/Debian: sudo apt install docker.io docker-compose-plugin"
                echo "  Fedora: sudo dnf install docker docker-compose-plugin"
                echo "  Arch: sudo pacman -S docker docker-compose"
                echo ""
                echo "  Then: sudo systemctl enable --now docker"
            fi
        fi
        exit 1
    fi

    if ! docker info &> /dev/null; then
        tui_error "Docker daemon is not running or permission denied"
        echo ""

        if [ "$OS_TYPE" = "macos" ]; then
            tui_info "Docker Desktop needs to be running"
            echo ""
            if tui_confirm "Try to start Docker Desktop?"; then
                open -a Docker 2>/dev/null || open /Applications/Docker.app 2>/dev/null
                tui_info "Waiting for Docker to start..."
                local attempts=0
                while [ $attempts -lt 30 ]; do
                    if docker info &> /dev/null 2>&1; then
                        tui_success "Docker is now running!"
                        return 0
                    fi
                    sleep 2
                    attempts=$((attempts + 1))
                    echo -n "."
                done
                echo ""
                tui_error "Docker didn't start in time. Please start Docker Desktop manually and try again."
                exit 1
            else
                tui_info "Please start Docker Desktop and run this script again"
                exit 1
            fi
        else
            # Linux - offer to start Docker
            if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
                local choice
                choice=$(gum choose --header "Docker is not running. What would you like to do?" \
                    "Start Docker now (requires sudo)" \
                    "Show manual fix steps" \
                    "Cancel")

                case "$choice" in
                    "Start Docker"*)
                        tui_info "Starting Docker..."
                        if sudo systemctl start docker 2>/dev/null; then
                            sleep 2
                            if docker info &> /dev/null; then
                                tui_success "Docker started successfully!"
                                return 0
                            fi
                        fi
                        tui_error "Failed to start Docker"
                        exit 1
                        ;;
                    "Show"*)
                        echo ""
                        gum style --foreground 214 "Manual fix steps:"
                        gum style --foreground 245 "  1. Start Docker:    sudo systemctl start docker"
                        gum style --foreground 245 "  2. Enable on boot:  sudo systemctl enable docker"
                        gum style --foreground 245 "  3. Fix permissions: sudo usermod -aG docker \$USER"
                        gum style --foreground 245 "     (requires logout/login to take effect)"
                        exit 1
                        ;;
                    *)
                        exit 1
                        ;;
                esac
            else
                echo "How to fix:"
                echo "  Start Docker:    sudo systemctl start docker"
                echo "  Enable on boot:  sudo systemctl enable docker"
                echo "  Fix permissions: sudo usermod -aG docker \$USER"
                echo "                   (then log out and back in)"
                exit 1
            fi
        fi
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        tui_error "Docker Compose is not available"
        echo ""
        if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
            gum style --foreground 214 "How to fix:"
            if [ "$OS_TYPE" = "macos" ]; then
                gum style --foreground 245 "  Docker Compose is included with Docker Desktop."
                gum style --foreground 245 "  Please update Docker Desktop to the latest version."
            else
                gum style --foreground 245 "  Install the plugin: sudo apt install docker-compose-plugin"
                gum style --foreground 245 "  Or standalone:      sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-linux-\$(uname -m) -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose"
            fi
        else
            echo "How to fix:"
            if [ "$OS_TYPE" = "macos" ]; then
                echo "  Docker Compose is included with Docker Desktop."
                echo "  Please update Docker Desktop to the latest version."
            else
                echo "  Install the plugin: sudo apt install docker-compose-plugin"
            fi
        fi
        exit 1
    fi

    return 0
}

check_ports() {
    local ports_in_use=""
    local port80_proc=""
    local port443_proc=""

    # Check if port 80 is in use (skip if we're updating an existing deployment)
    if [ "$ACTION" != "update" ]; then
        # Try to identify what's using the ports
        # Check for processes LISTENING on ports (not outbound connections)
        if command -v lsof &> /dev/null; then
            # -sTCP:LISTEN filters to only listening sockets
            port80_proc=$(lsof -iTCP:80 -sTCP:LISTEN -t 2>/dev/null | head -1) || true
            port443_proc=$(lsof -iTCP:443 -sTCP:LISTEN -t 2>/dev/null | head -1) || true
            if [ -n "$port80_proc" ]; then ports_in_use="80 $ports_in_use"; fi
            if [ -n "$port443_proc" ]; then ports_in_use="443 $ports_in_use"; fi
        elif command -v ss &> /dev/null; then
            # ss -tuln shows only listening sockets
            if ss -tuln | grep -q ':80 '; then ports_in_use="80 $ports_in_use"; fi
            if ss -tuln | grep -q ':443 '; then ports_in_use="443 $ports_in_use"; fi
        elif command -v netstat &> /dev/null; then
            # netstat -tuln shows only listening sockets
            if netstat -tuln 2>/dev/null | grep -q ':80 '; then ports_in_use="80 $ports_in_use"; fi
            if netstat -tuln 2>/dev/null | grep -q ':443 '; then ports_in_use="443 $ports_in_use"; fi
        fi

        if [ -n "$ports_in_use" ]; then
            tui_warn "Ports in use: $ports_in_use"
            echo ""

            # Try to identify the process
            local proc_info=""
            if [ -n "$port80_proc" ] && command -v ps &> /dev/null; then
                proc_info=$(ps -p "$port80_proc" -o comm= 2>/dev/null || echo "unknown")
                tui_info "Port 80 is used by: $proc_info (PID: $port80_proc)"
            fi
            if [ -n "$port443_proc" ] && command -v ps &> /dev/null; then
                proc_info=$(ps -p "$port443_proc" -o comm= 2>/dev/null || echo "unknown")
                tui_info "Port 443 is used by: $proc_info (PID: $port443_proc)"
            fi

            echo ""

            # Check if it's a previous CYROID deployment
            if docker ps 2>/dev/null | grep -q "cyroid\|traefik"; then
                tui_info "This looks like a previous CYROID deployment."
                echo ""
                if tui_confirm "Stop existing CYROID deployment and continue?"; then
                    tui_info "Stopping existing deployment..."
                    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down 2>/dev/null || true
                    sleep 2
                    tui_success "Previous deployment stopped"
                else
                    tui_info "Deployment cancelled"
                    exit 1
                fi
            else
                # Offer to show what to do
                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null && [ -t 0 ]; then
                    local choice
                    choice=$(gum choose --header "What would you like to do?" \
                        "Continue anyway (may fail)" \
                        "Show how to stop the service" \
                        "Cancel deployment")

                    case "$choice" in
                        "Continue"*)
                            tui_warn "Continuing - deployment may fail if ports are blocked"
                            ;;
                        "Show"*)
                            echo ""
                            gum style --foreground 214 "To free up ports, you can:"
                            echo ""
                            if [ -n "$port80_proc" ]; then
                                gum style --foreground 245 "  Stop process on port 80:  sudo kill $port80_proc"
                            fi
                            if [ -n "$port443_proc" ]; then
                                gum style --foreground 245 "  Stop process on port 443: sudo kill $port443_proc"
                            fi
                            gum style --foreground 245 "  Stop Apache:              sudo systemctl stop apache2"
                            gum style --foreground 245 "  Stop Nginx:               sudo systemctl stop nginx"
                            echo ""
                            tui_info "Run this script again after freeing the ports"
                            exit 1
                            ;;
                        *)
                            tui_info "Deployment cancelled"
                            exit 1
                            ;;
                    esac
                else
                    if ! tui_confirm "Continue anyway?"; then
                        echo ""
                        echo "To free up ports, try:"
                        echo "  sudo systemctl stop apache2"
                        echo "  sudo systemctl stop nginx"
                        if [ -n "$port80_proc" ]; then echo "  sudo kill $port80_proc"; fi
                        if [ -n "$port443_proc" ]; then echo "  sudo kill $port443_proc"; fi
                        exit 1
                    fi
                fi
            fi
        else
            tui_success "Ports 80 and 443 are available"
        fi
    fi

    return 0
}

check_data_dir_writable() {
    local parent_dir=$(dirname "$DATA_DIR")

    # Check if we can create the data directory
    if [ -d "$DATA_DIR" ]; then
        if [ ! -w "$DATA_DIR" ]; then
            log_error "Data directory $DATA_DIR exists but is not writable"
            log_info "Try: sudo chown -R \$(id -u):\$(id -g) $DATA_DIR"
            exit 1
        fi
    elif [ -d "$parent_dir" ]; then
        if [ ! -w "$parent_dir" ]; then
            log_warn "Cannot write to $parent_dir - will need sudo to create data directory"
        fi
    fi
}

backup_env_file() {
    if [ -f "$ENV_FILE" ]; then
        local backup="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$ENV_FILE" "$backup"
        log_info "Backed up existing config to $backup"
    fi
}

docker_compose_cmd() {
    if docker compose version &> /dev/null 2>&1; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

show_help() {
    echo "CYROID Production Deployment Script"
    echo ""
    echo "A full TUI for deploying and managing CYROID in production."
    echo "Uses 'gum' for beautiful terminal interfaces (auto-installs on macOS)."
    echo ""
    echo "Installation:"
    echo "  # Option 1: Git clone (recommended for updates)"
    echo "  git clone https://github.com/JongoDB/CYROID.git && cd CYROID"
    echo "  ./scripts/deploy.sh"
    echo ""
    echo "  # Option 2: Standalone (downloads required files automatically)"
    echo "  curl -fsSL https://raw.githubusercontent.com/JongoDB/CYROID/master/scripts/deploy.sh -o deploy.sh"
    echo "  bash deploy.sh"
    echo ""
    echo "Usage:"
    echo "  $0                                    Interactive TUI setup"
    echo "  $0 --domain example.com              Domain with Let's Encrypt"
    echo "  $0 --ip 192.168.1.100                IP with self-signed cert"
    echo "  $0 --update                          Update (interactive version)"
    echo "  $0 --start                           Start stopped deployment"
    echo "  $0 --stop                            Stop all services"
    echo "  $0 --restart                         Restart all services"
    echo "  $0 --status                          Show service status"
    echo ""
    echo "Lifecycle Commands:"
    echo "  --start            Start a stopped CYROID deployment"
    echo "  --stop             Stop all running services"
    echo "  --restart          Stop then start all services"
    echo "  --update           Update to new version (interactive selection)"
    echo "  --status           Show current status and health"
    echo ""
    echo "Deploy Options:"
    echo "  --domain DOMAIN    Domain name for the server"
    echo "  --ip IP            IP address for the server"
    echo "  --email EMAIL      Email for Let's Encrypt notifications"
    echo "  --ssl MODE         SSL mode: letsencrypt, selfsigned, manual"
    echo "  --version VER      CYROID version (default: interactive)"
    echo "  --data-dir DIR     Data directory (default: auto by OS)"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Interactive deployment (recommended)"
    echo "  $0"
    echo ""
    echo "  # Deploy with domain and Let's Encrypt"
    echo "  $0 --domain cyroid.example.com --email admin@example.com"
    echo ""
    echo "  # Update to specific version"
    echo "  $0 --update --version v0.30.0"
    echo ""
    echo "  # Check status"
    echo "  $0 --status"
}

# =============================================================================
# Deployment Functions
# =============================================================================

detect_os() {
    case "$(uname -s)" in
        Linux*)     OS_TYPE="linux" ;;
        Darwin*)    OS_TYPE="macos" ;;
        *)          OS_TYPE="unknown" ;;
    esac
    return 0
}

get_default_data_dir() {
    detect_os
    if [ "$OS_TYPE" = "macos" ]; then
        # macOS: use home directory since /data requires special setup
        echo "$HOME/.cyroid/data"
    else
        # Linux: use /data/cyroid (standard location)
        echo "/data/cyroid"
    fi
}

create_data_directories() {
    log_step "Creating data directories"

    detect_os

    # Check if we need sudo (can't write to parent directory)
    local parent_dir=$(dirname "$DATA_DIR")
    local need_sudo=false

    if [ ! -d "$DATA_DIR" ]; then
        if [ -d "$parent_dir" ] && [ ! -w "$parent_dir" ]; then
            need_sudo=true
        elif [ ! -d "$parent_dir" ]; then
            # Parent doesn't exist, check its parent
            local grandparent=$(dirname "$parent_dir")
            if [ ! -w "$grandparent" ]; then
                need_sudo=true
            fi
        fi
    fi

    # All directories needed by CYROID
    local dirs="iso-cache template-storage vm-storage shared catalogs scenarios images"

    if [ "$need_sudo" = true ]; then
        log_info "Need elevated permissions to create $DATA_DIR"
        sudo mkdir -p "$DATA_DIR"/{iso-cache,template-storage,vm-storage,shared,catalogs,scenarios,images}
        sudo chown -R "$(id -u):$(id -g)" "$DATA_DIR"
    else
        mkdir -p "$DATA_DIR"/{iso-cache,template-storage,vm-storage,shared,catalogs,scenarios,images}
    fi

    log_info "Data directory: $DATA_DIR"
    log_info "Operating system: $OS_TYPE"
}

create_env_file() {
    log_step "Configuring environment"

    # Determine address to use
    local address="${DOMAIN:-$IP}"

    # Determine SSL mode
    if [ -z "$SSL_MODE" ]; then
        if [ -n "$DOMAIN" ]; then
            SSL_MODE="letsencrypt"
        else
            SSL_MODE="selfsigned"
        fi
    fi

    # Generate secrets if needed
    local jwt_secret=""
    local pg_password=""
    local minio_password=""

    if [ -f "$ENV_FILE" ]; then
        # Load existing secrets
        source "$ENV_FILE" 2>/dev/null || true
        jwt_secret="${JWT_SECRET_KEY:-}"
        pg_password="${POSTGRES_PASSWORD:-}"
        minio_password="${MINIO_SECRET_KEY:-}"
    fi

    # Generate any missing secrets
    if [ -z "$jwt_secret" ]; then
        jwt_secret=$(generate_secret)
        log_info "Generated JWT secret"
    fi
    if [ -z "$pg_password" ]; then
        pg_password=$(generate_secret | head -c 32)
        log_info "Generated PostgreSQL password"
    fi
    if [ -z "$minio_password" ]; then
        minio_password=$(generate_secret | head -c 32)
        log_info "Generated MinIO password"
    fi

    # Set SSL resolver for Let's Encrypt
    local ssl_resolver=""
    if [ "$SSL_MODE" = "letsencrypt" ]; then
        ssl_resolver="letsencrypt"
    fi

    # Write environment file
    cat > "$ENV_FILE" << EOF
# CYROID Production Environment
# Generated by deploy.sh on $(date)

# Server Configuration
DOMAIN=$address
SSL_MODE=$SSL_MODE
SSL_RESOLVER=$ssl_resolver
ACME_EMAIL=${EMAIL:-admin@${address}}

# Secrets (auto-generated)
JWT_SECRET_KEY=$jwt_secret
POSTGRES_PASSWORD=$pg_password
MINIO_SECRET_KEY=$minio_password

# Settings
DEBUG=false
VERSION=$VERSION
CYROID_DATA_DIR=$DATA_DIR

# DinD Configuration
DIND_IMAGE=ghcr.io/jongodb/cyroid-dind:latest
DIND_STARTUP_TIMEOUT=60
DIND_DOCKER_PORT=2375

# Network Configuration
CYROID_MGMT_NETWORK=cyroid-mgmt
CYROID_MGMT_SUBNET=172.30.0.0/24
CYROID_RANGES_NETWORK=cyroid-ranges
CYROID_RANGES_SUBNET=172.30.1.0/24
EOF

    chmod 600 "$ENV_FILE"
    log_info "Environment file: $ENV_FILE"
    log_info "SSL Mode: $SSL_MODE"
}

setup_ssl() {
    log_step "Setting up SSL certificates"

    # Generate production Traefik config with correct email
    generate_traefik_config

    # Ensure directories exist (needed for docker-compose mounts)
    mkdir -p "$PROJECT_ROOT/certs"
    mkdir -p "$PROJECT_ROOT/acme"
    mkdir -p "$PROJECT_ROOT/traefik/dynamic"

    # Ensure acme.json exists with correct permissions
    if [ ! -f "$PROJECT_ROOT/acme/acme.json" ]; then
        touch "$PROJECT_ROOT/acme/acme.json"
        chmod 600 "$PROJECT_ROOT/acme/acme.json"
    fi

    # Create base traefik dynamic config if missing (defensive - should be in git)
    if [ ! -f "$PROJECT_ROOT/traefik/dynamic/base.yml" ]; then
        cat > "$PROJECT_ROOT/traefik/dynamic/base.yml" << 'BASEEOF'
# Base Traefik dynamic configuration
http:
  middlewares:
    secure-headers:
      headers:
        frameDeny: true
        sslRedirect: true
        browserXssFilter: true
        contentTypeNosniff: true
        referrerPolicy: "same-origin"
BASEEOF
    fi

    case "$SSL_MODE" in
        letsencrypt)
            log_info "Using Let's Encrypt for automatic certificates"
            log_info "Certificates will be obtained on first request"
            ;;

        selfsigned)
            log_info "Generating self-signed certificate"
            generate_self_signed_cert "${DOMAIN:-$IP}"
            ;;

        manual)
            if [ ! -f "$PROJECT_ROOT/certs/cert.pem" ] || [ ! -f "$PROJECT_ROOT/certs/key.pem" ]; then
                log_error "Manual SSL mode requires certificates in ./certs/"
                log_info "Please place your certificate files:"
                log_info "  - ./certs/cert.pem"
                log_info "  - ./certs/key.pem"
                exit 1
            fi
            log_info "Using manually provided certificates"
            ;;
    esac
}

generate_self_signed_cert() {
    local hostname="$1"
    local certs_dir="$PROJECT_ROOT/certs"

    # Check for openssl
    if ! command -v openssl &> /dev/null; then
        tui_error "OpenSSL is not installed (required for self-signed certificates)"
        echo ""
        if [ "$OS_TYPE" = "macos" ]; then
            tui_info "Install with: brew install openssl"
        else
            tui_info "Install with: sudo apt install openssl  OR  sudo dnf install openssl"
        fi
        exit 1
    fi

    # Determine if input is an IP address or domain
    local san cn
    if [[ "$hostname" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        san="IP:$hostname"
        cn="$hostname"
    else
        san="DNS:$hostname,DNS:*.$hostname"
        cn="$hostname"
    fi

    # Generate certificate (non-interactive, always overwrite)
    openssl req -x509 -nodes -days 365 \
        -newkey rsa:2048 \
        -keyout "$certs_dir/key.pem" \
        -out "$certs_dir/cert.pem" \
        -subj "/CN=$cn/O=CYROID/OU=Cyber Range" \
        -addext "subjectAltName=$san" \
        -addext "keyUsage=digitalSignature,keyEncipherment" \
        -addext "extendedKeyUsage=serverAuth" \
        2>/dev/null

    chmod 644 "$certs_dir/cert.pem"
    chmod 600 "$certs_dir/key.pem"

    log_info "Certificate generated for: $hostname"
}

generate_traefik_config() {
    local acme_email="${EMAIL:-admin@${DOMAIN:-$IP}}"
    local traefik_config="$PROJECT_ROOT/traefik-prod.yml"

    log_info "Generating Traefik production config"

    cat > "$traefik_config" << EOF
# Traefik Production Configuration (Generated by deploy.sh)
#
# Features:
# - ACME (Let's Encrypt) automatic certificate management
# - HTTP to HTTPS redirect
# - Dashboard disabled for security

api:
  insecure: false
  dashboard: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
          permanent: true
  websecure:
    address: ":443"

providers:
  docker:
    exposedByDefault: false
  file:
    directory: /etc/traefik/dynamic
    watch: true

certificatesResolvers:
  letsencrypt:
    acme:
      email: "$acme_email"
      storage: /etc/traefik/acme/acme.json
      httpChallenge:
        entryPoint: web

log:
  level: WARN
  format: common
EOF

    log_info "Traefik config generated with email: $acme_email"
}

init_networks() {
    log_step "Initializing Docker networks"

    # Create management network if not exists
    if ! docker network inspect cyroid-mgmt &>/dev/null; then
        log_info "Creating cyroid-mgmt network..."
        docker network create \
            --driver bridge \
            --subnet 172.30.0.0/24 \
            --gateway 172.30.0.1 \
            cyroid-mgmt
        log_info "Created cyroid-mgmt (172.30.0.0/24)"
    else
        log_info "cyroid-mgmt network already exists"
    fi

    # Create ranges network if not exists
    if ! docker network inspect cyroid-ranges &>/dev/null; then
        log_info "Creating cyroid-ranges network..."
        docker network create \
            --driver bridge \
            --subnet 172.30.1.0/24 \
            --gateway 172.30.1.1 \
            cyroid-ranges
        log_info "Created cyroid-ranges (172.30.1.0/24)"
    else
        log_info "cyroid-ranges network already exists"
    fi
}

pull_images() {
    cd "$PROJECT_ROOT"

    # Export env vars for docker-compose
    export $(grep -v '^#' "$ENV_FILE" | xargs) 2>/dev/null || true

    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    # Get list of images to show what we're pulling
    local images
    images=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml config 2>/dev/null | grep 'image:' | awk '{print $2}' | sort -u) || true

    if [ -n "$images" ]; then
        local total=$(echo "$images" | wc -l | tr -d ' ')
        echo ""
        tui_info "Pulling $total images:"
        echo "$images" | while read -r img; do
            local name=$(echo "$img" | sed 's/.*\///' | cut -d: -f1)
            echo "  - $name"
        done
        echo ""
    fi

    # Pull with docker compose (more reliable, handles auth, shows progress)
    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null && [ -t 0 ]; then
        # Use compose pull without -q to show progress, gum will capture it
        $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull 2>&1 | while read -r line; do
            # Show pull progress
            if echo "$line" | grep -q "Pull"; then
                echo "  $line"
            fi
        done
    else
        $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull
    fi
}

start_services() {
    cd "$PROJECT_ROOT"

    # Export env vars for docker-compose
    set -a
    source "$ENV_FILE"
    set +a

    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    # Start services (don't use gum spin - it can fail silently)
    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d 2>&1 | while read -r line; do
        if [ -n "$line" ]; then
            echo "  $line"
        fi
    done || true
}

wait_for_health() {
    tui_info "Waiting for services to be healthy..."

    local max_attempts=60
    local attempt=0
    local target_healthy=3  # Minimum healthy services needed

    while [ $attempt -lt $max_attempts ]; do
        local healthy_count=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
        local running_count=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "Up" || echo "0")

        # Update status bar with current health status
        tui_set_status "Waiting for services... ($healthy_count/$target_healthy healthy, $running_count running)" "progress"

        if [ "$healthy_count" -ge "$target_healthy" ]; then
            tui_set_status "All services healthy!" "success"
            tui_success "All services are healthy!"
            return 0
        fi

        attempt=$((attempt + 1))

        # Show dots in non-TUI mode
        if [ "$USE_TUI" != true ]; then
            echo -n "."
        fi

        sleep 2
    done

    echo ""
    tui_set_status "Some services may not be healthy" "warn"
    tui_warn "Some services may not be fully healthy yet"
    tui_info "Check status with: $0 --status"
    tui_info "View logs with: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
}

create_initial_admin() {
    # Create the initial admin user via API
    local address="${DOMAIN:-$IP}"
    local protocol="https"
    local api_url="${protocol}://${address}/api/v1/auth/register"

    # Default credentials
    local default_username="admin"
    local default_email="admin@cyroid.com"
    local default_password="password"

    echo ""
    tui_title "Step 5: Initial Admin User"
    echo ""

    # TUI input with defaults pre-filled
    local admin_username admin_email admin_password

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        admin_username=$(gum input --placeholder "admin" --value "$default_username" --header "Admin username:")
        admin_email=$(gum input --placeholder "admin@cyroid.com" --value "$default_email" --header "Admin email:")
        admin_password=$(gum input --placeholder "password" --value "$default_password" --password --header "Admin password:")
    else
        read -p "Admin username [$default_username]: " admin_username
        admin_username="${admin_username:-$default_username}"
        read -p "Admin email [$default_email]: " admin_email
        admin_email="${admin_email:-$default_email}"
        read -sp "Admin password [$default_password]: " admin_password
        admin_password="${admin_password:-$default_password}"
        echo ""
    fi

    # Use defaults if empty
    admin_username="${admin_username:-$default_username}"
    admin_email="${admin_email:-$default_email}"
    admin_password="${admin_password:-$default_password}"

    echo ""
    tui_info "Creating admin user: $admin_username ($admin_email)"

    # Wait a bit for API to be fully ready
    sleep 3

    # Call the register API (-k for self-signed certs)
    local response
    local http_code

    if command -v curl &> /dev/null; then
        response=$(curl -sk -w "\n%{http_code}" -X POST "$api_url" \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"$admin_username\",\"email\":\"$admin_email\",\"password\":\"$admin_password\"}" 2>/dev/null)
    elif command -v wget &> /dev/null; then
        response=$(wget -qO- --no-check-certificate --post-data="{\"username\":\"$admin_username\",\"email\":\"$admin_email\",\"password\":\"$admin_password\"}" \
            --header="Content-Type: application/json" "$api_url" 2>/dev/null)
        http_code="200"
    else
        tui_warn "Neither curl nor wget available - skipping admin user creation"
        tui_info "Register the first user through the web UI to become admin"
        return 0
    fi

    # Parse response (last line is http code from curl)
    if command -v curl &> /dev/null; then
        http_code=$(echo "$response" | tail -n1)
        response=$(echo "$response" | sed '$d')
    fi

    if [ "$http_code" = "201" ]; then
        tui_success "Admin user '$admin_username' created successfully!"

        # Store credentials for display
        ADMIN_USERNAME="$admin_username"
        ADMIN_EMAIL="$admin_email"
        ADMIN_PASSWORD="$admin_password"
    elif echo "$response" | grep -q "already registered"; then
        tui_warn "User already exists - skipping admin creation"
        tui_info "An admin user may have been created previously"
    else
        tui_warn "Could not create admin user automatically"
        tui_info "Register through the web UI - first user becomes admin"
        if [ -n "$response" ]; then
            tui_info "API response: $response"
        fi
    fi
}

show_access_info() {
    local address="${DOMAIN:-$IP}"
    local protocol="https"

    echo ""

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        local ssl_note=""
        if [ "$SSL_MODE" = "selfsigned" ]; then
            ssl_note="

Note: Using self-signed certificate.
      Browser will show a security warning.
      Click 'Advanced' → 'Proceed' to continue."
        fi

        local login_info=""
        if [ -n "$ADMIN_USERNAME" ]; then
            login_info="Login credentials:
  Username: $ADMIN_USERNAME
  Password: $ADMIN_PASSWORD"
        else
            login_info="First login:
  Register a new account
  First user becomes admin"
        fi

        gum style \
            --foreground 82 --border-foreground 82 --border double \
            --align center --width 60 --margin "1 2" --padding "1 2" \
            "🎉 CYROID Deployment Complete!

Access URL: ${protocol}://${address}

${login_info}${ssl_note}"

        echo ""
        gum style --foreground 245 "Useful commands:"
        echo ""
        gum style --foreground 39 "  View logs:  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
        gum style --foreground 39 "  Stop:       $0 --stop"
        gum style --foreground 39 "  Update:     $0 --update"
        gum style --foreground 39 "  Status:     $0 --status"
    else
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║${NC}            ${BOLD}CYROID Deployment Complete!${NC}                     ${GREEN}║${NC}"
        echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
        echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}  ${CYAN}Access URL:${NC}  ${protocol}://${address}                  ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
        if [ -n "$ADMIN_USERNAME" ]; then
        echo -e "${GREEN}║${NC}  ${CYAN}Login credentials:${NC}                                      ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}    Username: $ADMIN_USERNAME                                        ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}    Password: $ADMIN_PASSWORD                                     ${GREEN}║${NC}"
        else
        echo -e "${GREEN}║${NC}  ${CYAN}First login:${NC}                                           ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}    Register a new account - first user becomes admin      ${GREEN}║${NC}"
        fi
        echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
        if [ "$SSL_MODE" = "selfsigned" ]; then
        echo -e "${GREEN}║${NC}  ${YELLOW}Note:${NC} Using self-signed certificate.                    ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}        Browser will show a security warning.               ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}        Click 'Advanced' -> 'Proceed' to continue.          ${GREEN}║${NC}"
        echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
        fi
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo "Useful commands:"
        echo "  View logs:     docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
        echo "  Stop:          $0 --stop"
        echo "  Update:        $0 --update"
        echo "  Status:        $0 --status"
    fi
    echo ""
}

do_deploy() {
    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    # Check if CYROID is already running (check for env file + running containers from this project)
    if [ -f "$ENV_FILE" ]; then
        # Load env first so compose can work
        set -a
        source "$ENV_FILE" 2>/dev/null || true
        set +a

        local running_containers=""
        running_containers=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps -q 2>/dev/null | head -1) || true

        if [ -n "$running_containers" ]; then
            tui_clear
            tui_header

            tui_success "CYROID is already running!"
            echo ""

            # Get address from env
            local address="${DOMAIN:-$IP}"
            if [ -n "$address" ]; then
                tui_info "Access at: https://$address"
            fi

            # Go straight to management menu
            if [ -t 0 ]; then
                management_menu
            else
                tui_info "Use '$0 --stop' to stop services"
                tui_info "Use '$0 --status' to check status"
            fi
            return 0
        fi
    fi

    # If interactive mode, TUI header shown in interactive_setup
    # Otherwise show banner now
    if [ -n "$DOMAIN" ] || [ -n "$IP" ]; then
        tui_clear
        tui_header
    fi

    # Comprehensive pre-flight checks
    check_prerequisites

    # Detailed Docker check with auto-fix options
    check_docker

    check_ports

    # If no domain/IP specified, run interactive setup
    if [ -z "$DOMAIN" ] && [ -z "$IP" ]; then
        interactive_setup
    fi

    # Initialize full-screen TUI for deployment
    if [ "$USE_TUI" = true ]; then
        tui_init_fullscreen
        tui_set_status "Initializing deployment..." "info"
    fi

    tui_main_area
    tui_header
    tui_title "Deploying CYROID"
    echo ""

    # Pre-flight checks
    tui_set_status "Running pre-flight checks..." "progress"
    check_data_dir_writable
    backup_env_file

    # Create directories and config (Step 1/7)
    tui_set_progress "Creating data directories..." 14
    tui_info "Creating data directories..."
    create_data_directories
    tui_success "Data directories ready"

    # Generate config (Step 2/7)
    tui_set_progress "Generating configuration..." 28
    tui_info "Generating configuration..."
    create_env_file
    tui_success "Configuration saved"

    # Setup SSL (Step 3/7)
    tui_set_progress "Setting up SSL certificates..." 42
    tui_info "Setting up SSL certificates..."
    setup_ssl
    tui_success "SSL configured"

    # Init networks (Step 4/7)
    tui_set_progress "Initializing Docker networks..." 56
    tui_info "Initializing Docker networks..."
    init_networks
    tui_success "Networks ready"

    # Pull images (Step 5/7)
    tui_set_progress "Pulling Docker images..." 70
    tui_info "Pulling Docker images (this may take a while)..."
    pull_images
    tui_success "Images pulled"

    # Start services (Step 6/7)
    tui_set_progress "Starting services..." 85
    tui_info "Starting services..."
    start_services
    tui_success "Services started"

    # Wait for health (Step 7/7)
    tui_set_progress "Waiting for services to be healthy..." 92
    wait_for_health

    # Create initial admin user (final step)
    tui_set_progress "Creating admin user..." 98
    create_initial_admin

    # Deployment complete
    tui_set_status "Deployment complete!" "success"

    # Clean up fullscreen mode before showing access info
    if [ "$TUI_FULLSCREEN" = true ]; then
        tui_cleanup_fullscreen
    fi

    show_access_info

    # Show management menu if running interactively
    if [ -t 0 ]; then
        management_menu
    fi
}

management_menu() {
    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    while true; do
        echo ""
        if [ "$USE_TUI" = true ] && command -v gum &> /dev/null && [ -t 0 ]; then
            local choice
            choice=$(gum choose --header "What would you like to do?" \
                "Live Dashboard (auto-refresh)" \
                "View logs" \
                "Show status" \
                "Restart services" \
                "Stop services" \
                "Clean up (stop + remove data)" \
                "Exit")

            case "$choice" in
                "Live Dashboard"*)
                    tui_live_dashboard "$compose_cmd"
                    ;;
                "View logs")
                    clear
                    gum style --background 214 --foreground 0 --bold --padding "0 2" " Press Ctrl+C to exit and return to menu "
                    echo ""
                    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=50 || true
                    echo ""
                    tui_success "Returned to menu"
                    sleep 1
                    ;;
                "Show status")
                    echo ""
                    tui_title "Service Status"
                    echo ""
                    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps
                    echo ""
                    local healthy=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
                    local running=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "Up" || echo "0")
                    tui_info "Running: $running | Healthy: $healthy"
                    ;;
                "Restart services")
                    echo ""
                    tui_info "Restarting services..."
                    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml restart
                    tui_success "Services restarted"
                    wait_for_health
                    ;;
                "Stop services")
                    echo ""
                    if gum confirm "Stop all CYROID services?"; then
                        tui_info "Stopping services..."
                        $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down
                        tui_success "Services stopped"
                        echo ""
                        tui_info "Run '$0 --start' to start again"
                        break
                    fi
                    ;;
                "Clean up"*)
                    echo ""
                    tui_warn "This will stop all services and DELETE all data!"
                    echo ""

                    # Show what will be removed
                    tui_title "The following will be removed:"
                    echo ""

                    # List running containers
                    local containers=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps --format "{{.Names}}" 2>/dev/null) || true
                    if [ -n "$containers" ]; then
                        echo "  CYROID Services:"
                        echo "$containers" | while read -r c; do echo "    - $c"; done
                        echo ""
                    fi

                    # List volumes
                    local volumes=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml config --volumes 2>/dev/null) || true
                    if [ -n "$volumes" ]; then
                        echo "  Docker volumes:"
                        echo "$volumes" | while read -r v; do echo "    - $v"; done
                        echo ""
                    fi

                    # Detect deployed ranges (DinD containers and range networks)
                    local range_containers=$(docker ps -a --filter "label=cyroid.type=dind" --format "{{.Names}}" 2>/dev/null) || true
                    local range_networks=$(docker network ls --filter "name=range-" --format "{{.Name}}" 2>/dev/null) || true
                    local cyroid_networks=$(docker network ls --filter "name=cyroid-" --format "{{.Name}}" 2>/dev/null) || true

                    local has_ranges=false
                    if [ -n "$range_containers" ] || [ -n "$range_networks" ]; then
                        has_ranges=true
                        echo "  Deployed Ranges detected:"
                        if [ -n "$range_containers" ]; then
                            local range_count=$(echo "$range_containers" | wc -l | tr -d ' ')
                            echo "    - $range_count range container(s)"
                        fi
                        if [ -n "$range_networks" ]; then
                            local net_count=$(echo "$range_networks" | wc -l | tr -d ' ')
                            echo "    - $net_count range network(s)"
                        fi
                        echo ""
                    fi

                    # Data directory with size
                    if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
                        local data_size=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1) || data_size="unknown"
                        echo "  Data directory:"
                        echo "    - $DATA_DIR ($data_size)"
                        echo ""
                    fi

                    # Config files
                    echo "  Configuration files:"
                    if [ -f "$ENV_FILE" ]; then
                        echo "    - $ENV_FILE"
                    fi
                    if [ -f "$PROJECT_ROOT/traefik/acme.json" ]; then
                        echo "    - $PROJECT_ROOT/traefik/acme.json (SSL certificates)"
                    fi
                    if [ -d "$PROJECT_ROOT/traefik/certs" ]; then
                        echo "    - $PROJECT_ROOT/traefik/certs/ (SSL certificates)"
                    fi
                    echo ""

                    # Ask about ranges if they exist
                    local delete_ranges=false
                    if [ "$has_ranges" = true ]; then
                        echo ""
                        if gum confirm --affirmative="Yes, delete ranges too" --negative="Keep ranges" "Also delete all deployed ranges and their networks?"; then
                            delete_ranges=true
                            tui_warn "Ranges will also be deleted!"
                        else
                            tui_info "Ranges will be preserved"
                        fi
                        echo ""
                    fi

                    if gum confirm --affirmative="Yes, delete everything" --negative="Cancel" "Are you sure? This cannot be undone."; then
                        # Delete ranges first if requested
                        if [ "$delete_ranges" = true ]; then
                            tui_info "Stopping and removing deployed ranges..."

                            # Stop and remove range containers (DinD)
                            if [ -n "$range_containers" ]; then
                                echo "$range_containers" | while read -r container; do
                                    if [ -n "$container" ]; then
                                        tui_info "  Removing range: $container"
                                        docker stop "$container" 2>/dev/null || true
                                        docker rm -f "$container" 2>/dev/null || true
                                    fi
                                done
                            fi

                            # Also catch any dind- prefixed containers
                            local dind_containers=$(docker ps -a --filter "name=dind-" --format "{{.Names}}" 2>/dev/null) || true
                            if [ -n "$dind_containers" ]; then
                                echo "$dind_containers" | while read -r container; do
                                    if [ -n "$container" ]; then
                                        tui_info "  Removing DinD container: $container"
                                        docker stop "$container" 2>/dev/null || true
                                        docker rm -f "$container" 2>/dev/null || true
                                    fi
                                done
                            fi

                            # Remove range networks
                            if [ -n "$range_networks" ]; then
                                echo "$range_networks" | while read -r network; do
                                    if [ -n "$network" ]; then
                                        tui_info "  Removing network: $network"
                                        docker network rm "$network" 2>/dev/null || true
                                    fi
                                done
                            fi

                            tui_success "Deployed ranges removed"
                        fi

                        tui_info "Stopping CYROID services..."
                        $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down -v
                        tui_success "Services stopped and volumes removed"

                        # Remove CYROID management networks
                        if [ -n "$cyroid_networks" ]; then
                            tui_info "Removing CYROID networks..."
                            echo "$cyroid_networks" | while read -r network; do
                                if [ -n "$network" ]; then
                                    docker network rm "$network" 2>/dev/null || true
                                fi
                            done
                            tui_success "CYROID networks removed"
                        fi

                        if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
                            tui_info "Removing data directory: $DATA_DIR"
                            rm -rf "$DATA_DIR" 2>/dev/null || sudo rm -rf "$DATA_DIR"
                            tui_success "Data directory removed"
                        fi

                        if [ -f "$ENV_FILE" ]; then
                            rm -f "$ENV_FILE"
                            tui_success "Configuration removed"
                        fi

                        # Clean up traefik certs
                        rm -f "$PROJECT_ROOT/traefik/acme.json" 2>/dev/null || true
                        rm -rf "$PROJECT_ROOT/traefik/certs" 2>/dev/null || true

                        echo ""
                        tui_success "Cleanup complete"
                        break
                    fi
                    ;;
                "Exit"|"")
                    echo ""
                    tui_info "CYROID is still running in the background"
                    tui_info "Use '$0 --stop' to stop services"
                    break
                    ;;
            esac
        else
            # Non-TUI fallback
            echo ""
            echo "Management Menu:"
            echo "  1) View logs"
            echo "  2) Show status"
            echo "  3) Restart services"
            echo "  4) Stop services"
            echo "  5) Clean up (stop + remove data)"
            echo "  6) Exit"
            echo ""
            read -p "Choice [1-6]: " choice

            case "$choice" in
                1)
                    echo ""
                    echo "Showing logs (Ctrl+C to stop)..."
                    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=50 || true
                    ;;
                2)
                    echo ""
                    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps
                    ;;
                3)
                    echo ""
                    echo "Restarting services..."
                    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml restart
                    echo "Services restarted"
                    ;;
                4)
                    echo ""
                    read -p "Stop all services? [y/N]: " confirm
                    if [[ "$confirm" =~ ^[Yy] ]]; then
                        $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down
                        echo "Services stopped"
                        break
                    fi
                    ;;
                5)
                    echo ""
                    echo "WARNING: This will delete all data!"
                    echo ""
                    echo "The following will be removed:"
                    echo ""

                    # List containers
                    local containers=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps --format "{{.Names}}" 2>/dev/null) || true
                    if [ -n "$containers" ]; then
                        echo "  CYROID Services:"
                        echo "$containers" | while read -r c; do echo "    - $c"; done
                        echo ""
                    fi

                    # List volumes
                    local volumes=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml config --volumes 2>/dev/null) || true
                    if [ -n "$volumes" ]; then
                        echo "  Docker volumes:"
                        echo "$volumes" | while read -r v; do echo "    - $v"; done
                        echo ""
                    fi

                    # Detect deployed ranges
                    local range_containers=$(docker ps -a --filter "label=cyroid.type=dind" --format "{{.Names}}" 2>/dev/null) || true
                    local range_networks=$(docker network ls --filter "name=range-" --format "{{.Name}}" 2>/dev/null) || true
                    local cyroid_networks=$(docker network ls --filter "name=cyroid-" --format "{{.Name}}" 2>/dev/null) || true

                    local has_ranges=false
                    if [ -n "$range_containers" ] || [ -n "$range_networks" ]; then
                        has_ranges=true
                        echo "  Deployed Ranges detected:"
                        if [ -n "$range_containers" ]; then
                            local range_count=$(echo "$range_containers" | wc -l | tr -d ' ')
                            echo "    - $range_count range container(s)"
                        fi
                        if [ -n "$range_networks" ]; then
                            local net_count=$(echo "$range_networks" | wc -l | tr -d ' ')
                            echo "    - $net_count range network(s)"
                        fi
                        echo ""
                    fi

                    # Data directory
                    if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
                        local data_size=$(du -sh "$DATA_DIR" 2>/dev/null | cut -f1) || data_size="unknown"
                        echo "  Data directory:"
                        echo "    - $DATA_DIR ($data_size)"
                        echo ""
                    fi

                    # Config
                    echo "  Configuration files:"
                    [ -f "$ENV_FILE" ] && echo "    - $ENV_FILE"
                    [ -f "$PROJECT_ROOT/traefik/acme.json" ] && echo "    - $PROJECT_ROOT/traefik/acme.json"
                    [ -d "$PROJECT_ROOT/traefik/certs" ] && echo "    - $PROJECT_ROOT/traefik/certs/"
                    echo ""

                    # Ask about ranges
                    local delete_ranges=false
                    if [ "$has_ranges" = true ]; then
                        read -p "Also delete all deployed ranges? [y/N]: " range_confirm
                        if [[ "$range_confirm" =~ ^[Yy] ]]; then
                            delete_ranges=true
                            echo "Ranges will also be deleted."
                        fi
                        echo ""
                    fi

                    read -p "Type 'DELETE' to confirm: " confirm
                    if [ "$confirm" = "DELETE" ]; then
                        # Delete ranges first if requested
                        if [ "$delete_ranges" = true ]; then
                            echo "Removing deployed ranges..."

                            # Stop and remove range containers
                            if [ -n "$range_containers" ]; then
                                echo "$range_containers" | while read -r container; do
                                    [ -n "$container" ] && docker rm -f "$container" 2>/dev/null || true
                                done
                            fi

                            # Also catch dind- prefixed containers
                            local dind_containers=$(docker ps -a --filter "name=dind-" --format "{{.Names}}" 2>/dev/null) || true
                            if [ -n "$dind_containers" ]; then
                                echo "$dind_containers" | while read -r container; do
                                    [ -n "$container" ] && docker rm -f "$container" 2>/dev/null || true
                                done
                            fi

                            # Remove range networks
                            if [ -n "$range_networks" ]; then
                                echo "$range_networks" | while read -r network; do
                                    [ -n "$network" ] && docker network rm "$network" 2>/dev/null || true
                                done
                            fi

                            echo "Ranges removed"
                        fi

                        $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down -v

                        # Remove CYROID networks
                        if [ -n "$cyroid_networks" ]; then
                            echo "$cyroid_networks" | while read -r network; do
                                [ -n "$network" ] && docker network rm "$network" 2>/dev/null || true
                            done
                        fi

                        if [ -n "$DATA_DIR" ] && [ -d "$DATA_DIR" ]; then
                            rm -rf "$DATA_DIR" 2>/dev/null || sudo rm -rf "$DATA_DIR"
                        fi
                        rm -f "$ENV_FILE" 2>/dev/null || true
                        rm -f "$PROJECT_ROOT/traefik/acme.json" 2>/dev/null || true
                        rm -rf "$PROJECT_ROOT/traefik/certs" 2>/dev/null || true
                        echo "Cleanup complete"
                        break
                    fi
                    ;;
                6|"")
                    echo ""
                    echo "CYROID is still running. Use '$0 --stop' to stop."
                    break
                    ;;
            esac
        fi
    done
}

get_current_version() {
    # Try to get current version from env file or running containers
    if [ -f "$ENV_FILE" ]; then
        grep "^VERSION=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "unknown"
    else
        echo "unknown"
    fi
}

get_available_releases() {
    # Fetch releases from GitHub API
    if command -v curl &> /dev/null; then
        curl -s "https://api.github.com/repos/JongoDB/CYROID/releases?per_page=10" 2>/dev/null | \
            grep '"tag_name"' | sed 's/.*"tag_name": "\(.*\)".*/\1/' | head -10
    elif command -v wget &> /dev/null; then
        wget -qO- "https://api.github.com/repos/JongoDB/CYROID/releases?per_page=10" 2>/dev/null | \
            grep '"tag_name"' | sed 's/.*"tag_name": "\(.*\)".*/\1/' | head -10
    fi
}

get_available_tags() {
    # Fetch tags from GitHub API
    if command -v curl &> /dev/null; then
        curl -s "https://api.github.com/repos/JongoDB/CYROID/tags?per_page=15" 2>/dev/null | \
            grep '"name"' | sed 's/.*"name": "\(.*\)".*/\1/' | head -15
    elif command -v wget &> /dev/null; then
        wget -qO- "https://api.github.com/repos/JongoDB/CYROID/tags?per_page=15" 2>/dev/null | \
            grep '"name"' | sed 's/.*"name": "\(.*\)".*/\1/' | head -15
    fi
}

select_version_interactive() {
    # Interactive version selection - sets VERSION variable
    # Returns the selected version

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        tui_info "Fetching available versions from GitHub..."
        echo ""

        local releases=$(get_available_releases)
        local tags=$(get_available_tags)

        if [ -n "$releases" ] || [ -n "$tags" ]; then
            # Get the latest version to display
            local latest_version=""
            if [ -n "$releases" ]; then
                latest_version=$(echo "$releases" | head -1)
            elif [ -n "$tags" ]; then
                latest_version=$(echo "$tags" | head -1)
            fi

            local latest_label="Latest (recommended)"
            if [ -n "$latest_version" ]; then
                latest_label="Latest (recommended) - $latest_version"
            fi

            local version_choice
            version_choice=$(gum choose --header "Select version to deploy:" \
                "$latest_label" \
                "Choose from releases" \
                "Choose from all tags" \
                "Enter version manually")

            case "$version_choice" in
                "Latest"*)
                    VERSION="latest"
                    tui_success "Using latest version${latest_version:+ ($latest_version)}"
                    ;;
                "Choose from releases"*)
                    if [ -n "$releases" ]; then
                        # Show releases with gum choose
                        echo ""
                        tui_info "Available releases:"
                        VERSION=$(echo "$releases" | gum choose --header "Select a release:")
                        if [ -n "$VERSION" ]; then
                            tui_success "Selected: $VERSION"
                        else
                            VERSION="latest"
                            tui_warn "No selection made, using latest"
                        fi
                    else
                        tui_warn "No releases found, using latest"
                        VERSION="latest"
                    fi
                    ;;
                "Choose from all tags"*)
                    if [ -n "$tags" ]; then
                        echo ""
                        tui_info "Available tags:"
                        VERSION=$(echo "$tags" | gum choose --header "Select a tag:")
                        if [ -n "$VERSION" ]; then
                            tui_success "Selected: $VERSION"
                        else
                            VERSION="latest"
                            tui_warn "No selection made, using latest"
                        fi
                    else
                        tui_warn "No tags found, using latest"
                        VERSION="latest"
                    fi
                    ;;
                "Enter"*)
                    VERSION=$(gum input --placeholder "v0.32.0" --header "Enter version (e.g., v0.32.0):")
                    if [ -z "$VERSION" ]; then
                        VERSION="latest"
                        tui_warn "No version entered, using latest"
                    else
                        tui_success "Using version: $VERSION"
                    fi
                    ;;
                *)
                    VERSION="latest"
                    ;;
            esac
        else
            tui_warn "Could not fetch versions from GitHub"
            tui_info "Using latest version"
            VERSION="latest"
        fi
    else
        # Non-TUI fallback
        echo "Version options:"
        echo "  1) Latest (recommended)"
        echo "  2) Enter specific version"
        echo ""
        read -p "Choice [1]: " choice

        case "$choice" in
            2)
                read -p "Enter version (e.g., v0.32.0): " VERSION
                VERSION="${VERSION:-latest}"
                ;;
            *)
                VERSION="latest"
                ;;
        esac
        echo "Using version: $VERSION"
    fi

    echo "$VERSION"
}

do_update() {
    check_gum
    tui_clear
    tui_header

    tui_title "Update CYROID"
    echo ""

    check_docker

    if [ ! -f "$ENV_FILE" ]; then
        tui_error "No existing deployment found"
        tui_info "Run without --update for initial setup"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    # Load environment
    set -a
    source "$ENV_FILE"
    set +a

    # Show current version
    local current_version=$(get_current_version)
    tui_info "Current version: $current_version"
    echo ""

    # Determine target version
    local target_version="$VERSION"

    if [ -z "$target_version" ] || [ "$target_version" = "latest" ]; then
        # Interactive version selection
        if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
            tui_info "Fetching available versions..."

            local releases=$(get_available_releases)
            local tags=$(get_available_tags)

            if [ -n "$releases" ] || [ -n "$tags" ]; then
                local version_choice
                version_choice=$(gum choose --header "Select version to install:" \
                    "Latest (newest release)" \
                    "Choose from releases" \
                    "Choose from tags" \
                    "Enter version manually")

                case "$version_choice" in
                    "Latest"*)
                        target_version="latest"
                        ;;
                    "Choose from releases"*)
                        if [ -n "$releases" ]; then
                            target_version=$(echo "$releases" | gum choose --header "Select release:")
                        else
                            tui_warn "No releases found, using latest"
                            target_version="latest"
                        fi
                        ;;
                    "Choose from tags"*)
                        if [ -n "$tags" ]; then
                            target_version=$(echo "$tags" | gum choose --header "Select tag:")
                        else
                            tui_warn "No tags found, using latest"
                            target_version="latest"
                        fi
                        ;;
                    "Enter"*)
                        target_version=$(gum input --placeholder "v0.30.0" --header "Enter version:")
                        ;;
                    *)
                        target_version="latest"
                        ;;
                esac
            else
                tui_warn "Could not fetch versions from GitHub, using latest"
                target_version="latest"
            fi
        else
            target_version="latest"
        fi
    fi

    echo ""
    tui_info "Target version: $target_version"
    echo ""

    if ! tui_confirm "Proceed with update?"; then
        tui_info "Update cancelled"
        exit 0
    fi

    echo ""

    # Update VERSION in env file
    if [ "$target_version" != "latest" ]; then
        sed -i.bak "s/^VERSION=.*/VERSION=$target_version/" "$ENV_FILE" 2>/dev/null || \
            sed -i '' "s/^VERSION=.*/VERSION=$target_version/" "$ENV_FILE"
        export VERSION="$target_version"
    fi

    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    # Pull images
    tui_info "Pulling Docker images..."
    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull 2>&1 || true
    tui_success "Images pulled"

    # Restart services
    tui_info "Restarting services..."
    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d 2>&1 || true
    tui_success "Services restarted"

    wait_for_health

    echo ""
    tui_success "Update complete! Now running: $target_version"
    echo ""
}

do_start() {
    check_gum
    tui_clear
    tui_header

    tui_title "Start CYROID"
    echo ""

    check_docker

    if [ ! -f "$ENV_FILE" ]; then
        tui_error "No existing deployment found"
        tui_info "Run without --start for initial setup"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    # Load environment
    set -a
    source "$ENV_FILE"
    set +a

    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    tui_info "Starting CYROID services..."
    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d 2>&1 || true

    wait_for_health

    local address="${DOMAIN:-$IP}"
    [ -z "$address" ] && address=$(grep "^DOMAIN=" "$ENV_FILE" | cut -d= -f2)

    echo ""
    tui_success "CYROID is running!"
    tui_info "Access at: https://$address"
    echo ""
}

do_stop() {
    check_gum
    tui_clear
    tui_header

    tui_title "Stop CYROID"
    echo ""

    cd "$PROJECT_ROOT"

    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    # Determine docker compose command
    local compose_cmd="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        compose_cmd="docker-compose"
    fi

    # Check if anything is running
    local running=$($compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps -q 2>/dev/null | wc -l | tr -d ' ')

    if [ "$running" = "0" ]; then
        tui_info "CYROID is not currently running"
        exit 0
    fi

    tui_info "Found $running running containers"
    echo ""

    if ! tui_confirm "Stop all CYROID services?"; then
        tui_info "Cancelled"
        exit 0
    fi

    echo ""
    tui_info "Stopping services..."
    $compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down 2>&1 || true
    tui_success "All services stopped"
    echo ""
}

do_status() {
    check_gum
    tui_clear
    tui_header

    tui_title "CYROID Status"
    echo ""

    cd "$PROJECT_ROOT"

    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a

        local current_version=$(get_current_version)
        local address=$(grep "^DOMAIN=" "$ENV_FILE" | cut -d= -f2)

        tui_info "Version: $current_version"
        tui_info "Address: https://$address"
        echo ""
    fi

    tui_title "Services"
    echo ""

    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps

    echo ""

    # Show health summary
    local total=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps -q 2>/dev/null | wc -l | tr -d ' ')
    local healthy=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
    local running=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "Up" || echo "0")

    if [ "$total" = "0" ]; then
        tui_warn "CYROID is not running"
        tui_info "Start with: $0 --start"
    elif [ "$healthy" -ge 3 ]; then
        tui_success "All core services healthy ($healthy/$total)"
    else
        tui_warn "Some services may have issues ($healthy healthy, $running running of $total)"
        tui_info "View logs: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
    fi
    echo ""
}

interactive_setup() {
    # Check for TUI support
    check_gum

    # Step tracking for back navigation
    local current_step=1
    local max_step=5  # 1=Access, 2=SSL, 3=Data, 4=Version, 5=Summary
    local access_type=""  # "domain" or "ip"

    while [ $current_step -le $max_step ]; do
        tui_clear
        tui_header

        if [ "$USE_TUI" = true ]; then
            gum style --foreground 245 "This wizard will configure CYROID for production use."
            gum style --foreground 245 --italic "Use '← Back' option to return to previous step."
            echo ""
        else
            echo "This wizard will configure CYROID for production use."
            echo ""
        fi

        case $current_step in
            1)
                # Step 1: Access method
                tui_title "Step 1: Server Access"
                echo ""

                local access_choice
                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
                    access_choice=$(gum choose --header "How will users access CYROID?" \
                        "IP address (e.g., 0.0.0.0)" \
                        "Domain name (e.g., cyroid.example.com)")
                else
                    access_choice=$(tui_choose "How will users access CYROID?" \
                        "IP address (e.g., 0.0.0.0)" \
                        "Domain name (e.g., cyroid.example.com)")
                fi

                case "$access_choice" in
                    "IP address"*)
                        access_type="ip"
                        echo ""
                        local input_ip
                        input_ip=$(tui_input "Enter server IP address:" "0.0.0.0" "${IP:-0.0.0.0}")
                        if [ -z "$input_ip" ]; then
                            tui_error "IP address cannot be empty"
                            sleep 1
                            continue
                        fi
                        IP="$input_ip"
                        DOMAIN=""
                        SSL_MODE="selfsigned"
                        current_step=3  # Skip SSL step for IP (always self-signed)
                        ;;
                    "Domain name"*)
                        access_type="domain"
                        echo ""
                        local input_domain
                        input_domain=$(tui_input "Enter your domain name:" "cyroid.example.com" "${DOMAIN:-}")
                        if [ -z "$input_domain" ]; then
                            tui_error "Domain name cannot be empty"
                            sleep 1
                            continue
                        fi
                        DOMAIN="$input_domain"
                        IP=""
                        current_step=2
                        ;;
                    *)
                        tui_error "Invalid choice"
                        sleep 1
                        continue
                        ;;
                esac
                ;;

            2)
                # Step 2: SSL Certificate (only for domain)
                tui_title "Step 2: SSL Certificate"
                echo ""

                local ssl_choice
                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
                    ssl_choice=$(gum choose --header "Choose SSL certificate type:" \
                        "Let's Encrypt (automatic, free, requires public domain)" \
                        "Self-signed (works immediately, browser warning)" \
                        "← Back")
                else
                    ssl_choice=$(tui_choose "Choose SSL certificate type:" \
                        "Let's Encrypt (automatic, free, requires public domain)" \
                        "Self-signed (works immediately, browser warning)" \
                        "← Back")
                fi

                case "$ssl_choice" in
                    "← Back"*)
                        current_step=1
                        continue
                        ;;
                    "Let's Encrypt"*)
                        SSL_MODE="letsencrypt"
                        echo ""
                        EMAIL=$(tui_input "Email for Let's Encrypt notifications:" "admin@$DOMAIN" "${EMAIL:-admin@$DOMAIN}")
                        current_step=3
                        ;;
                    "Self-signed"*)
                        SSL_MODE="selfsigned"
                        EMAIL=""
                        current_step=3
                        ;;
                    *)
                        continue
                        ;;
                esac
                ;;

            3)
                # Step 3: Data directory
                tui_title "Step 3: Data Storage"
                echo ""

                if [ -z "$DATA_DIR" ]; then
                    DATA_DIR=$(get_default_data_dir)
                fi

                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
                    # Show back option first
                    local data_choice
                    data_choice=$(gum choose --header "Configure data storage location:" \
                        "Use default: $DATA_DIR" \
                        "Enter custom path" \
                        "← Back")

                    case "$data_choice" in
                        "← Back"*)
                            if [ "$access_type" = "ip" ]; then
                                current_step=1  # IP skips SSL step
                            else
                                current_step=2
                            fi
                            continue
                            ;;
                        "Use default"*)
                            # Keep default DATA_DIR
                            current_step=4
                            ;;
                        "Enter custom"*)
                            local input_data_dir
                            input_data_dir=$(gum input --placeholder "$DATA_DIR" --value "$DATA_DIR" --header "Data directory for CYROID storage:")
                            if [ -n "$input_data_dir" ]; then
                                DATA_DIR="$input_data_dir"
                            fi
                            current_step=4
                            ;;
                        *)
                            continue
                            ;;
                    esac
                else
                    local input_data_dir
                    input_data_dir=$(tui_input "Data directory for CYROID storage:" "$DATA_DIR" "$DATA_DIR")
                    if [ -n "$input_data_dir" ]; then
                        DATA_DIR="$input_data_dir"
                    fi
                    current_step=4
                fi
                ;;

            4)
                # Step 4: Version selection
                tui_title "Step 4: Version Selection"
                echo ""

                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
                    tui_info "Fetching available versions from GitHub..."
                    echo ""

                    local releases=$(get_available_releases)
                    local tags=$(get_available_tags)

                    # Get the latest version to display
                    local latest_version=""
                    if [ -n "$releases" ]; then
                        latest_version=$(echo "$releases" | head -1)
                    elif [ -n "$tags" ]; then
                        latest_version=$(echo "$tags" | head -1)
                    fi

                    local latest_label="Latest (recommended)"
                    if [ -n "$latest_version" ]; then
                        latest_label="Latest (recommended) - $latest_version"
                    fi

                    local version_choice
                    version_choice=$(gum choose --header "Select version to deploy:" \
                        "$latest_label" \
                        "Choose from releases" \
                        "Choose from all tags" \
                        "Enter version manually" \
                        "← Back")

                    case "$version_choice" in
                        "← Back"*)
                            current_step=3
                            continue
                            ;;
                        "Latest"*)
                            VERSION="latest"
                            tui_success "Using latest version${latest_version:+ ($latest_version)}"
                            sleep 1
                            current_step=5
                            ;;
                        "Choose from releases"*)
                            if [ -n "$releases" ]; then
                                echo ""
                                # Add back option to releases list
                                local release_choice
                                release_choice=$(echo -e "← Back\n$releases" | gum choose --header "Select a release:")
                                if [ "$release_choice" = "← Back" ]; then
                                    continue
                                elif [ -n "$release_choice" ]; then
                                    VERSION="$release_choice"
                                    tui_success "Selected: $VERSION"
                                    sleep 1
                                    current_step=5
                                else
                                    continue
                                fi
                            else
                                tui_warn "No releases found"
                                sleep 1
                                continue
                            fi
                            ;;
                        "Choose from all tags"*)
                            if [ -n "$tags" ]; then
                                echo ""
                                local tag_choice
                                tag_choice=$(echo -e "← Back\n$tags" | gum choose --header "Select a tag:")
                                if [ "$tag_choice" = "← Back" ]; then
                                    continue
                                elif [ -n "$tag_choice" ]; then
                                    VERSION="$tag_choice"
                                    tui_success "Selected: $VERSION"
                                    sleep 1
                                    current_step=5
                                else
                                    continue
                                fi
                            else
                                tui_warn "No tags found"
                                sleep 1
                                continue
                            fi
                            ;;
                        "Enter"*)
                            VERSION=$(gum input --placeholder "v0.32.0" --header "Enter version (e.g., v0.32.0):")
                            if [ -z "$VERSION" ]; then
                                VERSION="latest"
                            fi
                            tui_success "Using version: $VERSION"
                            sleep 1
                            current_step=5
                            ;;
                        *)
                            continue
                            ;;
                    esac
                else
                    # Non-TUI fallback
                    echo "Version options:"
                    echo "  1) Latest (recommended)"
                    echo "  2) Enter specific version"
                    echo "  b) Back"
                    echo ""
                    read -p "Choice [1]: " choice

                    case "$choice" in
                        b|B)
                            current_step=3
                            continue
                            ;;
                        2)
                            read -p "Enter version (e.g., v0.32.0): " VERSION
                            VERSION="${VERSION:-latest}"
                            current_step=5
                            ;;
                        *)
                            VERSION="latest"
                            current_step=5
                            ;;
                    esac
                fi
                ;;

            5)
                # Summary
                tui_title "Configuration Summary"

                local version_display="$VERSION"
                if [ "$VERSION" = "latest" ]; then
                    version_display="latest (newest)"
                fi

                local summary="Address:     ${DOMAIN:-$IP}
SSL Mode:    $SSL_MODE
Data Dir:    $DATA_DIR
Version:     $version_display"

                if [ -n "$EMAIL" ]; then
                    summary="$summary
Email:       $EMAIL"
                fi

                tui_summary_box "$summary"

                echo ""

                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
                    local confirm_choice
                    confirm_choice=$(gum choose --header "Ready to deploy?" \
                        "Yes, proceed with deployment" \
                        "← Back to version selection" \
                        "Cancel deployment")

                    case "$confirm_choice" in
                        "Yes"*)
                            current_step=6  # Exit loop
                            ;;
                        "← Back"*)
                            current_step=4
                            continue
                            ;;
                        "Cancel"*)
                            tui_info "Deployment cancelled"
                            exit 0
                            ;;
                        *)
                            continue
                            ;;
                    esac
                else
                    echo "Options:"
                    echo "  1) Proceed with deployment"
                    echo "  b) Back"
                    echo "  c) Cancel"
                    read -p "Choice [1]: " choice

                    case "$choice" in
                        b|B)
                            current_step=4
                            continue
                            ;;
                        c|C)
                            echo "Deployment cancelled"
                            exit 0
                            ;;
                        *)
                            current_step=6  # Exit loop
                            ;;
                    esac
                fi
                ;;
        esac
    done

    tui_clear
}

# =============================================================================
# Main
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --ip)
            IP="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --ssl)
            SSL_MODE="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --update)
            ACTION="update"
            shift
            ;;
        --start)
            ACTION="start"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --restart)
            ACTION="restart"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Bootstrap: download required files if running standalone
bootstrap_standalone

# Check for gum (TUI tool) early - before any TUI functions are called
check_gum

# Set OS-specific default for DATA_DIR if not specified
if [ -z "$DATA_DIR" ]; then
    DATA_DIR=$(get_default_data_dir)
fi

# Change to project root
cd "$PROJECT_ROOT"

# Execute action
case "$ACTION" in
    deploy)
        do_deploy
        ;;
    update)
        do_update
        ;;
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_stop
        do_start
        ;;
    status)
        do_status
        ;;
esac
