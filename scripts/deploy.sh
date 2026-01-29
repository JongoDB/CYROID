#!/bin/bash
# CYROID Deployment Script
#
# Deploys CYROID for production or development use with automatic environment setup.
# Handles platform differences (macOS, Linux) automatically.
#
# BOOTSTRAP: This script can be run standalone to bootstrap a fresh install:
#   curl -fsSL https://raw.githubusercontent.com/jongodb/CYROID/master/scripts/deploy.sh | bash -s -- --dev
#
# Usage:
#   ./scripts/deploy.sh                                    # Interactive setup
#   ./scripts/deploy.sh --dev                              # Local development mode
#   ./scripts/deploy.sh --domain example.com              # Domain with Let's Encrypt
#   ./scripts/deploy.sh --ip 192.168.1.100                # IP with self-signed cert
#   ./scripts/deploy.sh --update                          # Update existing deployment
#   ./scripts/deploy.sh --stop                            # Stop all services
#   ./scripts/deploy.sh --status                          # Show service status
#
# Options:
#   --dev              Development mode (builds from local source)
#   --domain DOMAIN    Domain name for the server
#   --ip IP            IP address for the server
#   --email EMAIL      Email for Let's Encrypt (optional with --domain)
#   --ssl MODE         SSL mode: letsencrypt, selfsigned, manual (default: auto)
#   --version VER      CYROID version to deploy (default: latest)
#   --update           Pull latest images and restart
#   --stop             Stop all services
#   --status           Show service status
#   --check            Run environment checks only (no deployment)
#   --help             Show this help message

set -euo pipefail

# Repository URL for bootstrap
REPO_URL="https://github.com/jongodb/CYROID.git"
REPO_NAME="CYROID"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
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
CLONE_DIR=""

# Platform detection
PLATFORM="$(uname -s)"
ARCH="$(uname -m)"

# Set default data directory based on platform
if [ "$PLATFORM" = "Darwin" ]; then
    # macOS: Use project-local directory since /data is not writable
    DATA_DIR="$PROJECT_ROOT/data"
else
    # Linux: Use system directory
    DATA_DIR="/data/cyroid"
fi

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

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running or you don't have permission."
        if [ "$PLATFORM" = "Darwin" ]; then
            log_info "Start Docker Desktop from your Applications folder"
        else
            log_info "Try: sudo systemctl start docker"
            log_info "Or add your user to the docker group: sudo usermod -aG docker \$USER"
        fi
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed."
        log_info "Visit: https://docs.docker.com/compose/install/"
        exit 1
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
        log_warn "Docker is not installed"
    else
        log_warn "Docker is installed but not running or accessible"
    fi

    case "$PLATFORM" in
        Darwin)
            echo ""
            log_info "Docker Desktop is required for macOS"
            log_info "Download from: https://www.docker.com/products/docker-desktop/"
            echo ""
            if command -v brew &> /dev/null; then
                read -p "Install Docker Desktop via Homebrew? [y/N]: " install_docker
                if [[ "$install_docker" =~ ^[Yy] ]]; then
                    brew install --cask docker
                    log_info "Docker Desktop installed. Please start it from Applications and run this script again."
                    exit 0
                fi
            fi
            log_info "Please install Docker Desktop and run this script again"
            exit 1
            ;;
        Linux)
            echo ""
            read -p "Install Docker automatically? [y/N]: " install_docker
            if [[ "$install_docker" =~ ^[Yy] ]]; then
                log_info "Installing Docker via official install script..."
                curl -fsSL https://get.docker.com | sh
                sudo usermod -aG docker "$USER"
                log_info "Docker installed! You may need to log out and back in for group changes."
                log_info "Then run this script again."
                exit 0
            fi
            log_info "Please install Docker and run this script again"
            log_info "Visit: https://docs.docker.com/engine/install/"
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

bootstrap_repository() {
    # Check if we're already in a CYROID repo
    if [ -f "$PROJECT_ROOT/docker-compose.yml" ] && [ -f "$PROJECT_ROOT/VERSION" ]; then
        log_info "Already in CYROID repository"
        return 0
    fi

    # Check if we're in a directory that looks like it could be CYROID
    if [ -f "./docker-compose.yml" ] && [ -f "./VERSION" ]; then
        PROJECT_ROOT="$(pwd)"
        SCRIPT_DIR="$PROJECT_ROOT/scripts"
        log_info "Found CYROID in current directory"
        return 0
    fi

    # Need to clone the repository
    log_step "Cloning CYROID repository"

    check_and_install_git

    local target_dir="${CLONE_DIR:-$HOME/$REPO_NAME}"

    if [ -d "$target_dir" ]; then
        log_info "Directory $target_dir already exists"
        read -p "Use existing directory? [Y/n]: " use_existing
        if [[ "$use_existing" =~ ^[Nn] ]]; then
            read -p "Enter new directory path: " target_dir
        fi
    fi

    if [ ! -d "$target_dir" ]; then
        log_info "Cloning to: $target_dir"
        git clone "$REPO_URL" "$target_dir"
    fi

    # Update paths
    PROJECT_ROOT="$target_dir"
    SCRIPT_DIR="$PROJECT_ROOT/scripts"
    ENV_FILE="$PROJECT_ROOT/.env.prod"

    # Update DATA_DIR based on platform
    if [ "$PLATFORM" = "Darwin" ]; then
        DATA_DIR="$PROJECT_ROOT/data"
    fi

    log_info "Repository ready at: $PROJECT_ROOT"

    # Change to the project directory
    cd "$PROJECT_ROOT"
}

ensure_in_repository() {
    # If PROJECT_ROOT doesn't have required files, we need to bootstrap
    if [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
        bootstrap_repository
    fi
}

# =============================================================================
# Environment Checks
# =============================================================================

check_platform() {
    log_step "Detecting platform"
    log_info "Platform: $PLATFORM ($ARCH)"

    case "$PLATFORM" in
        Darwin)
            log_info "macOS detected - using local data directory"
            ;;
        Linux)
            # Check if running in WSL
            if grep -qi microsoft /proc/version 2>/dev/null; then
                log_info "WSL detected"
            else
                log_info "Linux detected"
            fi
            ;;
        *)
            log_warn "Unknown platform: $PLATFORM - assuming Linux-like"
            ;;
    esac
}

check_disk_space() {
    log_step "Checking disk space"

    local target_dir="$PROJECT_ROOT"
    local required_gb=10
    local available_gb

    if [ "$PLATFORM" = "Darwin" ]; then
        available_gb=$(df -g "$target_dir" | awk 'NR==2 {print $4}')
    else
        available_gb=$(df -BG "$target_dir" | awk 'NR==2 {print $4}' | tr -d 'G')
    fi

    if [ "$available_gb" -lt "$required_gb" ]; then
        log_warn "Low disk space: ${available_gb}GB available, ${required_gb}GB recommended"
    else
        log_info "Disk space: ${available_gb}GB available"
    fi
}

check_conflicting_files() {
    log_step "Checking for conflicting configuration files"

    local has_conflicts=false

    # Check for docker-compose.override.yml when using explicit compose files
    if [ -f "$PROJECT_ROOT/docker-compose.override.yml" ]; then
        if [ "$DEV_MODE" = true ]; then
            log_warn "Found docker-compose.override.yml - this may conflict with dev mode"
            log_info "The override file will be loaded automatically by Docker Compose"
            log_info "Consider removing or renaming it: mv docker-compose.override.yml docker-compose.override.yml.bak"
            has_conflicts=true
        else
            log_info "Found docker-compose.override.yml (will be ignored in production mode)"
        fi
    fi

    # Check for .env file with potentially conflicting settings
    if [ -f "$PROJECT_ROOT/.env" ]; then
        local env_data_dir=$(grep "^CYROID_DATA_DIR=" "$PROJECT_ROOT/.env" 2>/dev/null | cut -d'=' -f2)
        if [ -n "$env_data_dir" ] && [ "$env_data_dir" != "$DATA_DIR" ]; then
            log_warn "Found .env with CYROID_DATA_DIR=$env_data_dir"
            log_info "This deployment will use DATA_DIR=$DATA_DIR"
            if [ "$DEV_MODE" = true ]; then
                log_info "Updating .env to match..."
            fi
        fi
    fi

    return 0
}

check_data_directory() {
    log_step "Checking data directory: $DATA_DIR"

    # Check if we can create/write to the data directory
    if [ -d "$DATA_DIR" ]; then
        if [ -w "$DATA_DIR" ]; then
            log_info "Data directory exists and is writable"
        else
            log_error "Data directory exists but is not writable: $DATA_DIR"
            log_info "Try: sudo chown -R $(id -u):$(id -g) $DATA_DIR"
            exit 1
        fi
    else
        # Try to create it
        local parent_dir=$(dirname "$DATA_DIR")
        if [ "$PLATFORM" = "Darwin" ]; then
            # On macOS, we should be able to create in project directory
            mkdir -p "$DATA_DIR" 2>/dev/null || {
                log_error "Cannot create data directory: $DATA_DIR"
                exit 1
            }
            log_info "Created data directory: $DATA_DIR"
        else
            # On Linux, might need sudo for /data
            if [ -w "$parent_dir" ] || mkdir -p "$DATA_DIR" 2>/dev/null; then
                log_info "Created data directory: $DATA_DIR"
            else
                log_info "Creating data directory with sudo..."
                sudo mkdir -p "$DATA_DIR"
                sudo chown -R "$(id -u):$(id -g)" "$DATA_DIR"
                log_info "Created data directory: $DATA_DIR"
            fi
        fi
    fi

    # Create subdirectories
    local subdirs="iso-cache template-storage vm-storage shared catalogs scenarios images"
    for subdir in $subdirs; do
        mkdir -p "$DATA_DIR/$subdir" 2>/dev/null || sudo mkdir -p "$DATA_DIR/$subdir" 2>/dev/null || true
    done
}

check_ports() {
    log_step "Checking port availability"

    local ports="80 443 8000 3000 5432 6379 9000"
    local blocked_ports=""

    for port in $ports; do
        if [ "$PLATFORM" = "Darwin" ]; then
            if lsof -i ":$port" -sTCP:LISTEN &>/dev/null; then
                blocked_ports="$blocked_ports $port"
            fi
        else
            if ss -tuln 2>/dev/null | grep -q ":$port " || netstat -tuln 2>/dev/null | grep -q ":$port "; then
                blocked_ports="$blocked_ports $port"
            fi
        fi
    done

    if [ -n "$blocked_ports" ]; then
        log_warn "Ports in use:$blocked_ports"
        log_info "These may be from a previous CYROID deployment (that's OK)"
        log_info "Or another service - check with: lsof -i :PORT"
    else
        log_info "All required ports are available"
    fi
}

check_docker_resources() {
    log_step "Checking Docker resources"

    if [ "$PLATFORM" = "Darwin" ]; then
        # On macOS, check Docker Desktop resource allocation
        local docker_info=$(docker info 2>/dev/null)
        local mem_total=$(echo "$docker_info" | grep "Total Memory:" | awk '{print $3}')
        local cpus=$(echo "$docker_info" | grep "CPUs:" | awk '{print $2}')

        log_info "Docker Desktop resources: ${cpus:-?} CPUs, ${mem_total:-?} memory"

        # Check if memory seems low (rough check)
        if [ -n "$mem_total" ]; then
            local mem_gb=$(echo "$mem_total" | grep -o '[0-9]*' | head -1)
            if [ -n "$mem_gb" ] && [ "$mem_gb" -lt 4 ]; then
                log_warn "Docker Desktop memory is low (${mem_total})"
                log_info "Recommend at least 4GB for CYROID. Adjust in Docker Desktop settings."
            fi
        fi
    else
        # On Linux, Docker uses host resources directly
        local mem_total=$(free -g 2>/dev/null | awk '/Mem:/ {print $2}')
        local cpus=$(nproc 2>/dev/null)

        log_info "System resources: ${cpus:-?} CPUs, ${mem_total:-?}GB memory"

        if [ -n "$mem_total" ] && [ "$mem_total" -lt 4 ]; then
            log_warn "System memory is low (${mem_total}GB)"
            log_info "Recommend at least 4GB for CYROID"
        fi
    fi
}

run_all_checks() {
    log_step "Running environment checks"
    echo ""

    check_platform
    check_docker
    check_docker_resources
    check_disk_space
    check_ports
    check_conflicting_files
    check_data_directory

    echo ""
    log_info "All checks passed!"
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
    echo "This script handles complete setup including Docker installation,"
    echo "repository cloning, and service deployment."
    echo ""
    echo "Usage:"
    echo "  $0                                    Interactive setup (production)"
    echo "  $0 --dev                              Development mode (local build)"
    echo "  $0 --domain example.com              Domain with Let's Encrypt"
    echo "  $0 --ip 192.168.1.100                IP with self-signed cert"
    echo "  $0 --update                          Update existing deployment"
    echo "  $0 --stop                            Stop all services"
    echo "  $0 --status                          Show service status"
    echo "  $0 --check                           Run environment checks only"
    echo ""
    echo "Options:"
    echo "  --dev              Development mode (builds from local source, hot-reload)"
    echo "  --domain DOMAIN    Domain name for the server"
    echo "  --ip IP            IP address for the server"
    echo "  --email EMAIL      Email for Let's Encrypt notifications"
    echo "  --ssl MODE         SSL mode: letsencrypt, selfsigned, manual"
    echo "  --version VER      CYROID version to deploy (default: latest)"
    echo "  --data-dir DIR     Data directory (default: auto-detected)"
    echo "  --clone-dir DIR    Directory to clone repository into (if not in repo)"
    echo "  --update           Pull latest images and restart"
    echo "  --stop             Stop all services"
    echo "  --status           Show service status"
    echo "  --check            Run environment checks without deploying"
    echo "  --help             Show this help message"
    echo ""
    echo "Bootstrap (fresh install on new machine):"
    echo "  # One-liner to download and run:"
    echo "  curl -fsSL https://raw.githubusercontent.com/jongodb/CYROID/master/scripts/deploy.sh -o deploy.sh"
    echo "  chmod +x deploy.sh && ./deploy.sh --dev"
    echo ""
    echo "  # Or clone first, then run:"
    echo "  git clone https://github.com/jongodb/CYROID.git && cd CYROID"
    echo "  ./scripts/deploy.sh --dev"
    echo ""
    echo "Examples:"
    echo "  # Local development (macOS or Linux)"
    echo "  $0 --dev"
    echo ""
    echo "  # Deploy with domain and Let's Encrypt"
    echo "  $0 --domain cyroid.example.com --email admin@example.com"
    echo ""
    echo "  # Deploy with IP and self-signed certificate"
    echo "  $0 --ip 10.0.0.50"
    echo ""
    echo "  # Check environment before deploying"
    echo "  $0 --check"
    echo ""
    echo "Platform notes:"
    echo "  macOS:  Uses ./data for storage (Docker Desktop limitation)"
    echo "  Linux:  Uses /data/cyroid for storage by default"
    echo ""
    echo "The script will automatically:"
    echo "  - Check for and help install Docker if missing"
    echo "  - Clone the repository if run from outside it"
    echo "  - Detect platform (macOS/Linux) and configure appropriately"
    echo "  - Set up data directories with correct permissions"
    echo "  - Handle Docker Compose configuration conflicts"
}

# =============================================================================
# Deployment Functions
# =============================================================================

create_data_directories() {
    log_step "Creating data directories"

    sudo mkdir -p "$DATA_DIR"/{iso-cache,template-storage,vm-storage,shared}
    sudo chown -R "$(id -u):$(id -g)" "$DATA_DIR" 2>/dev/null || true

    log_info "Data directory: $DATA_DIR"
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

    case "$SSL_MODE" in
        letsencrypt)
            log_info "Using Let's Encrypt for automatic certificates"
            log_info "Certificates will be obtained on first request"

            # Create acme directory and file if it doesn't exist
            mkdir -p "$PROJECT_ROOT/acme"
            touch "$PROJECT_ROOT/acme/acme.json"
            chmod 600 "$PROJECT_ROOT/acme/acme.json"
            ;;

        selfsigned)
            log_info "Generating self-signed certificate"
            "$SCRIPT_DIR/generate-certs.sh" "${DOMAIN:-$IP}"
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
    "$SCRIPT_DIR/init-networks.sh"
}

pull_images() {
    log_step "Pulling Docker images"

    cd "$PROJECT_ROOT"

    # Export env vars for docker-compose
    export $(grep -v '^#' "$ENV_FILE" | xargs)

    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull

    log_info "Images pulled successfully"
}

start_services() {
    log_step "Starting CYROID services"

    cd "$PROJECT_ROOT"

    # Export env vars for docker-compose
    set -a
    source "$ENV_FILE"
    set +a

    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d

    log_info "Services starting..."
}

wait_for_health() {
    log_step "Waiting for services to be healthy"

    local max_attempts=60
    local attempt=0
    local address="${DOMAIN:-$IP:-localhost}"

    while [ $attempt -lt $max_attempts ]; do
        # Check Docker health status
        if docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -q "(healthy)"; then
            local healthy_count=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
            if [ "$healthy_count" -ge 3 ]; then
                # Also verify API is responding
                if curl -sk "https://${address}/api/v1/version" 2>/dev/null | grep -q "version" || \
                   curl -s "http://${address}/api/v1/version" 2>/dev/null | grep -q "version"; then
                    echo ""
                    log_info "All core services are healthy!"
                    return 0
                fi
            fi
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    log_warn "Some services may not be fully healthy yet"
    log_info "Check status with: $0 --status"
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
    print_banner

    # Bootstrap: ensure we have the repository and dependencies
    log_step "Checking prerequisites"
    check_and_install_curl
    check_and_install_docker
    ensure_in_repository

    # Run comprehensive environment checks
    check_platform
    check_docker
    check_docker_resources
    check_disk_space
    check_ports

    # If no domain/IP specified, run interactive setup
    if [ -z "$DOMAIN" ] && [ -z "$IP" ]; then
        interactive_setup
    fi

    # Check data directory (after interactive setup may have changed DATA_DIR)
    check_data_directory

    # Create directories and config
    create_data_directories
    create_env_file
    setup_ssl
    init_networks
    pull_images
    start_services
    wait_for_health
    show_access_info
}

do_update() {
    print_banner
    log_step "Updating CYROID deployment"

    check_docker

    # Check for env file (prod or dev)
    local found_env=false
    if [ -f "$ENV_FILE" ]; then
        found_env=true
        set -a
        source "$ENV_FILE"
        set +a
    elif [ -f "$PROJECT_ROOT/.env" ]; then
        found_env=true
        set -a
        source "$PROJECT_ROOT/.env"
        set +a
    fi

    if [ "$found_env" = false ]; then
        log_error "No existing deployment found. Run without --update for initial setup."
        exit 1
    fi

    cd "$PROJECT_ROOT"

    # Pull latest images
    log_info "Pulling latest images..."
    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml pull

    # Restart services
    log_info "Restarting services..."
    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml up -d

    wait_for_health

    log_info "Update complete!"
    echo ""
}

do_stop() {
    print_banner
    log_step "Stopping CYROID services"

    cd "$PROJECT_ROOT"

    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml down

    log_info "All services stopped"
    echo ""
}

do_status() {
    print_banner
    log_step "CYROID Service Status"

    cd "$PROJECT_ROOT"

    # Try to load env file (prod or dev)
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    elif [ -f "$PROJECT_ROOT/.env" ]; then
        set -a
        source "$PROJECT_ROOT/.env"
        set +a
    fi

    # Determine which compose files to use
    if [ "$DEV_MODE" = true ] || [ -f "$PROJECT_ROOT/.env" ]; then
        docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml ps
    else
        docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps
    fi
    echo ""
}

do_check() {
    print_banner
    run_all_checks
}

# =============================================================================
# Development Mode Functions
# =============================================================================

setup_dev_env() {
    log_step "Setting up development environment"

    local env_file="$PROJECT_ROOT/.env"

    # Backup existing .env if it exists and differs
    if [ -f "$env_file" ]; then
        local existing_data_dir=$(grep "^CYROID_DATA_DIR=" "$env_file" 2>/dev/null | cut -d'=' -f2)
        if [ "$existing_data_dir" != "$DATA_DIR" ]; then
            log_info "Updating .env with correct DATA_DIR"
        fi
    fi

    # Create/update .env file for development
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
    log_info "Created .env file"
}

handle_override_file() {
    log_step "Checking for docker-compose.override.yml"

    local override_file="$PROJECT_ROOT/docker-compose.override.yml"

    if [ -f "$override_file" ]; then
        log_warn "Found docker-compose.override.yml"
        log_info "This file gets auto-loaded by Docker Compose and may conflict"
        log_info "The deploy script manages environment configuration directly"

        # Back it up to prevent conflicts
        local backup_file="${override_file}.bak.$(date +%Y%m%d%H%M%S)"
        mv "$override_file" "$backup_file"
        log_info "Backed up to: $(basename "$backup_file")"
        log_info "To restore: mv $(basename "$backup_file") docker-compose.override.yml"
    fi
}

create_traefik_dirs() {
    log_step "Creating Traefik directories"

    mkdir -p "$PROJECT_ROOT/traefik/dynamic"
    mkdir -p "$PROJECT_ROOT/acme"

    # Create empty acme.json if needed
    if [ ! -f "$PROJECT_ROOT/acme/acme.json" ]; then
        touch "$PROJECT_ROOT/acme/acme.json"
        chmod 600 "$PROJECT_ROOT/acme/acme.json"
    fi

    log_info "Traefik directories ready"
}

do_dev_deploy() {
    print_banner
    log_info "Development Mode"
    echo ""

    # Bootstrap: ensure we have the repository and dependencies
    log_step "Checking prerequisites"
    check_and_install_curl
    check_and_install_docker
    ensure_in_repository

    # Run all environment checks
    run_all_checks

    # Handle conflicting override file
    handle_override_file

    # Setup environment
    setup_dev_env
    create_traefik_dirs

    # Initialize networks
    log_step "Initializing Docker networks"
    "$SCRIPT_DIR/init-networks.sh" || true

    # Build and start services
    log_step "Building and starting services"
    cd "$PROJECT_ROOT"

    # Load the environment
    set -a
    source "$PROJECT_ROOT/.env"
    set +a

    # Build and start with dev compose file
    docker_compose_cmd -f docker-compose.yml -f docker-compose.dev.yml up -d --build

    # Wait for services
    wait_for_health_dev

    # Show access info
    show_dev_access_info
}

wait_for_health_dev() {
    log_step "Waiting for services to be ready"

    local max_attempts=60
    local attempt=0

    cd "$PROJECT_ROOT"

    while [ $attempt -lt $max_attempts ]; do
        # Check if API is responding (through Traefik)
        if curl -s http://localhost/api/v1/version 2>/dev/null | grep -q "version"; then
            echo ""
            log_info "API is ready!"
            return 0
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    log_warn "Services may not be fully ready yet"
    log_info "Check logs with: docker compose -f docker-compose.yml -f docker-compose.dev.yml logs"
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

interactive_setup() {
    echo -e "${BOLD}Production Deployment Setup${NC}"
    echo ""
    echo "This wizard will configure CYROID for production use."
    echo ""

    # Ask for domain or IP
    echo -e "${CYAN}How will users access CYROID?${NC}"
    echo "  1) Domain name (e.g., cyroid.example.com)"
    echo "  2) IP address (e.g., 192.168.1.100)"
    echo ""
    read -p "Enter choice [1-2]: " access_choice

    case "$access_choice" in
        1)
            read -p "Enter domain name: " DOMAIN
            if [ -z "$DOMAIN" ]; then
                log_error "Domain name cannot be empty"
                exit 1
            fi

            echo ""
            echo -e "${CYAN}SSL Certificate:${NC}"
            echo "  1) Let's Encrypt (automatic, free, requires domain to be publicly accessible)"
            echo "  2) Self-signed (works immediately, shows browser warning)"
            echo ""
            read -p "Enter choice [1-2]: " ssl_choice

            case "$ssl_choice" in
                1)
                    SSL_MODE="letsencrypt"
                    read -p "Enter email for Let's Encrypt notifications: " EMAIL
                    ;;
                2)
                    SSL_MODE="selfsigned"
                    ;;
                *)
                    SSL_MODE="selfsigned"
                    ;;
            esac
            ;;
        2)
            read -p "Enter IP address: " IP
            if [ -z "$IP" ]; then
                log_error "IP address cannot be empty"
                exit 1
            fi
            SSL_MODE="selfsigned"
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac

    # Data directory
    echo ""
    read -p "Data directory [$DATA_DIR]: " input_data_dir
    if [ -n "$input_data_dir" ]; then
        DATA_DIR="$input_data_dir"
    fi

    echo ""
    echo -e "${GREEN}Configuration Summary:${NC}"
    echo "  Address:    ${DOMAIN:-$IP}"
    echo "  SSL Mode:   $SSL_MODE"
    echo "  Data Dir:   $DATA_DIR"
    echo ""
    read -p "Proceed with deployment? [Y/n]: " confirm

    if [[ "$confirm" =~ ^[Nn] ]]; then
        log_info "Deployment cancelled"
        exit 0
    fi
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
        --clone-dir)
            CLONE_DIR="$2"
            shift 2
            ;;
        --update)
            ACTION="update"
            shift
            ;;
        --stop)
            ACTION="stop"
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
            do_dev_deploy  # Dev mode update is the same as deploy (rebuild)
        else
            do_update
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
            log_info "All services stopped"
        else
            do_stop
        fi
        ;;
    status)
        do_status
        ;;
    check)
        do_check
        ;;
esac
