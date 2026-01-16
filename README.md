<p align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-brightgreen" alt="Status">
  <img src="https://img.shields.io/badge/Phase-4%20of%207-blue" alt="Phase">
  <img src="https://img.shields.io/badge/Version-0.4.0--alpha-orange" alt="Version">
  <img src="https://img.shields.io/badge/License-Proprietary-red" alt="License">
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

## Overview

**CYROID** is a comprehensive web-based cyber range orchestration platform designed to automate the instantiation, management, and execution of Docker-based cyber training environments. Built for military, government, and educational institutions, CYROID enables rapid deployment of isolated, networked cyber environments for training, evaluation, and security testing.

### Key Capabilities

- **Full Lifecycle Management**: Planning → Development → Deployment → Execution → Teardown
- **Multi-OS Support**: Linux containers, Linux VMs (QEMU/KVM), Windows VMs (dockur/windows)
- **Network Isolation**: Complete Docker network segmentation with custom subnets
- **Web-Based Console**: VNC access to all VMs through browser
- **Scenario Automation**: MSEL (Master Scenario Events List) execution engine
- **Evidence Management**: Student submission, validation, and automated scoring

---

## Features

### Implemented (Phases 1-4)

| Category | Feature | Status |
|----------|---------|--------|
| **Authentication** | JWT-based auth with role management | ✅ Complete |
| **User Management** | RBAC (Admin, Range Engineer, White Cell, Evaluator) | ✅ Complete |
| **VM Templates** | CRUD operations, OS library (24+ Linux distros, Windows 7-11, Server 2003-2025) | ✅ Complete |
| **Range Builder** | Visual drag-drop network designer | ✅ Complete |
| **Network Management** | Multi-segment Docker networks with custom subnets | ✅ Complete |
| **VM Lifecycle** | Create, start, stop, restart, delete with real-time status | ✅ Complete |
| **VNC Console** | Web-based graphical access via Traefik proxy | ✅ Complete |
| **Dynamic Networking** | Add/remove network interfaces on running VMs | ✅ Complete |
| **Range Templating** | Import/export/clone range configurations | ✅ Complete |
| **Resource Monitoring** | CPU, memory, network statistics per VM | ✅ Complete |
| **Event Logging** | Timestamped activity feed with real-time streaming | ✅ Complete |
| **Artifact Repository** | MinIO-backed storage with SHA256 hashing | ✅ Complete |
| **Snapshot Management** | Golden images for Windows, Docker snapshots | ✅ Complete |
| **Execution Console** | Multi-panel dashboard with VM grid | ✅ Complete |
| **MSEL Parser** | Markdown/YAML inject timeline | ✅ Complete |
| **Manual Injects** | Trigger scenario events from console | ✅ Complete |
| **ABAC** | Attribute-based access control with resource tags | ✅ Complete |

### In Development (Phase 5)

| Feature | Progress | Target |
|---------|----------|--------|
| Evidence Submission Portal | 🟡 70% | Phase 5 |
| Automated Evidence Validation | 🟡 50% | Phase 5 |
| Scoring Engine | 🟡 30% | Phase 5 |
| Network Traffic Visualization | 🟡 60% | Phase 5 |

### Planned (Phases 6-7)

| Feature | Phase | Priority |
|---------|-------|----------|
| MSEL Time-based Automation | 6 | High |
| Attack Scenario Scripts | 6 | High |
| CAC/PKI Authentication | 6 | Medium |
| Offline/Air-gap Mode | 6 | Medium |
| Purple Team Integration (Caldera) | 7 | Medium |
| Collaborative Range Editing | 7 | Low |
| Advanced Reporting & Analytics | 7 | Low |
| Custom Report Builder | 7 | Low |
| AAR Auto-generation | 7 | Low |

---

## Architecture

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
│                     Traefik Reverse Proxy (v3)                           │
│           HTTP Routing • VNC Path Proxy • SSL/TLS Termination            │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────┐
│                   FastAPI Backend (Python 3.12)                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        API Layer                                  │    │
│  │  /auth  /users  /ranges  /vms  /networks  /templates  /artifacts │    │
│  │  /events  /msel  /evidence  /cache  /snapshots  /websocket       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      Service Layer                                │    │
│  │  DockerService • EventService • MSELParser • StorageService      │    │
│  │  InjectService • ConnectionService • ValidationEngine            │    │
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
    │ • Users    │  │ • Cache    │  │ • ISOs │  │ • VMs    │
    │ • Ranges   │  │ • Queue    │  │ • Tmpl │  │ • Nets   │
    │ • VMs      │  │ • Sessions │  │ • Artf │  │ • Vols   │
    │ • Events   │  │            │  │        │  │          │
    └────────────┘  └────────────┘  └────────┘  └──────────┘
                                                      │
                           ┌──────────────────────────┴───────────────────┐
                           │           VM Container Types                 │
                           ├──────────────────────────────────────────────┤
                           │  ┌─────────────┐  ┌─────────────────────┐   │
                           │  │   Docker    │  │   Linux VMs         │   │
                           │  │ Containers  │  │   (qemus/qemu)      │   │
                           │  │             │  │                     │   │
                           │  │ • Ubuntu    │  │ • Ubuntu  • Debian  │   │
                           │  │ • Alpine    │  │ • Fedora  • Rocky   │   │
                           │  │ • Debian    │  │ • Arch    • Mint    │   │
                           │  │ • CentOS    │  │ • Kali    • Parrot  │   │
                           │  └─────────────┘  └─────────────────────┘   │
                           │  ┌─────────────────────────────────────────┐│
                           │  │           Windows VMs                   ││
                           │  │         (dockur/windows)                ││
                           │  │                                         ││
                           │  │ • Windows 7/8/10/11                     ││
                           │  │ • Windows Server 2003-2025              ││
                           │  │ • KVM/QEMU acceleration                 ││
                           │  └─────────────────────────────────────────┘│
                           └──────────────────────────────────────────────┘
```

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
| | Python | 3.12 | Runtime |
| | SQLAlchemy | 2.0 | ORM |
| | Alembic | 1.13 | Migrations |
| | Dramatiq | 1.15 | Task Queue |
| | Docker SDK | 7.1 | Container Orchestration |
| **Infrastructure** | PostgreSQL | 16 | Primary Database |
| | Redis | 7 | Cache & Queue |
| | MinIO | Latest | Object Storage (S3) |
| | Traefik | 3.x | Reverse Proxy |
| | Docker | 24+ | Container Runtime |

### Network Segmentation Architecture

CYROID uses VyOS router containers to provide per-range network isolation, NAT, and routing:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Docker Host                                       │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │               Management Network (10.10.0.0/16)                        │ │
│  │                      cyroid-management                                 │ │
│  └─────────┬──────────────────┬──────────────────┬───────────────────────┘ │
│            │                  │                  │                         │
│       ┌────┴────┐        ┌────┴────┐        ┌────┴────┐                    │
│       │ CYROID  │        │ Traefik │        │ VyOS-1  │                    │
│       │   API   │        │         │        │ Router  │                    │
│       └─────────┘        └─────────┘        └────┬────┘                    │
│                                                  │                         │
│        Range 1                                   │                         │
│  ┌───────────────────────────────────────────────┘                         │
│  │                                                                         │
│  │  eth1 ──► Network A (10.0.1.0/24) ──┬── VM1 (10.0.1.10)                │
│  │                                      └── VM2 (10.0.1.11)                │
│  │                                                                         │
│  │  eth2 ──► Network B (10.0.2.0/24) ──── VM3 (10.0.2.10)                 │
│  └─────────────────────────────────────────────────────────────────────────┘
└────────────────────────────────────────────────────────────────────────────┘
```

**Key Features:**

| Feature | Description |
|---------|-------------|
| **Per-Range VyOS Router** | Each range gets a dedicated VyOS container for routing/NAT |
| **Management Network** | 10.10.0.0/16 for CYROID ↔ VyOS communication |
| **Network Isolation** | Shield icon toggle - VyOS firewall blocks external access |
| **Internet Access** | Globe icon toggle - VyOS NAT enables per-network internet |
| **VNC Unaffected** | Traefik connects directly to range networks for console access |

**Network Connectivity Matrix:**

| is_isolated | internet_enabled | Result |
|-------------|------------------|--------|
| ✓ | ✗ | No external access, deny all outbound |
| ✓ | ✓ | NAT to internet via VyOS, isolated from host |
| ✗ | ✗ | Direct Docker bridge access |
| ✗ | ✓ | Full internet + host access |

---

## Quick Start

### Prerequisites

- Docker Engine 24.0+
- Docker Compose 2.20+
- KVM support (for Windows VMs): `lsmod | grep kvm`
- Minimum resources: 16 CPU cores, 32GB RAM, 500GB disk

### Installation

```bash
# Clone the repository
git clone <repository-url> CYROID
cd CYROID

# Copy environment template
cp .env.example .env

# Generate secure secrets
sed -i "s/your-secret-key-here/$(openssl rand -hex 32)/" .env

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps

# Check API health
curl http://localhost:8000/health
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Web UI | http://localhost | Self-register |
| API Docs | http://localhost:8000/docs | JWT required |
| Traefik Dashboard | http://localhost:8080 | None |
| MinIO Console | http://localhost:9001 | See .env |

### First Steps

1. **Register**: Navigate to http://localhost and create an account
2. **Create Template**: Go to Templates → Add Template → Configure a VM template
3. **Build Range**: Go to Ranges → New Range → Add VMs and networks
4. **Deploy**: Click Deploy to provision all resources
5. **Access VMs**: Use the VNC console to interact with running VMs

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
│   │   │   ├── templates.py   # VM templates
│   │   │   ├── artifacts.py   # Artifact repository
│   │   │   ├── msel.py        # MSEL operations
│   │   │   └── websocket.py   # Real-time events
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── docker_service.py
│   │   │   ├── event_service.py
│   │   │   └── storage_service.py
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
│   │   │   └── Templates.tsx
│   │   ├── components/        # Reusable components
│   │   │   ├── range-builder/
│   │   │   ├── console/
│   │   │   └── execution/
│   │   ├── stores/            # Zustand stores
│   │   ├── services/          # API client
│   │   └── types/             # TypeScript types
│   └── Dockerfile
│
├── docs/                       # Documentation
│   └── plans/                 # Development plans
│
├── certs/                      # SSL certificates
├── docker-compose.yml          # Service orchestration
├── traefik-dynamic.yml         # Traefik configuration
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
Phase 6: Automation & Intelligence  ░░░░░░░░░░░░░░░░░░░░   0% ⏳
Phase 7: Advanced Features          ░░░░░░░░░░░░░░░░░░░░   0% ⏳
```

### Milestone Details

#### Phase 1-4: Foundation (Complete)
- User authentication and RBAC
- VM template library with 24+ OS options
- Visual range builder with drag-drop networking
- Full VM lifecycle management
- VNC console access
- Range templating (import/export/clone)
- Event logging and real-time monitoring

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
- [ ] Offline deployment mode

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
| Concurrent ranges supported | 10+ | Tested: 5 |
| VM templates available | 30+ | 27 |
| API response time (p95) | < 200ms | ~150ms |

---

## API Reference

Full API documentation available at `http://localhost:8000/docs` (Swagger UI) when the server is running.

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
DELETE /api/v1/ranges/{id}        # Delete range
POST   /api/v1/ranges/{id}/deploy # Deploy range
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
DATABASE_URL=postgresql://cyroid:cyroid@db:5432/cyroid

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=cyroid
MINIO_SECRET_KEY=<secure-password>

# JWT
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Storage Paths
ISO_CACHE_DIR=/data/cyroid/iso-cache
TEMPLATE_STORAGE_DIR=/data/cyroid/template-storage
VM_STORAGE_DIR=/data/cyroid/vm-storage

# Docker
DOCKER_HOST=unix:///var/run/docker.sock
```

### VM Resource Defaults

| OS Type | CPU | RAM | Disk |
|---------|-----|-----|------|
| Linux Container | 2 | 2 GB | - |
| Linux VM | 2 | 2 GB | 30 GB |
| Windows Workstation | 2 | 4 GB | 60 GB |
| Windows Server | 4 | 8 GB | 80 GB |

### Limits

| Parameter | Soft Limit | Hard Limit |
|-----------|------------|------------|
| VMs per Range | 25 (warning) | 50 (enforced) |
| Networks per Range | - | 20 |
| Concurrent Ranges | - | Based on host resources |

---

## Troubleshooting

### Common Issues

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
# Check traefik network exists
docker network ls | grep traefik

# Verify VM is running
docker ps | grep <vm-name>

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

---

## Contributing

1. Check the `CLAUDE.md` file for project context and conventions
2. Review the roadmap for current priorities
3. Follow semantic commit messages
4. Update tests for new features
5. Update documentation as needed

---

## License

Proprietary - All Rights Reserved

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Backend LoC | ~4,000+ Python |
| Frontend LoC | ~3,000+ TypeScript |
| Database Models | 15+ |
| API Endpoints | 50+ |
| Supported OS Templates | 27+ |
| Development Phase | 4 of 7 (57%) |

---

<p align="center">
  <strong>CYROID</strong> - Cyber Range Orchestrator In Docker<br>
  <em>Built for secure, scalable cyber training environments</em>
</p>
