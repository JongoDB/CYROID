<p align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-brightgreen" alt="Status">
  <img src="https://img.shields.io/badge/Phase-5%20of%207-blue" alt="Phase">
  <img src="https://img.shields.io/badge/Version-0.35.35-orange" alt="Version">
  <img src="https://img.shields.io/badge/License-AGPL%20v3-blue" alt="License">
  <img src="https://github.com/JongoDB/CYROID/actions/workflows/docker-publish.yml/badge.svg" alt="Docker Build">
</p>

<h1 align="center">CYROID</h1>
<h3 align="center">Cyber Range Orchestrator In Docker</h3>

<p align="center">
  <strong>Enterprise-grade cyber range orchestration platform for automated deployment, management, and execution of Docker-based training environments</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#api-reference">API</a> •
  <a href="#contributing">Contributing</a>
</p>

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/JongoDB/CYROID/master/scripts/deploy.sh -o deploy.sh
chmod +x deploy.sh
./deploy.sh
```

---

## Overview

**CYROID** is a comprehensive web-based cyber range orchestration platform designed to automate the instantiation, management, and execution of Docker-based cyber training environments. Built for military, government, and educational institutions, CYROID enables rapid deployment of isolated, networked cyber environments for training, evaluation, and security testing.

### Key Capabilities

- **Full Lifecycle Management**: Planning → Development → Deployment → Execution → Teardown
- **Multi-OS Support**: Linux containers, Linux VMs (QEMU/KVM), Windows VMs (dockur/windows)
- **Complete Isolation**: Each range runs in its own Docker-in-Docker (DinD) container
- **Web-Based Console**: VNC access to all VMs through browser
- **Scenario Automation**: MSEL (Master Scenario Events List) execution engine
- **Evidence Management**: Student submission, validation, and automated scoring

---

## What's New in v0.35.x

### Production Deployment (v0.34.0 - v0.35.5)

- **Self-Contained Deploy Script**: Full TUI-based deployment with version selection
- **Non-Interactive Mode**: Deploy with `-y` flag for CI/CD pipelines
- **Admin CLI Flags**: Create admin user via `--admin-user`, `--admin-password`, `--admin-email`
- **Multi-Architecture Support**: Platform detection and proper image pulls for x86_64/ARM64
- **Image Backup/Restore**: Backup all CYROID Docker images to disk for offline deployment
- **Live Dashboard**: K9s-style TUI with real-time service status during deployment

### Registry & Catalog (v0.30.0 - v0.33.x)

- **Content Catalog**: Browse and install training scenarios from remote registries
- **Storefront UI**: Professional catalog browsing with categories and search
- **Registry Management**: Admin interface for managing catalog sources
- **Scenario Installation**: One-click install of scenarios with all dependencies

### Previous Highlights

- **DinD Isolation**: Each range runs in isolated Docker-in-Docker container
- **Content Library**: Student Lab walkthroughs with markdown support
- **Blueprint Export/Import v3.0**: Dockerfiles included for reproducible environments
- **Global Notifications**: Toast notifications + bell dropdown history
- **Cross-Platform Support**: Linux and macOS (Docker Desktop)

---

## Architecture Overview

### DinD (Docker-in-Docker) Isolation

Every range deploys inside its own isolated Docker-in-Docker container:

- **Complete Network Isolation**: Each range has its own Docker daemon and network namespace
- **Identical IP Spaces**: Multiple ranges can use the same blueprint IPs simultaneously
- **Simplified Cleanup**: Deleting a range just removes its DinD container
- **No IP Translation**: Blueprint IPs are used exactly as defined

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CYROID Host Docker                                │
│                                                                      │
│   cyroid-mgmt (172.30.0.0/24)         cyroid-ranges (172.30.1.0/24) │
│   ├── API: 172.30.0.10                ├── Range-1 DinD: 172.30.1.x  │
│   ├── DB: 172.30.0.11                 │   └── Internal: 10.0.1.0/24 │
│   ├── Redis: 172.30.0.12              ├── Range-2 DinD: 172.30.1.y  │
│   ├── MinIO: 172.30.0.13              │   └── Internal: 10.0.1.0/24 │
│   ├── Traefik: 172.30.0.14            │       (Same IPs - isolated!)│
│   ├── Worker: 172.30.0.15             └── ...                       │
│   ├── Registry: 172.30.0.16                                         │
│   └── Frontend: 172.30.0.20                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Features

### Implemented (Phases 1-5)

| Category | Feature | Status |
|----------|---------|--------|
| **Authentication** | JWT-based auth with role management | ✅ Complete |
| **User Management** | RBAC (Admin, Range Engineer, White Cell, Evaluator) | ✅ Complete |
| **ABAC** | Attribute-based access control with resource tags | 🟡 In Progress |
| **VM Templates** | CRUD operations, OS library (24+ Linux distros, Windows 7-11, Server 2003-2025, macOS) | ✅ Complete |
| **Range Builder** | Visual drag-drop network designer | ✅ Complete |
| **DinD Isolation** | Each range runs in isolated Docker-in-Docker container | ✅ Complete |
| **Network Management** | Multi-segment Docker networks with custom subnets | ✅ Complete |
| **VM Lifecycle** | Create, start, stop, restart, delete with real-time status | ✅ Complete |
| **VNC Console** | Web-based graphical access via Traefik proxy | ✅ Complete |
| **Console Pop-out** | Default new window, Shift+click for inline | ✅ Complete |
| **Dynamic Networking** | Add/remove network interfaces on running VMs | ✅ Complete |
| **Range Templating** | Import/export/clone range configurations | ✅ Complete |
| **Blueprint Export v3** | Full config, artifacts, MSEL, Dockerfiles, offline Docker images | ✅ Complete |
| **Resource Monitoring** | CPU, memory, network statistics per VM | ✅ Complete |
| **Event Logging** | Timestamped activity feed with real-time streaming | ✅ Complete |
| **Artifact Repository** | MinIO-backed storage with SHA256 hashing | ✅ Complete |
| **Snapshot Management** | Golden images for Windows, Docker snapshots | ✅ Complete |
| **Execution Console** | Multi-panel dashboard with VM grid | ✅ Complete |
| **MSEL Parser** | Markdown/YAML inject timeline | ✅ Complete |
| **Manual Injects** | Trigger scenario events from console | ✅ Complete |
| **Connection Tracking** | Monitor student activity | ✅ Complete |
| **Version Display** | API endpoint + UI footer | ✅ Complete |
| **Multi-Architecture** | x86_64 + ARM64 native, emulation warnings | ✅ Complete |
| **Content Library** | Student Lab walkthroughs with markdown support | ✅ Complete |
| **Training Events** | Event scheduling with range associations | ✅ Complete |
| **Global Notifications** | Toast notifications + bell dropdown history | ✅ Complete |
| **Deployment Progress** | Real-time visual progress during range deployment | ✅ Complete |
| **Clipboard Sync** | Copy from walkthrough to VNC console | ✅ Complete |
| **macOS Support** | macOS ISOs and container creation | ✅ Complete |

### In Development (Phase 5)

| Feature | Progress | Target |
|---------|----------|--------|
| Evidence Submission Portal | 🟡 40% | Phase 5 |
| Automated Evidence Validation | 🟡 30% | Phase 5 |
| Scoring Engine | 🟡 20% | Phase 5 |
| Network Traffic Visualization | 🟡 60% | Phase 5 |

### Planned (Phases 6-7)

| Feature | Phase | Priority |
|---------|-------|----------|
| MSEL Time-based Automation | 6 | High |
| Attack Scenario Scripts | 6 | High |
| CAC/PKI Authentication | 6 | Medium |
| Offline/Air-gap Mode | 6 | ✅ Done (via export) |
| Purple Team Integration (Caldera) | 7 | Medium |
| Collaborative Range Editing | 7 | Low |
| Advanced Reporting & Analytics | 7 | Low |
| Custom Report Builder | 7 | Low |
| AAR Auto-generation | 7 | Low |
| Windows ARM64 VM Support | 7 | Low |

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CYROID Architecture                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  Dashboard   │ │Range Builder │ │  Execution   │ │   Evidence   │   │
│  │              │ │   (Visual)   │ │   Console    │ │    Review    │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  Templates   │ │  Artifacts   │ │ VNC Console  │ │    Users     │   │
│  │   Library    │ │  Repository  │ │  (noVNC)     │ │  Management  │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTPS/WSS
┌──────────────────────────────▼──────────────────────────────────────────┐
│                     Traefik Reverse Proxy (v2.11)                        │
│           HTTP Routing • VNC Path Proxy • SSL/TLS Termination            │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                   FastAPI Backend (Python 3.11)                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        API Layer                                  │    │
│  │  /auth  /users  /ranges  /vms  /networks  /templates  /artifacts │    │
│  │  /events  /msel  /evidence  /cache  /snapshots  /websocket       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      Service Layer                                │    │
│  │  DinDService • DockerService • RangeDeploymentService            │    │
│  │  EventService • MSELParser • StorageService • VyOSService        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                       Data Layer                                  │    │
│  │  SQLAlchemy ORM • Pydantic Schemas • Alembic Migrations          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────┬─────────────┬─────────────┬─────────────┬──────────────────┘
             │             │             │             │
    ┌────────▼───┐  ┌──────▼─────┐  ┌───▼────┐  ┌────▼─────┐
    │ PostgreSQL │  │   Redis    │  │ MinIO  │  │  Docker  │
    │     16     │  │     7      │  │  S3    │  │  Engine  │
    │            │  │            │  │        │  │          │
    │ • Users    │  │ • Cache    │  │ • ISOs │  │ • DinD   │
    │ • Ranges   │  │ • Queue    │  │ • Tmpl │  │   Ranges │
    │ • VMs      │  │ • Sessions │  │ • Artf │  │ • Nets   │
    │ • Events   │  │            │  │        │  │          │
    └────────────┘  └────────────┘  └────────┘  └──────────┘
```

### DinD Range Isolation Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Docker Host                                       │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │              cyroid-mgmt Network (172.30.0.0/24)                       │ │
│  │           CYROID Infrastructure Services (External)                    │ │
│  └─────────┬──────────────────┬──────────────────┬───────────────────────┘ │
│            │                  │                  │                         │
│       ┌────┴────┐        ┌────┴────┐        ┌────┴────┐  ┌─────────┐       │
│       │ CYROID  │        │ Traefik │        │ Database│  │Registry │       │
│       │   API   │        │ (VNC)   │        │  Redis  │  │ (Local) │       │
│       │ Worker  │        │         │        │  MinIO  │  │         │       │
│       └────┬────┘        └────┬────┘        └─────────┘  └────┬────┘       │
│            │                  │                               │            │
│  ┌─────────┴──────────────────┴───────────────────────────────┴─────────┐ │
│  │              cyroid-ranges Network (172.30.1.0/24)                    │ │
│  │              Range DinD Containers (Isolated)                         │ │
│  └───────────┬────────────────────────────────┬─────────────────────────┘ │
│              │                                │                           │
│   ┌──────────▼──────────┐          ┌──────────▼──────────┐               │
│   │   Range 1 DinD      │          │   Range 2 DinD      │               │
│   │   (172.30.1.10)     │          │   (172.30.1.11)     │               │
│   │                     │          │                     │               │
│   │  ┌───────────────┐  │          │  ┌───────────────┐  │               │
│   │  │ Inner Docker  │  │          │  │ Inner Docker  │  │               │
│   │  │               │  │          │  │               │  │               │
│   │  │ Net: 10.0.1.0 │  │          │  │ Net: 10.0.1.0 │  │  Same IPs!    │
│   │  │ VM1: 10.0.1.10│  │          │  │ VM1: 10.0.1.10│  │  Fully        │
│   │  │ VM2: 10.0.1.11│  │          │  │ VM2: 10.0.1.11│  │  Isolated!    │
│   │  │ VyOS: 10.0.1.1│  │          │  │ VyOS: 10.0.1.1│  │               │
│   │  └───────────────┘  │          │  └───────────────┘  │               │
│   └─────────────────────┘          └─────────────────────┘               │
└────────────────────────────────────────────────────────────────────────────┘
```

### Local Docker Registry

CYROID includes a local Docker registry (`registry:2`) for efficient image distribution to DinD containers:

**Purpose:**
- Eliminates redundant image pulls from external registries (Docker Hub, GHCR)
- Each DinD container pulls images from the local registry instead of the internet
- Enables layer caching for faster subsequent deployments

**How It Works:**
1. When a range is deployed, required images are pushed to the local registry
2. DinD containers are configured to use `172.30.0.16:5000` as an insecure registry
3. VMs inside DinD pull images from the local registry
4. Cached layers are reused across all range deployments

**Benefits:**
| Benefit | Description |
|---------|-------------|
| Faster Deployments | Cached images deploy in seconds instead of minutes |
| Reduced Bandwidth | Images are pulled once and shared across ranges |
| Offline Support | Pre-populate registry for air-gapped environments |
| Consistency | All ranges use identical image versions |

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Frontend** | React | 18.2 | UI Framework |
| | TypeScript | 5.3 | Type Safety |
| | Vite | 5.x | Build Tool |
| | Tailwind CSS | 3.4 | Styling |
| | Zustand | 4.5 | State Management |
| | React Flow | 11.x | Network Visualization |
| | noVNC | 1.4 | VNC Client |
| | xterm.js | 5.x | Terminal Emulator |
| **Backend** | FastAPI | 0.109 | API Framework |
| | Python | 3.11 | Runtime |
| | SQLAlchemy | 2.0 | ORM |
| | Alembic | 1.13 | Migrations |
| | Dramatiq | 1.15 | Task Queue |
| | Docker SDK | 7.1 | Container Orchestration |
| **Infrastructure** | PostgreSQL | 16 | Primary Database |
| | Redis | 7 | Cache & Queue |
| | MinIO | Latest | Object Storage (S3) |
| | Traefik | 2.11 | Reverse Proxy |
| | Docker | 24+ | Container Runtime |
| | Docker DinD | 24 | Range Isolation |
| | Registry | 2 | Local Image Distribution |

### Container Images (GHCR)

All CYROID images are published to GitHub Container Registry:

| Image | Description | Pull Command |
|-------|-------------|--------------|
| `ghcr.io/jongodb/cyroid-api` | FastAPI backend | `docker pull ghcr.io/jongodb/cyroid-api:latest` |
| `ghcr.io/jongodb/cyroid-frontend` | React web UI | `docker pull ghcr.io/jongodb/cyroid-frontend:latest` |
| `ghcr.io/jongodb/cyroid-worker` | Dramatiq task worker | `docker pull ghcr.io/jongodb/cyroid-worker:latest` |
| `ghcr.io/jongodb/cyroid-proxy` | Traefik reverse proxy | `docker pull ghcr.io/jongodb/cyroid-proxy:latest` |
| `ghcr.io/jongodb/cyroid-dind` | Docker-in-Docker | `docker pull ghcr.io/jongodb/cyroid-dind:latest` |
| `ghcr.io/jongodb/cyroid-storage` | MinIO object storage | `docker pull ghcr.io/jongodb/cyroid-storage:latest` |

Images are automatically built and pushed on every commit to master via GitHub Actions.

### Per-Range Network Architecture (Inside DinD)

Each range runs inside a DinD container with iptables-based routing (VyOS optional):

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        Range DinD Container                                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   DinD iptables (Router)                               │ │
│  │           - Network isolation via FORWARD rules                        │ │
│  │           - NAT/MASQUERADE for internet                               │ │
│  │           - VNC DNAT port forwarding                                  │ │
│  └─────────┬────────────────────────────────────────────────────────────┘ │
│            │                                                               │
│  ┌─────────┴───────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  Network A (10.0.1.0/24) ──┬── VM1 (10.0.1.10)                      │  │
│  │                             └── VM2 (10.0.1.11)                      │  │
│  │                                                                      │  │
│  │  Network B (10.0.2.0/24) ──── VM3 (10.0.2.10)                       │  │
│  │                                                                      │  │
│  │  (Optional) VyOS Router ──── For DHCP, advanced routing             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Key Features:**

| Feature | Description |
|---------|-------------|
| **DinD Isolation** | Each range runs in its own Docker-in-Docker container |
| **iptables Routing** | DinD handles network isolation and NAT via iptables |
| **VyOS Optional** | Add VyOS only for DHCP server or advanced routing policies |
| **Network Isolation** | Shield icon toggle - iptables FORWARD rules block external access |
| **Internet Access** | Globe icon toggle - iptables MASQUERADE enables per-network internet |
| **VNC Access** | Traefik → DinD (iptables DNAT) → VM container |

**Network Connectivity Matrix:**

| is_isolated | internet_enabled | Result |
|-------------|------------------|--------|
| ✓ | ✗ | No external access, iptables DROP on FORWARD |
| ✓ | ✓ | NAT to internet via iptables MASQUERADE |
| ✗ | ✗ | Direct Docker bridge access |
| ✗ | ✓ | Full internet + host access |

---

## Quick Start

### Easy Install (3 Commands)

```bash
curl -fsSL https://raw.githubusercontent.com/JongoDB/CYROID/master/scripts/deploy.sh -o deploy.sh
chmod +x deploy.sh
./deploy.sh
```

The deploy script provides a TUI-based installation wizard that handles everything automatically.

### Prerequisites

- Docker Engine 24.0+ (or Docker Desktop on macOS)
- Docker Compose 2.20+
- KVM support (for Windows VMs on Linux): `lsmod | grep kvm`
- Minimum resources: 16 CPU cores, 32GB RAM, 500GB disk

### Installation Options

#### Option 1: Deploy Script (Recommended)

**Interactive mode (with TUI wizard):**
```bash
curl -fsSL https://raw.githubusercontent.com/JongoDB/CYROID/master/scripts/deploy.sh -o deploy.sh
chmod +x deploy.sh
./deploy.sh
```

**Non-interactive mode (for CI/CD or scripted deployments):**
```bash
./deploy.sh -y --ip 192.168.1.100 --ssl selfsigned --admin-user admin --admin-password admin123
```

**Deploy Script Options:**
| Flag | Description |
|------|-------------|
| `-y`, `--yes` | Non-interactive mode (use defaults) |
| `--ip IP` | Server IP address |
| `--domain DOMAIN` | Domain name (for Let's Encrypt) |
| `--ssl MODE` | SSL mode: `letsencrypt`, `selfsigned`, `manual` |
| `--admin-user USER` | Admin username (default: admin) |
| `--admin-password PASS` | Admin password (default: admin123) |
| `--admin-email EMAIL` | Admin email (default: admin@cyroid.local) |
| `--version VER` | CYROID version to deploy |
| `--backup [NAME]` | Backup Docker images to disk |
| `--restore [NAME]` | Restore Docker images from backup |

#### Option 2: Manual Installation

```bash
# Clone the repository
git clone https://github.com/JongoDB/CYROID.git
cd CYROID

# Copy environment template
cp .env.example .env

# Generate secure secrets (Linux)
sed -i "s/your-secret-key-here/$(openssl rand -hex 32)/" .env

# macOS: Generate secure secrets
sed -i '' "s/your-secret-key-here/$(openssl rand -hex 32)/" .env

# Initialize CYROID networks
./scripts/init-networks.sh

# Start all services (pulls pre-built images from GHCR)
docker-compose up -d

# Verify services are running
docker-compose ps

# Check API health
curl http://localhost/api/v1/version
```

### Development Setup

For development with local builds and hot-reload:

```bash
# Use the development compose file
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Or copy to override for automatic loading
cp docker-compose.dev.yml docker-compose.override.yml
docker-compose up --build
```

### macOS Setup (Docker Desktop)

On macOS, you **must** configure the data directory to a path Docker Desktop can access:

```bash
# Edit .env and add (replace 'yourname' with your username):
CYROID_DATA_DIR=/Users/yourname/.cyroid

# Or use your home directory shorthand:
echo "CYROID_DATA_DIR=$HOME/.cyroid" >> .env

# The directories will be created automatically on first range deployment
```

> **Why?** Docker Desktop for Mac only shares files from `/Users`, `/Volumes`, `/private`, `/tmp`, and `/var/folders` by default. The Linux default of `/data/cyroid` won't work.

### Network Initialization

CYROID uses external Docker networks for isolation. Initialize them before first run:

```bash
# Create required networks
./scripts/init-networks.sh

# Output:
# === Initializing CYROID Networks ===
# Created cyroid-mgmt (172.30.0.0/24)
# Created cyroid-ranges (172.30.1.0/24)
# Created traefik-routing
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Web UI | http://localhost | Self-register |
| API Docs | http://localhost/api/v1/docs | JWT required |
| Traefik Dashboard | http://localhost:8080 | None |
| MinIO Console | http://localhost:9001 | See .env |

### First Steps

1. **Register**: Navigate to http://localhost and create an account
2. **Create Template**: Go to Templates → Add Template → Configure a VM template
3. **Build Range**: Go to Ranges → New Range → Add VMs and networks
4. **Deploy**: Click Deploy to provision all resources (creates DinD container)
5. **Access VMs**: Use the VNC console to interact with running VMs

---

## Platform Support

CYROID runs natively on both **x86_64** and **ARM64** architectures (Apple Silicon, AWS Graviton, Raspberry Pi, etc.).

### Architecture Compatibility Matrix

| Feature | x86_64 | ARM64 |
|---------|--------|-------|
| Core Platform (API, Frontend, DB) | ✅ Native | ✅ Native |
| DinD Range Containers | ✅ Native | ✅ Native |
| Linux Containers | ✅ Native | ✅ Native |
| Linux VMs (Ubuntu, Debian, Fedora, Alpine, Rocky, Alma, Kali) | ✅ Native | ✅ Native |
| Linux VMs (Arch, Manjaro, Security Onion, others) | ✅ Native | ⚠️ Emulated |
| Windows VMs (all versions) | ✅ Native | ⚠️ Emulated |
| VyOS Router | ✅ Native | ⚠️ Emulated |

### Running on ARM64 Hosts

When running CYROID on ARM64 hosts (e.g., Apple Silicon Macs, AWS Graviton instances):

**Native Performance:**
- All core platform services (API, database, cache, storage) run natively
- DinD range containers run natively
- Docker containers run natively
- Linux VMs for supported distributions download ARM64 ISOs automatically

**Emulated (x86 via QEMU):**
- Arch Linux, Manjaro, Security Onion, and other x86-only distributions
- All Windows VMs (Windows ARM support planned for future release)
- VyOS routers

**Performance Expectations:**

| Mode | Performance | Use Case |
|------|-------------|----------|
| Native ARM64 | 100% | Production on ARM infrastructure |
| Emulated x86 | 5-10% | Development, testing, demos |

> **Note:** The UI displays inline warnings when VMs will run via emulation, allowing you to understand performance implications before deployment.

---

## Project Structure

```
CYROID/
├── backend/                    # FastAPI Application
│   ├── cyroid/
│   │   ├── main.py            # Application entry point
│   │   ├── config.py          # Configuration management
│   │   ├── database.py        # SQLAlchemy setup
│   │   ├── api/               # REST API endpoints
│   │   │   ├── auth.py        # Authentication
│   │   │   ├── ranges.py      # Range management
│   │   │   ├── vms.py         # VM lifecycle
│   │   │   ├── networks.py    # Network configuration
│   │   │   ├── blueprints.py  # Range blueprints
│   │   │   ├── content.py     # Content Library
│   │   │   ├── events.py      # Training Events
│   │   │   ├── cache.py       # Image Cache
│   │   │   ├── artifacts.py   # Artifact repository
│   │   │   ├── msel.py        # MSEL operations
│   │   │   └── websocket.py   # Real-time events
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── dind_service.py         # DinD container management
│   │   │   ├── docker_service.py       # Docker orchestration
│   │   │   ├── range_deployment_service.py  # Range lifecycle
│   │   │   ├── blueprint_export_service.py  # Blueprint export/import
│   │   │   ├── event_service.py        # Event broadcasting
│   │   │   └── storage_service.py      # MinIO storage
│   │   └── tasks/             # Async workers (Dramatiq)
│   ├── alembic/               # Database migrations
│   ├── tests/                 # Test suite
│   └── Dockerfile
│
├── frontend/                   # React Application
│   ├── src/
│   │   ├── pages/             # Page components
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Ranges.tsx
│   │   │   ├── RangeDetail.tsx
│   │   │   ├── ExecutionConsole.tsx
│   │   │   ├── VMLibrary.tsx        # VM Library (base images)
│   │   │   ├── ImageCache.tsx       # Docker image cache
│   │   │   ├── ContentLibrary.tsx   # Content management
│   │   │   ├── StudentLab.tsx       # Student lab view
│   │   │   └── TrainingEvents.tsx   # Event scheduling
│   │   ├── components/        # Reusable components
│   │   │   ├── range-builder/
│   │   │   ├── console/
│   │   │   ├── notifications/       # Toast + bell dropdown
│   │   │   └── execution/
│   │   ├── stores/            # Zustand stores
│   │   ├── providers/         # React context providers
│   │   ├── services/          # API client
│   │   └── types/             # TypeScript types
│   └── Dockerfile
│
├── data/                       # Runtime data (gitignored, created at startup)
│   ├── images/                # Catalog-installed Dockerfile projects
│   └── scenarios/             # Catalog-installed training scenarios
│
├── scripts/                    # Utility scripts
│   ├── init-networks.sh       # Network initialization
│   └── build-dind-image.sh    # Custom DinD build
│
├── docs/                       # Documentation
│   └── plans/                 # Development plans
│
├── .github/workflows/          # GitHub Actions CI/CD
│   └── docker-publish.yml     # Build and push to GHCR
├── certs/                      # SSL certificates
├── docker-compose.yml          # Production (GHCR images)
├── docker-compose.dev.yml      # Development (local builds)
├── traefik.yml                 # Traefik static config
├── CLAUDE.md                   # AI assistant context
└── README.md                   # This file
```

---

## Roadmap

### Phase Overview

```
Phase 1: Core Infrastructure        ████████████████████ 100% ✅
Phase 2: Network & Deployment       ████████████████████ 100% ✅
Phase 3: Templates & Artifacts      ████████████████████ 100% ✅
Phase 4: Execution & Monitoring     ████████████████████ 100% ✅
Phase 5: Evidence & Scoring         ████████░░░░░░░░░░░░  40% 🟡
Phase 6: Automation & Intelligence  ███░░░░░░░░░░░░░░░░░  17% 🟡
Phase 7: Advanced Features          ░░░░░░░░░░░░░░░░░░░░   0% ⏳
```

### Milestone Details

#### Phase 1-4: Foundation (Complete)
- User authentication and RBAC/ABAC
- VM template library with 27+ OS options
- Visual range builder with drag-drop networking
- Full VM lifecycle management
- VNC console access with pop-out windows
- Range templating (import/export/clone)
- Comprehensive export with Docker images
- Event logging and real-time monitoring

#### Phase 4.5: DinD Isolation (Complete - v0.11.0)
- [x] Docker-in-Docker range containers
- [x] Complete network namespace isolation
- [x] Multiple ranges with identical IP spaces
- [x] Simplified range deployment/cleanup

#### Phase 5: Evidence & Scoring (Current)
- [ ] Evidence submission portal (upload interface)
- [ ] Manifest.csv parser
- [ ] Chain of custody form
- [ ] Automated hash verification
- [ ] Evaluator review interface
- [ ] Basic automated scoring
- [ ] Metrics export (CSV/PDF)

#### Phase 6: Automation & Intelligence
- [ ] MSEL time-based scheduling
- [ ] Automated inject execution
- [ ] Attack scenario automation
- [ ] Advanced scoring (timeline reconstruction)
- [ ] CAC/PKI authentication
- [x] Offline deployment mode (via comprehensive export)

#### Phase 7: Advanced Features
- [ ] Purple team integration (Caldera, Atomic Red Team)
- [ ] Collaborative range editing
- [ ] Custom report builder
- [ ] AAR auto-generation
- [ ] Advanced analytics dashboard

### Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Range deployment time (10 VMs) | < 5 minutes | ~3 minutes |
| VM console latency | < 500ms | ~200ms |
| Concurrent ranges supported | 10+ | Unlimited (DinD isolated) |
| VM templates available | 30+ | 27 |
| API response time (p95) | < 200ms | ~150ms |

---

## API Reference

Full API documentation available at `http://localhost/api/v1/docs` (Swagger UI) when the server is running.

### Key Endpoints

#### Authentication
```
POST   /api/v1/auth/register      # Create account
POST   /api/v1/auth/login         # Get JWT token
GET    /api/v1/auth/me            # Current user info
```

#### Ranges
```
GET    /api/v1/ranges             # List all ranges
POST   /api/v1/ranges             # Create range
GET    /api/v1/ranges/{id}        # Get range details
PUT    /api/v1/ranges/{id}        # Update range
DELETE /api/v1/ranges/{id}        # Delete range (removes DinD container)
POST   /api/v1/ranges/{id}/deploy # Deploy range (creates DinD container)
POST   /api/v1/ranges/{id}/start  # Start all VMs
POST   /api/v1/ranges/{id}/stop   # Stop all VMs
GET    /api/v1/ranges/{id}/export # Export as template
POST   /api/v1/ranges/import      # Import from template
```

#### VMs
```
GET    /api/v1/vms                # List VMs
POST   /api/v1/vms                # Create VM
POST   /api/v1/vms/{id}/start     # Start VM
POST   /api/v1/vms/{id}/stop      # Stop VM
GET    /api/v1/vms/{id}/vnc-info  # Get VNC access info
GET    /api/v1/vms/{id}/stats     # Resource statistics
POST   /api/v1/vms/{id}/networks/{net_id}  # Add network
DELETE /api/v1/vms/{id}/networks/{net_id}  # Remove network
```

#### Networks
```
GET    /api/v1/networks           # List networks
POST   /api/v1/networks           # Create network
DELETE /api/v1/networks/{id}      # Delete network
```

#### WebSocket
```
WS     /api/v1/ws/events/{range_id}   # Real-time events
WS     /api/v1/ws/console/{vm_id}     # VM console stream
```

---

## User Roles

| Role | Capabilities |
|------|-------------|
| **Admin** | Full system access, user management, all ranges, system configuration |
| **Range Engineer** | Create/edit ranges, manage templates, deploy/teardown ranges |
| **White Cell** | Execute ranges, trigger injects, monitor progress, manage evidence |
| **Evaluator** | Review evidence, score submissions, generate reports |
| **Student** | Access assigned ranges, submit evidence (future) |

Access control uses ABAC (Attribute-Based Access Control) with resource tags for fine-grained sharing between teams.

---

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://cyroid:cyroid@172.30.0.11:5432/cyroid

# Redis
REDIS_URL=redis://172.30.0.12:6379/0

# MinIO
MINIO_ENDPOINT=172.30.0.13:9000
MINIO_ACCESS_KEY=cyroid
MINIO_SECRET_KEY=<secure-password>

# JWT
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Data Directory (REQUIRED on macOS - must be under /Users)
# macOS: CYROID_DATA_DIR=/Users/yourname/.cyroid
# Linux: CYROID_DATA_DIR=/data/cyroid (default)
CYROID_DATA_DIR=/data/cyroid

# Storage Paths (derived from CYROID_DATA_DIR)
ISO_CACHE_DIR=${CYROID_DATA_DIR}/iso-cache
TEMPLATE_STORAGE_DIR=${CYROID_DATA_DIR}/template-storage
VM_STORAGE_DIR=${CYROID_DATA_DIR}/vm-storage

# DinD Configuration
DIND_IMAGE=ghcr.io/jongodb/cyroid-dind:latest
DIND_STARTUP_TIMEOUT=60
DIND_DOCKER_PORT=2375
```

### Network Configuration

| Network | Subnet | Purpose |
|---------|--------|---------|
| cyroid-mgmt | 172.30.0.0/24 | CYROID infrastructure services |
| cyroid-ranges | 172.30.1.0/24 | Range DinD containers |
| traefik-routing | Dynamic | Traefik service routing |

### Service IP Addresses (cyroid-mgmt)

| Service | IP Address | Port | Purpose |
|---------|------------|------|---------|
| API | 172.30.0.10 | 8000 | FastAPI backend |
| Database | 172.30.0.11 | 5432 | PostgreSQL |
| Redis | 172.30.0.12 | 6379 | Cache & queue |
| MinIO | 172.30.0.13 | 9000/9001 | Object storage |
| Traefik | 172.30.0.14 | 80/443/8080 | Reverse proxy |
| Worker | 172.30.0.15 | - | Dramatiq worker |
| Registry | 172.30.0.16 | 5000 | Local Docker registry |
| Frontend | 172.30.0.20 | 80 | React web UI |

### VM Resource Defaults

| OS Type | CPU | RAM | Disk |
|---------|-----|-----|------|
| Linux Container | 2 | 2 GB | - |
| Linux VM | 2 | 2 GB | 30 GB |
| Windows Workstation | 2 | 4 GB | 60 GB |
| Windows Server | 4 | 8 GB | 80 GB |

### DinD Range Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| Memory Limit | 8g | Per-range DinD container |
| CPU Limit | 4.0 | Per-range DinD container |
| Docker Port | 2375 | Internal Docker daemon |

---

## Troubleshooting

### Common Issues

<details>
<summary><strong>Network Initialization Errors</strong></summary>

```bash
# Networks must be created before docker-compose up
./scripts/init-networks.sh

# If networks already exist with different config
docker network rm cyroid-mgmt cyroid-ranges traefik-routing
./scripts/init-networks.sh
```
</details>

<details>
<summary><strong>DinD Container Won't Start</strong></summary>

```bash
# Check Docker daemon status
docker info

# Verify privileged mode is allowed
docker run --rm --privileged docker:24-dind dockerd --help

# Check range container logs
docker logs cyroid-range-<range-id-first-12-chars>
```
</details>

<details>
<summary><strong>Docker Connection Errors</strong></summary>

```bash
# Verify Docker daemon
sudo systemctl status docker

# Check socket permissions
ls -la /var/run/docker.sock

# Add user to docker group
sudo usermod -aG docker $USER
# Logout and login again
```
</details>

<details>
<summary><strong>Windows VM Won't Start (KVM Error)</strong></summary>

```bash
# Check KVM support
lsmod | grep kvm
kvm-ok

# Enable KVM modules
sudo modprobe kvm
sudo modprobe kvm_intel  # or kvm_amd

# Add user to kvm group
sudo usermod -aG kvm $USER
```
</details>

<details>
<summary><strong>VNC Console Not Accessible</strong></summary>

```bash
# Verify VM has display_type="desktop"
# Check traefik can reach range network
docker network inspect cyroid-ranges

# Verify DinD container is running
docker ps | grep cyroid-range

# Check traefik logs
docker-compose logs traefik
```
</details>

<details>
<summary><strong>Database Migration Errors</strong></summary>

```bash
# Run migrations manually
docker-compose exec api alembic upgrade head

# Reset database (development only)
docker-compose exec db psql -U cyroid -d cyroid \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker-compose exec api alembic upgrade head
```
</details>

---

## Development

### Running Tests

```bash
# Backend unit tests
docker-compose exec api pytest tests/unit -v

# Backend integration tests
docker-compose exec api pytest tests/integration -v

# Frontend tests
docker-compose exec frontend npm test

# E2E tests (Playwright)
docker-compose exec frontend npm run test:e2e
```

### Code Style

- **Python**: Black + isort + flake8
- **TypeScript**: ESLint + Prettier
- **Commits**: Semantic versioning (`feat:`, `fix:`, `perf:`, `docs:`)

### Database Migrations

```bash
# Create new migration
docker-compose exec api alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback one migration
docker-compose exec api alembic downgrade -1
```

### Building Custom DinD Image

```bash
# Build optimized DinD image
./scripts/build-dind-image.sh

# Use custom image
export DIND_IMAGE=cyroid-dind:latest
docker-compose up -d
```

### Developer Notes

#### Running in Development Mode

For local development with hot-reload and local builds:

```bash
# Start with development overrides (local builds + hot-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Or copy dev file to override for automatic loading
cp docker-compose.dev.yml docker-compose.override.yml
docker compose up -d
```

#### Applying Backend Changes

After modifying backend Python files, restart the API container to apply changes:

```bash
# Restart API to apply backend code changes
docker compose restart api

# Or for a full rebuild
docker compose up -d --build api
```

> **Note:** Frontend changes auto-reload via Vite hot module replacement (HMR). Backend changes require an API restart.

#### Keeping Up with Latest Tags

To pull the most recent images from GHCR:

```bash
# Pull latest images
docker compose pull

# Or pull and restart
docker compose pull && docker compose up -d
```

#### Common Development Workflow

```bash
# 1. Pull latest code
git pull origin master

# 2. Start services with dev overrides
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. After backend changes, restart API
docker compose restart api

# 4. Check logs
docker compose logs -f api
```

---

## Contributing

1. Check the `CLAUDE.md` file for project context and conventions
2. Review the roadmap for current priorities
3. Follow semantic commit messages
4. Update tests for new features
5. Update documentation as needed

---

## License

Licensed under the **GNU Affero General Public License v3.0** — see
[LICENSE](LICENSE) for the full text.

AGPL-3.0 is a network copyleft license: if you modify this software and make it
available to users over a network, you must also offer those users the
corresponding source. For alternative licensing terms, open an issue to start a
conversation.

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.35.5 | 2026-01-30 | Non-interactive mode, admin CLI flags, service healthchecks |
| 0.35.4 | 2026-01-30 | API health endpoints, OpenAPI docs config, registry bootstrap |
| 0.35.3 | 2026-01-30 | Linux amd64 deployment fixes (frontend healthcheck, traefik routing) |
| 0.35.2 | 2026-01-30 | Image backup/restore feature |
| 0.35.1 | 2026-01-30 | Multi-arch platform detection in deploy script |
| 0.34.8 | 2026-01-29 | CI fix for cyroid-dind insecure-registries |
| 0.34.7 | 2026-01-29 | Full-screen TUI with live dashboard |
| 0.34.6 | 2026-01-29 | TUI version selection, admin user creation, back navigation |
| 0.34.5 | 2026-01-29 | Self-contained deploy.sh TUI |
| 0.34.0 | 2026-01-28 | Registry refactor, catalog storefront UI |
| 0.30.0 | 2026-01-27 | Content catalog, scenario installation |
| 0.23.5 | 2026-01-25 | Notification dropdown positioning fix |
| 0.23.1 | 2026-01-24 | Blueprint export/import v3.0 with Dockerfiles |
| 0.23.0 | 2026-01-24 | Global notifications, clipboard sync, deployment progress |
| 0.22.0 | 2026-01-23 | Content Library for Student Lab walkthroughs |
| 0.21.x | 2026-01-22 | VNC fixes, DinD container config, ISO VM support |
| 0.20.0 | 2026-01-21 | Image Cache consolidation, GHCR publishing |
| 0.11.0 | 2026-01-19 | DinD isolation for all ranges |
| 0.10.0 | 2026-01-16 | Multi-architecture support (x86_64 + ARM64) |

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Backend LoC | ~40,000 Python |
| Frontend LoC | ~33,000 TypeScript |
| Database Models | 21+ |
| API Endpoints | 250+ |
| Supported OS Templates | 27+ |
| Development Phase | 5 of 7 (71%) |

---

<p align="center">
  <strong>CYROID</strong> - Cyber Range Orchestrator In Docker<br>
  <em>Built for secure, scalable cyber training environments</em>
</p>
