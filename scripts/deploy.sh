#!/bin/bash
# CYROID Production Deployment Script
#
# Deploys CYROID for production use with automatic SSL and secret generation.
#
# Usage:
#   ./scripts/deploy.sh                                    # Interactive setup
#   ./scripts/deploy.sh --domain example.com              # Domain with Let's Encrypt
#   ./scripts/deploy.sh --ip 192.168.1.100                # IP with self-signed cert
#   ./scripts/deploy.sh --update                          # Update existing deployment
#   ./scripts/deploy.sh --stop                            # Stop all services
#   ./scripts/deploy.sh --status                          # Show service status
#
# Options:
#   --domain DOMAIN    Domain name for the server
#   --ip IP            IP address for the server
#   --email EMAIL      Email for Let's Encrypt (optional with --domain)
#   --ssl MODE         SSL mode: letsencrypt, selfsigned, manual (default: auto)
#   --version VER      CYROID version to deploy (default: latest)
#   --update           Pull latest images and restart
#   --stop             Stop all services
#   --status           Show service status
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
DATA_DIR="/data/cyroid"

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
        log_info "Try: sudo systemctl start docker"
        log_info "Or add your user to the docker group: sudo usermod -aG docker \$USER"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed."
        log_info "Visit: https://docs.docker.com/compose/install/"
        exit 1
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
    echo "Usage:"
    echo "  $0                                    Interactive setup"
    echo "  $0 --domain example.com              Domain with Let's Encrypt"
    echo "  $0 --ip 192.168.1.100                IP with self-signed cert"
    echo "  $0 --update                          Update existing deployment"
    echo "  $0 --stop                            Stop all services"
    echo "  $0 --status                          Show service status"
    echo ""
    echo "Options:"
    echo "  --domain DOMAIN    Domain name for the server"
    echo "  --ip IP            IP address for the server"
    echo "  --email EMAIL      Email for Let's Encrypt notifications"
    echo "  --ssl MODE         SSL mode: letsencrypt, selfsigned, manual"
    echo "  --version VER      CYROID version to deploy (default: latest)"
    echo "  --data-dir DIR     Data directory (default: /data/cyroid)"
    echo "  --update           Pull latest images and restart"
    echo "  --stop             Stop all services"
    echo "  --status           Show service status"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Deploy with domain and Let's Encrypt"
    echo "  $0 --domain cyroid.example.com --email admin@example.com"
    echo ""
    echo "  # Deploy with IP and self-signed certificate"
    echo "  $0 --ip 10.0.0.50"
    echo ""
    echo "  # Deploy specific version"
    echo "  $0 --domain cyroid.example.com --version 0.27.0"
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

    while [ $attempt -lt $max_attempts ]; do
        if docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -q "(healthy)"; then
            local healthy_count=$(docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -c "(healthy)" || echo "0")
            if [ "$healthy_count" -ge 3 ]; then
                log_info "All core services are healthy!"
                return 0
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

    # Check prerequisites
    check_docker

    # If no domain/IP specified, run interactive setup
    if [ -z "$DOMAIN" ] && [ -z "$IP" ]; then
        interactive_setup
    fi

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

    if [ ! -f "$ENV_FILE" ]; then
        log_error "No existing deployment found. Run without --update for initial setup."
        exit 1
    fi

    cd "$PROJECT_ROOT"

    # Load environment
    set -a
    source "$ENV_FILE"
    set +a

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

    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi

    docker_compose_cmd -f docker-compose.yml -f docker-compose.prod.yml ps
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
        --stop)
            ACTION="stop"
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
    stop)
        do_stop
        ;;
    status)
        do_status
        ;;
esac
