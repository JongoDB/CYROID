#!/bin/bash
# CYROID Deployment Script
#
# Full TUI for deploying and managing CYROID in production or development mode.
# Uses 'gum' for beautiful terminal interfaces (auto-installs on macOS).
# Handles platform differences (macOS, Linux) automatically.
#
# This script works TWO ways:
#
#   1. From git clone (recommended):
#      git clone https://github.com/JongoDB/CYROID.git && cd CYROID
#      ./scripts/deploy.sh
#
#   2. Standalone download (auto-downloads required files):
#      curl -fsSL https://raw.githubusercontent.com/JongoDB/CYROID/master/scripts/deploy.sh -o deploy.sh
#      chmod +x deploy.sh && ./deploy.sh
#
# Usage:
#   ./scripts/deploy.sh                                    # Interactive TUI setup
#   ./scripts/deploy.sh --dev                              # Local development mode
#   ./scripts/deploy.sh --domain example.com              # Domain with Let's Encrypt
#   ./scripts/deploy.sh --ip 192.168.1.100                # IP with self-signed cert
#   ./scripts/deploy.sh --update                          # Update (choose version)
#   ./scripts/deploy.sh --start                           # Start stopped deployment
#   ./scripts/deploy.sh --stop                            # Stop all services
#   ./scripts/deploy.sh --restart                         # Restart all services
#   ./scripts/deploy.sh --status                          # Show service status
#   ./scripts/deploy.sh --check                           # Run environment checks only
#
# Options:
#   --dev              Development mode (builds from local source, hot-reload)
#   --domain DOMAIN    Domain name for the server
#   --ip IP            IP address for the server
#   --email EMAIL      Email for Let's Encrypt (optional with --domain)
#   --ssl MODE         SSL mode: letsencrypt, selfsigned, manual (default: auto)
#   --version VER      CYROID version to deploy/update to (default: interactive)
#   --data-dir DIR     Data directory (default: auto by OS)
#   --update           Update deployment (interactive version selection)
#   --start            Start a stopped deployment
#   --stop             Stop all services
#   --restart          Stop and start all services
#   --status           Show current status and health
#   --check            Run environment checks only (no deployment)
#   --help             Show this help message

set -euo pipefail

# Repository URL for bootstrap
REPO_URL="https://github.com/jongodb/CYROID.git"
REPO_NAME="CYROID"

# GitHub repository for standalone downloads (without git)
GITHUB_REPO="JongoDB/CYROID"
GITHUB_BRANCH="master"
GITHUB_RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Platform detection (early, before PROJECT_ROOT)
PLATFORM="$(uname -s)"
ARCH="$(uname -m)"

# Get script directory - handle both normal execution and piped execution (curl | bash)
if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" != "/dev/stdin" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    # Running via curl | bash or similar - use current directory
    SCRIPT_DIR="$(pwd)"
fi

# Determine PROJECT_ROOT: use current directory if not in a valid CYROID repo
if [ -f "$SCRIPT_DIR/../docker-compose.yml" ] && [ -f "$SCRIPT_DIR/../VERSION" ]; then
    # Script is inside a CYROID repo (scripts/ directory)
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
elif [ -f "./docker-compose.yml" ] && [ -f "./VERSION" ]; then
    # Current directory is a CYROID repo
    PROJECT_ROOT="$(pwd)"
else
    # Not in a repo - use current directory (will clone here)
    PROJECT_ROOT="$(pwd)"
fi
ENV_FILE="$PROJECT_ROOT/.env.prod"

# Default values
DOMAIN=""
IP=""
EMAIL=""
SSL_MODE=""
VERSION="latest"
ACTION="deploy"
DEV_MODE=false
CHECK_ONLY=false
DATA_DIR=""  # Set after OS detection

# OS type detection
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS_TYPE="linux" ;;
        Darwin*)    OS_TYPE="macos" ;;
        *)          OS_TYPE="unknown" ;;
    esac
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

check_gum() {
    if command -v gum &> /dev/null; then
        return 0
    fi

    echo -e "${YELLOW}The TUI requires 'gum' to be installed.${NC}"
    echo ""

    detect_os
    if [ "$OS_TYPE" = "macos" ]; then
        echo "Install with: brew install gum"
        read -p "Install gum now? [Y/n]: " install_choice
        if [[ ! "$install_choice" =~ ^[Nn] ]]; then
            if command -v brew &> /dev/null; then
                brew install gum
                return 0
            else
                echo -e "${RED}Homebrew not found. Install from: https://brew.sh${NC}"
            fi
        fi
    else
        echo "Install with your package manager:"
        echo "  Ubuntu/Debian: sudo apt install gum"
        echo "  Fedora: sudo dnf install gum"
        echo "  Arch: sudo pacman -S gum"
        echo "  Or: go install github.com/charmbracelet/gum@latest"
        read -p "Continue without TUI? [Y/n]: " continue_choice
        if [[ "$continue_choice" =~ ^[Nn] ]]; then
            exit 1
        fi
    fi

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
# Bootstrap Functions (for fresh installs)
# =============================================================================

check_and_install_git() {
    if command -v git &> /dev/null; then
        return 0
    fi

    log_warn "Git is not installed"

    case "$PLATFORM" in
        Darwin)
            log_info "Installing git via Xcode Command Line Tools..."
            xcode-select --install 2>/dev/null || true
            log_info "Please complete the installation dialog, then run this script again"
            exit 1
            ;;
        Linux)
            if command -v apt-get &> /dev/null; then
                log_info "Installing git..."
                sudo apt-get update && sudo apt-get install -y git
            elif command -v yum &> /dev/null; then
                log_info "Installing git..."
                sudo yum install -y git
            elif command -v dnf &> /dev/null; then
                log_info "Installing git..."
                sudo dnf install -y git
            else
                log_error "Please install git manually and run this script again"
                exit 1
            fi
            ;;
        *)
            log_error "Please install git manually and run this script again"
            exit 1
            ;;
    esac
}

check_and_install_docker() {
    if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
        return 0
    fi

    if ! command -v docker &> /dev/null; then
        tui_error "Docker is not installed"
    else
        tui_error "Docker is installed but not running or accessible"
    fi

    detect_os
    case "$OS_TYPE" in
        macos)
            echo ""
            tui_info "Docker Desktop is required for macOS"
            tui_info "Download from: https://www.docker.com/products/docker-desktop/"
            echo ""
            if command -v brew &> /dev/null; then
                if tui_confirm "Install Docker Desktop via Homebrew?"; then
                    brew install --cask docker
                    tui_info "Docker Desktop installed. Please start it from Applications and run this script again."
                    exit 0
                fi
            fi
            tui_info "Please install Docker Desktop and run this script again"
            exit 1
            ;;
        linux)
            echo ""
            if tui_confirm "Install Docker automatically?"; then
                tui_info "Installing Docker via official install script..."
                curl -fsSL https://get.docker.com | sh
                sudo usermod -aG docker "$USER"
                tui_info "Docker installed! You may need to log out and back in for group changes."
                tui_info "Then run this script again."
                exit 0
            fi
            tui_info "Please install Docker and run this script again"
            tui_info "Visit: https://docs.docker.com/engine/install/"
            exit 1
            ;;
        *)
            log_error "Please install Docker manually"
            log_info "Visit: https://docs.docker.com/get-docker/"
            exit 1
            ;;
    esac
}

check_and_install_curl() {
    if command -v curl &> /dev/null; then
        return 0
    fi

    log_warn "curl is not installed"

    case "$PLATFORM" in
        Linux)
            if command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y curl
            elif command -v yum &> /dev/null; then
                sudo yum install -y curl
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y curl
            else
                log_error "Please install curl manually"
                exit 1
            fi
            ;;
        *)
            log_error "Please install curl manually"
            exit 1
            ;;
    esac
}

download_file() {
    # Download a file via curl or wget (for standalone bootstrap)
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

    log_error "Failed to download $desc"
    return 1
}

bootstrap_standalone() {
    # Bootstrap for curl|bash execution - downloads compose files without git
    # This is an alternative to bootstrap_repository() when git isn't available

    local missing_files=()

    # Check for required compose files
    if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        missing_files+=("docker-compose.yml")
    fi
    if [ ! -f "$PROJECT_ROOT/docker-compose.prod.yml" ]; then
        missing_files+=("docker-compose.prod.yml")
    fi

    # If no files are missing, continue normally
    if [ ${#missing_files[@]} -eq 0 ]; then
        return 0
    fi

    print_banner
    echo -e "${YELLOW}Standalone mode - downloading required files from GitHub...${NC}"
    echo ""

    # Check for curl or wget
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        log_error "Neither curl nor wget found. Please install one of them."
        exit 1
    fi

    # Create CYROID directory if needed
    if [ ! -d "$PROJECT_ROOT" ] || [ "$PROJECT_ROOT" = "/" ]; then
        PROJECT_ROOT="$HOME/cyroid"
        SCRIPT_DIR="$PROJECT_ROOT/scripts"
        ENV_FILE="$PROJECT_ROOT/.env.prod"
        log_info "Creating CYROID directory at: $PROJECT_ROOT"
        mkdir -p "$PROJECT_ROOT/scripts"
    fi

    # Download required files
    local files_to_download=(
        "docker-compose.yml"
        "docker-compose.prod.yml"
        "docker-compose.dev.yml"
        "traefik/dynamic/base.yml"
        "scripts/init-networks.sh"
        "scripts/generate-certs.sh"
    )

    for file in "${files_to_download[@]}"; do
        local dest="$PROJECT_ROOT/$file"
        if [ ! -f "$dest" ]; then
            log_info "Downloading $file..."
            if ! download_file "${GITHUB_RAW_BASE}/$file" "$dest" "$file"; then
                log_error "Failed to download $file"
                log_info "Try: git clone https://github.com/${GITHUB_REPO}.git"
                exit 1
            fi
            # Make scripts executable
            if [[ "$file" == *.sh ]]; then
                chmod +x "$dest"
            fi
        fi
    done

    # Copy this script to the project if not already there
    if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" != "/dev/stdin" ] && [ -f "${BASH_SOURCE[0]}" ]; then
        if [ ! -f "$PROJECT_ROOT/scripts/deploy.sh" ]; then
            cp "${BASH_SOURCE[0]}" "$PROJECT_ROOT/scripts/deploy.sh" 2>/dev/null || true
            chmod +x "$PROJECT_ROOT/scripts/deploy.sh" 2>/dev/null || true
        fi
    fi

    echo ""
    log_info "Required files downloaded to: $PROJECT_ROOT"
    log_info "Continuing with deployment..."
    echo ""

    # Update paths for the new location
    cd "$PROJECT_ROOT"
}

bootstrap_repository() {
    local current_dir="$(pwd)"

    # Check if current directory is already a CYROID repo
    if [ -f "./docker-compose.yml" ] && [ -f "./VERSION" ]; then
        PROJECT_ROOT="$current_dir"
        SCRIPT_DIR="$PROJECT_ROOT/scripts"
        log_info "Already in CYROID repository"
        return 0
    fi

    # Try standalone bootstrap first if git isn't available
    if ! command -v git &> /dev/null; then
        log_info "Git not found, attempting standalone bootstrap..."
        bootstrap_standalone
        return $?
    fi

    # Need to clone the repository into current directory
    log_step "Cloning CYROID repository into current directory"

    check_and_install_git

    # Remove the standalone deploy.sh if it exists (repo has its own)
    rm -f "./deploy.sh" 2>/dev/null || true

    # Clone directly into current directory
    git clone "$REPO_URL" .

    # Verify clone worked
    if [ ! -f "./docker-compose.yml" ]; then
        log_error "Clone failed - docker-compose.yml not found"
        exit 1
    fi

    # Update paths
    PROJECT_ROOT="$current_dir"
    SCRIPT_DIR="$PROJECT_ROOT/scripts"
    ENV_FILE="$PROJECT_ROOT/.env.prod"

    log_info "Repository cloned to: $PROJECT_ROOT"
}

ensure_in_repository() {
    # If PROJECT_ROOT doesn't have required files, we need to bootstrap
    if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        bootstrap_repository
    fi
}

# =============================================================================
# Check Functions
# =============================================================================

check_docker() {
    detect_os

    if ! command -v docker &> /dev/null; then
        check_and_install_docker
        return
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
        detect_os
        if [ "$OS_TYPE" = "macos" ]; then
            tui_info "Docker Compose is included with Docker Desktop."
            tui_info "Please update Docker Desktop to the latest version."
        else
            tui_info "Install the plugin: sudo apt install docker-compose-plugin"
        fi
        exit 1
    fi
}

check_ports() {
    local ports_in_use=""
    local port80_proc=""
    local port443_proc=""

    # Check if port 80 is in use (skip if we're updating an existing deployment)
    if [ "$ACTION" != "update" ] && [ "$ACTION" != "start" ]; then
        # Try to identify what's using the ports
        if command -v lsof &> /dev/null; then
            port80_proc=$(lsof -i :80 -t 2>/dev/null | head -1)
            port443_proc=$(lsof -i :443 -t 2>/dev/null | head -1)
            [ -n "$port80_proc" ] && ports_in_use="80 $ports_in_use"
            [ -n "$port443_proc" ] && ports_in_use="443 $ports_in_use"
        elif command -v ss &> /dev/null; then
            ss -tuln | grep -q ':80 ' && ports_in_use="80 $ports_in_use"
            ss -tuln | grep -q ':443 ' && ports_in_use="443 $ports_in_use"
        elif command -v netstat &> /dev/null; then
            netstat -tuln 2>/dev/null | grep -q ':80 ' && ports_in_use="80 $ports_in_use"
            netstat -tuln 2>/dev/null | grep -q ':443 ' && ports_in_use="443 $ports_in_use"
        fi

        if [ -n "$ports_in_use" ]; then
            tui_warn "Ports in use: $ports_in_use"
            echo ""

            # Try to identify the process
            if [ -n "$port80_proc" ] && command -v ps &> /dev/null; then
                local proc_info=$(ps -p "$port80_proc" -o comm= 2>/dev/null || echo "unknown")
                tui_info "Port 80 is used by: $proc_info (PID: $port80_proc)"
            fi
            if [ -n "$port443_proc" ] && command -v ps &> /dev/null; then
                local proc_info=$(ps -p "$port443_proc" -o comm= 2>/dev/null || echo "unknown")
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
                if ! tui_confirm "Continue anyway? (may fail if ports are blocked)"; then
                    tui_info "Deployment cancelled. Free up ports 80 and 443 first."
                    exit 1
                fi
            fi
        else
            tui_success "Ports 80 and 443 are available"
        fi
    fi
}

check_data_dir_writable() {
    local parent_dir=$(dirname "$DATA_DIR")

    if [ -d "$DATA_DIR" ]; then
        if [ ! -w "$DATA_DIR" ]; then
            tui_error "Data directory $DATA_DIR exists but is not writable"
            tui_info "Try: sudo chown -R \$(id -u):\$(id -g) $DATA_DIR"
            exit 1
        fi
    elif [ -d "$parent_dir" ]; then
        if [ ! -w "$parent_dir" ]; then
            tui_warn "Cannot write to $parent_dir - will need sudo to create data directory"
        fi
    fi
}

backup_env_file() {
    if [ -f "$ENV_FILE" ]; then
        local backup="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$ENV_FILE" "$backup"
        tui_info "Backed up existing config to $backup"
    fi
}

check_disk_space() {
    log_step "Checking disk space"

    local target_dir="$PROJECT_ROOT"
    local required_gb=10
    local available_gb

    detect_os
    if [ "$OS_TYPE" = "macos" ]; then
        available_gb=$(df -g "$target_dir" | awk 'NR==2 {print $4}')
    else
        available_gb=$(df -BG "$target_dir" | awk 'NR==2 {print $4}' | tr -d 'G')
    fi

    if [ "$available_gb" -lt "$required_gb" ]; then
        tui_warn "Low disk space: ${available_gb}GB available, ${required_gb}GB recommended"
    else
        tui_success "Disk space: ${available_gb}GB available"
    fi
}

check_docker_resources() {
    log_step "Checking Docker resources"

    detect_os
    if [ "$OS_TYPE" = "macos" ]; then
        local docker_info=$(docker info 2>/dev/null)
        local mem_total=$(echo "$docker_info" | grep "Total Memory:" | awk '{print $3}')
        local cpus=$(echo "$docker_info" | grep "CPUs:" | awk '{print $2}')

        tui_info "Docker Desktop resources: ${cpus:-?} CPUs, ${mem_total:-?} memory"

        if [ -n "$mem_total" ]; then
            local mem_gb=$(echo "$mem_total" | grep -o '[0-9]*' | head -1)
            if [ -n "$mem_gb" ] && [ "$mem_gb" -lt 4 ]; then
                tui_warn "Docker Desktop memory is low (${mem_total})"
                tui_info "Recommend at least 4GB for CYROID. Adjust in Docker Desktop settings."
            fi
        fi
    else
        local mem_total=$(free -g 2>/dev/null | awk '/Mem:/ {print $2}')
        local cpus=$(nproc 2>/dev/null)

        tui_info "System resources: ${cpus:-?} CPUs, ${mem_total:-?}GB memory"

        if [ -n "$mem_total" ] && [ "$mem_total" -lt 4 ]; then
            tui_warn "System memory is low (${mem_total}GB)"
            tui_info "Recommend at least 4GB for CYROID"
        fi
    fi
}

run_all_checks() {
    log_step "Running environment checks"
    echo ""

    detect_os
    tui_info "Platform: $PLATFORM ($ARCH)"
    tui_info "OS Type: $OS_TYPE"
    echo ""

    check_docker
    check_docker_resources
    check_disk_space
    check_ports
    check_data_dir_writable

    echo ""
    tui_success "All checks passed!"
}

docker_compose_cmd() {
    if docker compose version &> /dev/null 2>&1; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

show_help() {
    echo "CYROID Deployment Script"
    echo ""
    echo "A full TUI for deploying and managing CYROID in production or development mode."
    echo "Uses 'gum' for beautiful terminal interfaces (auto-installs on macOS)."
    echo "Can bootstrap a fresh install from a standalone script."
    echo ""
    echo "Usage:"
    echo "  $0                                    Interactive TUI setup"
    echo "  $0 --dev                              Development mode (local build)"
    echo "  $0 --domain example.com              Domain with Let's Encrypt"
    echo "  $0 --ip 192.168.1.100                IP with self-signed cert"
    echo "  $0 --update                          Update (interactive version)"
    echo "  $0 --start                           Start stopped deployment"
    echo "  $0 --stop                            Stop all services"
    echo "  $0 --restart                         Restart all services"
    echo "  $0 --status                          Show service status"
    echo "  $0 --check                           Run environment checks only"
    echo ""
    echo "Lifecycle Commands:"
    echo "  --start            Start a stopped CYROID deployment"
    echo "  --stop             Stop all running services"
    echo "  --restart          Stop then start all services"
    echo "  --update           Update to new version (interactive selection)"
    echo "  --status           Show current status and health"
    echo "  --check            Run environment checks without deploying"
    echo ""
    echo "Deploy Options:"
    echo "  --dev              Development mode (builds from local source, hot-reload)"
    echo "  --domain DOMAIN    Domain name for the server"
    echo "  --ip IP            IP address for the server"
    echo "  --email EMAIL      Email for Let's Encrypt notifications"
    echo "  --ssl MODE         SSL mode: letsencrypt, selfsigned, manual"
    echo "  --version VER      CYROID version (default: interactive)"
    echo "  --data-dir DIR     Data directory (default: auto by OS)"
    echo "  --help             Show this help message"
    echo ""
    echo "Bootstrap (fresh install on new machine):"
    echo "  # One-liner to download and run:"
    echo "  curl -fsSL https://raw.githubusercontent.com/jongodb/CYROID/master/scripts/deploy.sh -o deploy.sh"
    echo "  chmod +x deploy.sh && ./deploy.sh --dev"
    echo ""
    echo "Examples:"
    echo "  # Local development (macOS or Linux)"
    echo "  $0 --dev"
    echo ""
    echo "  # Deploy with domain and Let's Encrypt"
    echo "  $0 --domain cyroid.example.com --email admin@example.com"
    echo ""
    echo "  # Update to specific version"
    echo "  $0 --update --version v0.30.0"
    echo ""
    echo "  # Check environment before deploying"
    echo "  $0 --check"
    echo ""
    echo "Platform notes:"
    echo "  macOS:  Uses ~/.cyroid/data for storage"
    echo "  Linux:  Uses /data/cyroid for storage by default"
}

# =============================================================================
# Deployment Functions
# =============================================================================

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
            local grandparent=$(dirname "$parent_dir")
            if [ ! -w "$grandparent" ]; then
                need_sudo=true
            fi
        fi
    fi

    # All directories needed by CYROID
    local dirs="iso-cache template-storage vm-storage shared catalogs scenarios images registry"

    if [ "$need_sudo" = true ]; then
        tui_info "Need elevated permissions to create $DATA_DIR"
        sudo mkdir -p "$DATA_DIR"/{iso-cache,template-storage,vm-storage,shared,catalogs,scenarios,images,registry}
        sudo chown -R "$(id -u):$(id -g)" "$DATA_DIR"
    else
        mkdir -p "$DATA_DIR"/{iso-cache,template-storage,vm-storage,shared,catalogs,scenarios,images,registry}
    fi

    # Ensure certs directory exists for docker-compose mount
    mkdir -p "$PROJECT_ROOT/certs"

    tui_info "Data directory: $DATA_DIR"
}

create_env_file() {
    log_step "Configuring environment"

    local address="${DOMAIN:-$IP}"

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
        source "$ENV_FILE" 2>/dev/null || true
        jwt_secret="${JWT_SECRET_KEY:-}"
        pg_password="${POSTGRES_PASSWORD:-}"
        minio_password="${MINIO_SECRET_KEY:-}"
    fi

    if [ -z "$jwt_secret" ]; then
        jwt_secret=$(generate_secret)
        tui_info "Generated JWT secret"
    fi
    if [ -z "$pg_password" ]; then
        pg_password=$(generate_secret | head -c 32)
        tui_info "Generated PostgreSQL password"
    fi
    if [ -z "$minio_password" ]; then
        minio_password=$(generate_secret | head -c 32)
        tui_info "Generated MinIO password"
    fi

    local ssl_resolver=""
    if [ "$SSL_MODE" = "letsencrypt" ]; then
        ssl_resolver="letsencrypt"
    fi

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
    tui_info "Environment file: $ENV_FILE"
    tui_info "SSL Mode: $SSL_MODE"
}

setup_ssl() {
    log_step "Setting up SSL certificates"

    generate_traefik_config

    mkdir -p "$PROJECT_ROOT/certs"

    case "$SSL_MODE" in
        letsencrypt)
            tui_info "Using Let's Encrypt for automatic certificates"
            mkdir -p "$PROJECT_ROOT/acme"
            touch "$PROJECT_ROOT/acme/acme.json"
            chmod 600 "$PROJECT_ROOT/acme/acme.json"
            ;;

        selfsigned)
            tui_info "Generating self-signed certificate"
            "$SCRIPT_DIR/generate-certs.sh" "${DOMAIN:-$IP}"
            ;;

        manual)
            if [ ! -f "$PROJECT_ROOT/certs/cert.pem" ] || [ ! -f "$PROJECT_ROOT/certs/key.pem" ]; then
                tui_error "Manual SSL mode requires certificates in ./certs/"
                tui_info "Please place your certificate files:"
                tui_info "  - ./certs/cert.pem"
                tui_info "  - ./certs/key.pem"
                exit 1
            fi
            tui_info "Using manually provided certificates"
            ;;
    esac
}

generate_traefik_config() {
    local acme_email="${EMAIL:-admin@${DOMAIN:-$IP}}"
    local traefik_config="$PROJECT_ROOT/traefik-prod.yml"

    tui_info "Generating Traefik production config"

    cat > "$traefik_config" << EOF
# Traefik Production Configuration (Generated by deploy.sh)
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
}

init_networks() {
    log_step "Initializing Docker networks"
    "$SCRIPT_DIR/init-networks.sh"
}

pull_images() {
    cd "$PROJECT_ROOT"
    export $(grep -v '^#' "$ENV_FILE" | xargs)

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Pulling Docker images..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull -q
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull
    fi
}

start_services() {
    cd "$PROJECT_ROOT"

    set -a
    source "$ENV_FILE"
    set +a

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Starting services..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d
    fi
}

wait_for_health() {
    tui_info "Waiting for services to be healthy..."

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -q "(healthy)"; then
            local healthy_count=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
            if [ "$healthy_count" -ge 3 ]; then
                tui_success "All services are healthy!"
                return 0
            fi
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    tui_warn "Some services may not be fully healthy yet"
    tui_info "Check status with: $0 --status"
}

show_access_info() {
    local address="${DOMAIN:-$IP}"
    local protocol="https"

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}            ${BOLD}CYROID Deployment Complete!${NC}                     ${GREEN}║${NC}"
    echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}Access URL:${NC}  ${protocol}://${address}                  ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}First login:${NC}                                           ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}    Register a new account - first user becomes admin      ${GREEN}║${NC}"
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
    echo ""
}

do_deploy() {
    if [ -n "$DOMAIN" ] || [ -n "$IP" ]; then
        tui_clear
        tui_header
    fi

    tui_info "Checking Docker installation..."
    check_docker
    tui_success "Docker is available"

    check_ports

    if [ -z "$DOMAIN" ] && [ -z "$IP" ]; then
        interactive_setup
    fi

    tui_header
    tui_title "Deploying CYROID"
    echo ""

    check_data_dir_writable
    backup_env_file

    tui_info "Creating data directories..."
    create_data_directories
    tui_success "Data directories ready"

    tui_info "Generating configuration..."
    create_env_file
    tui_success "Configuration saved"

    tui_info "Setting up SSL certificates..."
    setup_ssl
    tui_success "SSL configured"

    tui_info "Initializing Docker networks..."
    init_networks
    tui_success "Networks ready"

    tui_info "Pulling Docker images (this may take a while)..."
    pull_images
    tui_success "Images pulled"

    tui_info "Starting services..."
    start_services
    tui_success "Services started"

    wait_for_health
    show_access_info
}

# =============================================================================
# Development Mode Functions
# =============================================================================

setup_dev_env() {
    log_step "Setting up development environment"

    local env_file="$PROJECT_ROOT/.env"

    cat > "$env_file" << EOF
# CYROID Development Environment
# Generated by deploy.sh --dev on $(date)
# Platform: $PLATFORM ($ARCH)

# Data directory (platform-specific)
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

# Development settings
DEBUG=true
EOF

    chmod 600 "$env_file"
    tui_info "Created .env file"
}

handle_override_file() {
    log_step "Checking for docker-compose.override.yml"

    local override_file="$PROJECT_ROOT/docker-compose.override.yml"

    if [ -f "$override_file" ]; then
        tui_warn "Found docker-compose.override.yml"
        tui_info "This file gets auto-loaded by Docker Compose and may conflict"

        local backup_file="${override_file}.bak.$(date +%Y%m%d%H%M%S)"
        mv "$override_file" "$backup_file"
        tui_info "Backed up to: $(basename "$backup_file")"
    fi
}

create_traefik_dirs() {
    log_step "Creating Traefik directories"

    mkdir -p "$PROJECT_ROOT/traefik/dynamic"
    mkdir -p "$PROJECT_ROOT/acme"
    mkdir -p "$PROJECT_ROOT/certs"

    if [ ! -f "$PROJECT_ROOT/acme/acme.json" ]; then
        touch "$PROJECT_ROOT/acme/acme.json"
        chmod 600 "$PROJECT_ROOT/acme/acme.json"
    fi

    tui_info "Traefik directories ready"
}

wait_for_health_dev() {
    log_step "Waiting for services to be ready"

    local max_attempts=60
    local attempt=0

    cd "$PROJECT_ROOT"

    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost/api/v1/version 2>/dev/null | grep -q "version"; then
            echo ""
            tui_success "API is ready!"
            return 0
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    tui_warn "Services may not be fully ready yet"
    tui_info "Check logs with: docker compose -f docker-compose.yml -f docker-compose.dev.yml logs"
}

show_dev_access_info() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}         ${BOLD}CYROID Development Environment Ready!${NC}              ${GREEN}║${NC}"
    echo -e "${GREEN}╠════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}Application:${NC}  http://localhost                           ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}API Docs:${NC}     http://localhost/docs                      ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}Traefik:${NC}      http://localhost:8080                      ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${CYAN}Data Dir:${NC}     $DATA_DIR                                  ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}  ${YELLOW}First login:${NC}  Register - first user becomes admin       ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}                                                            ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Useful commands:"
    echo "  View logs:     docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f"
    echo "  View API logs: docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f api"
    echo "  Stop:          $0 --dev --stop"
    echo "  Rebuild:       $0 --dev"
    echo "  Status:        $0 --dev --status"
    echo ""
}

do_dev_deploy() {
    print_banner
    tui_info "Development Mode"
    echo ""

    log_step "Checking prerequisites"
    check_and_install_curl
    check_and_install_docker
    ensure_in_repository

    run_all_checks

    handle_override_file
    setup_dev_env
    create_traefik_dirs
    create_data_directories

    log_step "Initializing Docker networks"
    "$SCRIPT_DIR/init-networks.sh" || true

    log_step "Building and starting services"
    cd "$PROJECT_ROOT"

    set -a
    source "$PROJECT_ROOT/.env"
    set +a

    docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml up -d --build

    wait_for_health_dev
    show_dev_access_info
}

# =============================================================================
# Lifecycle Functions
# =============================================================================

get_current_version() {
    if [ -f "$ENV_FILE" ]; then
        grep "^VERSION=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "unknown"
    else
        echo "unknown"
    fi
}

get_available_releases() {
    if command -v curl &> /dev/null; then
        curl -s "https://api.github.com/repos/JongoDB/CYROID/releases?per_page=10" 2>/dev/null | \
            grep '"tag_name"' | sed 's/.*"tag_name": "\(.*\)".*/\1/' | head -10
    fi
}

get_available_tags() {
    if command -v curl &> /dev/null; then
        curl -s "https://api.github.com/repos/JongoDB/CYROID/tags?per_page=15" 2>/dev/null | \
            grep '"name"' | sed 's/.*"name": "\(.*\)".*/\1/' | head -15
    fi
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

    set -a
    source "$ENV_FILE"
    set +a

    local current_version=$(get_current_version)
    tui_info "Current version: $current_version"
    echo ""

    local target_version="$VERSION"

    if [ -z "$target_version" ] || [ "$target_version" = "latest" ]; then
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
                            target_version="latest"
                        fi
                        ;;
                    "Choose from tags"*)
                        if [ -n "$tags" ]; then
                            target_version=$(echo "$tags" | gum choose --header "Select tag:")
                        else
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

    if [ "$target_version" != "latest" ]; then
        sed -i.bak "s/^VERSION=.*/VERSION=$target_version/" "$ENV_FILE" 2>/dev/null || \
            sed -i '' "s/^VERSION=.*/VERSION=$target_version/" "$ENV_FILE"
        export VERSION="$target_version"
    fi

    tui_info "Pulling Docker images..."
    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Pulling images for $target_version..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull -q
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull
    fi
    tui_success "Images pulled"

    tui_info "Restarting services..."
    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Restarting services..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d
    fi
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

    set -a
    source "$ENV_FILE"
    set +a

    tui_info "Starting CYROID services..."

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Starting services..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d
    fi

    wait_for_health

    local address=$(grep "^DOMAIN=" "$ENV_FILE" | cut -d= -f2)

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

    local running=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps -q 2>/dev/null | wc -l | tr -d ' ')

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

    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Stopping CYROID..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down
    fi

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

do_check() {
    print_banner
    run_all_checks
}

interactive_setup() {
    check_gum

    tui_clear
    tui_header

    if [ "$USE_TUI" = true ]; then
        gum style --foreground 245 "This wizard will configure CYROID for production use."
        echo ""
    else
        echo "This wizard will configure CYROID for production use."
        echo ""
    fi

    tui_title "Step 1: Server Access"
    echo ""

    local access_choice
    access_choice=$(tui_choose "How will users access CYROID?" \
        "Domain name (e.g., cyroid.example.com)" \
        "IP address (e.g., 192.168.1.100)")

    case "$access_choice" in
        "Domain name"*)
            echo ""
            DOMAIN=$(tui_input "Enter your domain name:" "cyroid.example.com" "")
            if [ -z "$DOMAIN" ]; then
                tui_error "Domain name cannot be empty"
                exit 1
            fi

            echo ""
            tui_title "Step 2: SSL Certificate"
            echo ""

            local ssl_choice
            ssl_choice=$(tui_choose "Choose SSL certificate type:" \
                "Let's Encrypt (automatic, free, requires public domain)" \
                "Self-signed (works immediately, browser warning)")

            case "$ssl_choice" in
                "Let's Encrypt"*)
                    SSL_MODE="letsencrypt"
                    echo ""
                    EMAIL=$(tui_input "Email for Let's Encrypt notifications:" "admin@$DOMAIN" "admin@$DOMAIN")
                    ;;
                *)
                    SSL_MODE="selfsigned"
                    ;;
            esac
            ;;
        "IP address"*)
            echo ""
            IP=$(tui_input "Enter server IP address:" "192.168.1.100" "")
            if [ -z "$IP" ]; then
                tui_error "IP address cannot be empty"
                exit 1
            fi
            SSL_MODE="selfsigned"
            ;;
        *)
            tui_error "Invalid choice"
            exit 1
            ;;
    esac

    echo ""
    tui_title "Step 3: Data Storage"
    echo ""

    if [ -z "$DATA_DIR" ]; then
        DATA_DIR=$(get_default_data_dir)
    fi

    local input_data_dir
    input_data_dir=$(tui_input "Data directory for CYROID storage:" "$DATA_DIR" "$DATA_DIR")
    if [ -n "$input_data_dir" ]; then
        DATA_DIR="$input_data_dir"
    fi

    echo ""
    tui_title "Configuration Summary"

    local summary="Address:     ${DOMAIN:-$IP}
SSL Mode:    $SSL_MODE
Data Dir:    $DATA_DIR"

    if [ -n "$EMAIL" ]; then
        summary="$summary
Email:       $EMAIL"
    fi

    tui_summary_box "$summary"

    echo ""
    if ! tui_confirm "Proceed with deployment?"; then
        tui_info "Deployment cancelled"
        exit 0
    fi

    tui_clear
}

# =============================================================================
# Main
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dev)
            DEV_MODE=true
            shift
            ;;
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
        --check)
            ACTION="check"
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

# Set OS-specific default for DATA_DIR if not specified
if [ -z "$DATA_DIR" ]; then
    DATA_DIR=$(get_default_data_dir)
fi

# Change to project root
cd "$PROJECT_ROOT"

# Execute action
case "$ACTION" in
    deploy)
        if [ "$DEV_MODE" = true ]; then
            do_dev_deploy
        else
            do_deploy
        fi
        ;;
    update)
        if [ "$DEV_MODE" = true ]; then
            do_dev_deploy
        else
            do_update
        fi
        ;;
    start)
        if [ "$DEV_MODE" = true ]; then
            print_banner
            log_step "Starting development services"
            cd "$PROJECT_ROOT"
            if [ -f "$PROJECT_ROOT/.env" ]; then
                set -a
                source "$PROJECT_ROOT/.env"
                set +a
            fi
            docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml up -d
            wait_for_health_dev
            show_dev_access_info
        else
            do_start
        fi
        ;;
    stop)
        if [ "$DEV_MODE" = true ]; then
            print_banner
            log_step "Stopping development services"
            cd "$PROJECT_ROOT"
            if [ -f "$PROJECT_ROOT/.env" ]; then
                set -a
                source "$PROJECT_ROOT/.env"
                set +a
            fi
            docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml down
            tui_success "All services stopped"
        else
            do_stop
        fi
        ;;
    restart)
        if [ "$DEV_MODE" = true ]; then
            print_banner
            log_step "Restarting development services"
            cd "$PROJECT_ROOT"
            if [ -f "$PROJECT_ROOT/.env" ]; then
                set -a
                source "$PROJECT_ROOT/.env"
                set +a
            fi
            docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml down
            docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml up -d --build
            wait_for_health_dev
            show_dev_access_info
        else
            do_stop
            do_start
        fi
        ;;
    status)
        if [ "$DEV_MODE" = true ]; then
            print_banner
            log_step "Development Service Status"
            cd "$PROJECT_ROOT"
            if [ -f "$PROJECT_ROOT/.env" ]; then
                set -a
                source "$PROJECT_ROOT/.env"
                set +a
            fi
            docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml ps
        else
            do_status
        fi
        ;;
    check)
        do_check
        ;;
esac
