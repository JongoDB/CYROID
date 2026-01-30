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
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
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
}

check_ports() {
    local ports_in_use=""
    local port80_proc=""
    local port443_proc=""

    # Check if port 80 is in use (skip if we're updating an existing deployment)
    if [ "$ACTION" != "update" ]; then
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
                if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
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
                        [ -n "$port80_proc" ] && echo "  sudo kill $port80_proc"
                        exit 1
                    fi
                fi
            fi
        else
            tui_success "Ports 80 and 443 are available"
        fi
    fi
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

    # Export env vars for docker-compose
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
        if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
            : # gum spin handles its own progress display
        else
            echo -n "."
        fi
        sleep 2
    done

    echo ""
    tui_warn "Some services may not be fully healthy yet"
    tui_info "Check status with: $0 --status"
    tui_info "View logs with: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
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

        gum style \
            --foreground 82 --border-foreground 82 --border double \
            --align center --width 60 --margin "1 2" --padding "1 2" \
            "🎉 CYROID Deployment Complete!

Access URL: ${protocol}://${address}

First login:
  Register a new account
  First user becomes admin${ssl_note}"

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
    fi
    echo ""
}

do_deploy() {
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

    tui_header
    tui_title "Deploying CYROID"
    echo ""

    # Pre-flight checks
    check_data_dir_writable
    backup_env_file

    # Create directories and config
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

    # Pull images
    tui_info "Pulling Docker images..."
    if [ "$USE_TUI" = true ] && command -v gum &> /dev/null; then
        gum spin --spinner dot --title "Pulling images for $target_version..." -- \
            docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull -q
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull
    fi
    tui_success "Images pulled"

    # Restart services
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

    # Load environment
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

    # Check if anything is running
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

    tui_clear
    tui_header

    if [ "$USE_TUI" = true ]; then
        gum style --foreground 245 "This wizard will configure CYROID for production use."
        echo ""
    else
        echo "This wizard will configure CYROID for production use."
        echo ""
    fi

    # Step 1: Access method
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

    # Step 3: Data directory
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

    # Summary
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
