# CYROID MVP Design Document

**Date:** 2026-01-12
**Status:** Approved
**Scope:** Phases 1-3 (MVP)

---

## Overview

**CYROID** (Cyber Range Orchestrator In Docker) is an open-source platform for creating, deploying, and managing Docker-based cyber training environments.

### Target Audience

- Corporate security teams (internal red/blue team exercises)
- Educational institutions (university cybersecurity programs, CTF competitions)
- Training providers (bootcamps, certification prep)

### Core Goals

- **Simplify range creation** - Visual builder for network topologies, no Docker expertise required
- **Automate deployment** - One-click provisioning of complex multi-VM environments
- **Enable realistic training** - Support Windows and Linux VMs, network segmentation, artifact placement
- **Streamline evaluation** - Artifact repository, evidence collection, basic scoring

### MVP Scope

1. User authentication and role-based access
2. VM template library (Windows/Linux server and desktop variants)
3. Visual network topology builder
4. Multi-segment Docker networking with isolation
5. VM lifecycle management and web console access
6. Reusable range templates with versioning
7. Artifact repository with hash verification
8. Automated artifact placement on VMs
9. Snapshot management
10. End-to-end testing

### Out of Scope for MVP

- MSEL automation (Phase 4)
- Evidence submission portal (Phase 5)
- Scoring engine (Phase 5)
- CAC/PKI authentication (Phase 6)
- Multi-host/clustering (future)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| Cache | Redis |
| Task Queue | Dramatiq |
| Object Storage | MinIO |
| Frontend | React + TypeScript |
| Styling | TailwindCSS |
| Visual Builder | React Flow |
| Reverse Proxy | Traefik |
| Testing | pytest, Vitest, Playwright |

---

## Architecture

```
+------------------------------------------------------------------+
|                         Browser (React SPA)                       |
+-----------------------------+------------------------------------+
                              | HTTPS
+-----------------------------v------------------------------------+
|                      Traefik (Reverse Proxy)                      |
+-----------+--------------------------------------+----------------+
            |                                      |
+-----------v-----------+          +---------------v----------------+
|   FastAPI Backend     |<-------->|   React Frontend (static)      |
|   (REST + WebSocket)  |          +--------------------------------+
+-----------+-----------+
            |
      +-----+------------------+------------------+
      |     |                  |                  |
+-----v---+ | +----------------v----+  +----------v-------+
|Postgres | | |      Redis          |  |     MinIO        |
|  (DB)   | | | (Cache + Queue)     |  | (Artifacts)      |
+---------+ | +---------+-----------+  +------------------+
            |           |
      +-----v-----------v-----+
      |   Dramatiq Workers    |
      |   (Async VM Ops)      |
      +-----------+-----------+
                  |
      +-----------v-----------+
      |     Docker Daemon     |
      |  +-----+ +-----+      |
      |  | VM1 | | VM2 | ...  |
      |  +-----+ +-----+      |
      |     Range Networks    |
      +-----------------------+
```

### Key Architectural Decisions

- **Monolithic API** with plugin extension points (not microservices)
- **Async task processing** via Dramatiq for VM provisioning, artifact placement, snapshots
- **WebSocket** for real-time updates (deployment progress, VM status, console)
- **Plugin interfaces** for auth, VM providers, and scoring (future extensibility)
- **Single-host deployment** (clustering deferred to future)

---

## Plugin System

Plugins extend CYROID without modifying core code. Designed for future open core transition.

### Plugin Types

| Type | Interface | Core Implementation | Future Examples |
|------|-----------|---------------------|-----------------|
| `AuthProvider` | `authenticate()`, `get_user()`, `validate_token()` | Local (username/password + JWT) | SAML, LDAP, CAC/PKI |
| `VMProvider` | `create()`, `start()`, `stop()`, `destroy()`, `exec()` | Docker, dockur/windows | Proxmox, VMware |
| `StorageProvider` | `upload()`, `download()`, `delete()`, `list()` | MinIO | S3, Azure Blob |
| `ScoringProvider` | `evaluate()`, `calculate_score()` | Basic (hash match, presence) | AI-assisted, rubric-based |

### Plugin Configuration

```yaml
# config/plugins.yaml
plugins:
  auth:
    provider: local
    config:
      jwt_expire_minutes: 60
  vm:
    providers:
      - docker
      - dockur
  storage:
    provider: minio
    config:
      endpoint: localhost:9000
      bucket: cyroid-artifacts
```

---

## Data Models

### Entity Relationships

```
User -----------------------+
  |                         |
  | creates                 | assigned to
  v                         v
VMTemplate                Range <---------------------+
  |                         |                         |
  | based on                | contains                | references
  v                         v                         |
  +----------------->     VM <---- ArtifactPlacement -+
                           |              ^
                           | connected    | places
                           v              |
                       Network        Artifact
                           |
                           | has
                           v
                       Snapshot
```

### Key Models

| Model | Key Fields |
|-------|------------|
| `User` | id, username, email, hashed_password, role (admin/engineer/facilitator/evaluator) |
| `VMTemplate` | id, name, os_type, os_variant, base_image, default_specs, config_script, tags |
| `Range` | id, name, status, created_by, networks[], vms[] |
| `Network` | id, range_id, name, subnet (CIDR), gateway, isolation_level |
| `VM` | id, range_id, network_id, template_id, hostname, ip_address, specs, status, container_id |
| `Artifact` | id, name, file_path, sha256_hash, artifact_type, malicious_indicator, ttps[], uploaded_by |
| `ArtifactPlacement` | id, artifact_id, vm_id, target_path, placement_time, status |
| `Snapshot` | id, vm_id, name, created_at, docker_image_id |

### Status Enums

- **Range Status**: `draft` -> `deploying` -> `running` -> `stopped` -> `archived`
- **VM Status**: `pending` -> `creating` -> `running` -> `stopped` -> `error`
- **Placement Status**: `pending` -> `in_progress` -> `placed` -> `verified` -> `failed`

---

## VM Template Library

### Windows Templates

- **Windows Server**: Domain Controller, File Server, Web Server (IIS), DNS, baseline
- **Windows Desktop**: Windows 10/11 workstation variants (analyst, finance, developer personas)

### Linux Templates

- **Linux Server**: Web (Apache/Nginx), DNS (BIND), File (Samba/NFS), SIEM, baseline
- **Linux Desktop**: Ubuntu/Debian workstation, analyst tools, clean baseline

---

## Docker Orchestration

### Linux VMs

Standard Docker container management:
- Base images: `ubuntu:22.04`, `rockylinux:9`, `debian:12`
- Persistent storage via Docker volumes
- Network attachment to custom bridge networks
- Config scripts run via `docker exec` post-creation

### Windows VMs (dockur/windows)

Windows requires KVM/QEMU inside container:
- Host must have `/dev/kvm` access
- First boot ~5-10 min (Windows install); subsequent boots from snapshot ~1-2 min
- Pre-cache Windows ISOs and "gold" snapshots
- Console via VNC (port 8006) or RDP (port 3389)
- Higher resources: minimum 4 CPU, 8GB RAM

### Image Sources

| Source | Use Case |
|--------|----------|
| Docker Hub | Default, public images |
| Local Registry | Air-gapped/offline, custom org images |
| Docker Daemon | Images already present on host |
| Tar Upload | Custom images via UI, portable distribution |

**Resolution Order:**
1. Check local Docker daemon
2. Check configured local registry
3. Fall back to Docker Hub (if online)

---

## API Design

### REST Endpoints

```
/api/v1
├── /auth
│   ├── POST /register
│   ├── POST /login
│   └── GET  /me
├── /templates
│   ├── GET    /
│   ├── POST   /
│   ├── GET    /{id}
│   ├── PUT    /{id}
│   ├── DELETE /{id}
│   └── POST   /{id}/clone
├── /ranges
│   ├── GET    /
│   ├── POST   /
│   ├── GET    /{id}
│   ├── PUT    /{id}
│   ├── DELETE /{id}
│   ├── POST   /{id}/deploy
│   ├── POST   /{id}/start
│   ├── POST   /{id}/stop
│   └── POST   /{id}/teardown
├── /vms
│   ├── GET    /{id}
│   ├── POST   /{id}/start
│   ├── POST   /{id}/stop
│   ├── POST   /{id}/restart
│   └── POST   /{id}/snapshot
├── /networks
│   └── (CRUD, managed via range)
├── /artifacts
│   ├── GET    /
│   ├── POST   /upload
│   ├── GET    /{id}
│   ├── DELETE /{id}
│   └── GET    /{id}/download
├── /snapshots
│   ├── GET    /
│   ├── POST   /{vm_id}
│   └── POST   /{id}/restore
└── /admin
    ├── GET    /users
    ├── GET    /images
    ├── POST   /images/upload
    └── GET    /health
```

### WebSocket Channels

| Channel | Purpose |
|---------|---------|
| `/ws/deployment/{range_id}` | Real-time deployment progress |
| `/ws/status/{range_id}` | VM status updates |
| `/ws/console/{vm_id}` | Interactive terminal |
| `/ws/events` | System-wide event stream |

---

## Frontend Design

### Visual Network Builder

```
+------------------------------------------------------------------+
| Range Builder: "Training Range Alpha"                     [Save] |
+---------------+--------------------------------------------------+
|  Components   |                                                  |
|  ----------   |    +----------------------------------+          |
|  [+ Network]  |    |  Corporate Network (172.16.1.0/24)         |
|  [+ Win Srv]  |    |  +------+  +------+  +------+   |          |
|  [+ Win Wks]  |    |  |DC-01 |--|FS-01 |  |WKS-01|   |          |
|  [+ Lin Srv]  |    |  +------+  +------+  +------+   |          |
|  [+ Lin Wks]  |    +----------------------------------+          |
|  [+ Router]   |                    |                             |
|               |    +----------------------------------+          |
|  Templates    |    |  DMZ Network (172.16.2.0/24)     |          |
|  ----------   |    |  +------+  +------+             |          |
|  > DC Ready   |    |  |WEB-01|  |DNS-01|             |          |
|  > File Srv   |    |  +------+  +------+             |          |
|  > Analyst    |    +----------------------------------+          |
|               |                                                  |
+---------------+--------------------------------------------------+
| Properties: DC-01                                                |
| Hostname: [DC-01        ]  IP: [172.16.1.10  ]                  |
| Template: [Windows Server - DC v]  CPU: [4] RAM: [8GB]          |
| Artifacts: [+ Add Artifact]                                      |
+------------------------------------------------------------------+
```

### Execution Console

```
+------------------------------------------------------------------+
| Range: Training Alpha          [Start All] [Stop All] [Teardown] |
+------------------------------------+-----------------------------+
|  VM Status Grid                    |  Event Log                  |
|  +--------+--------+--------+      |  10:42:15 DC-01 started     |
|  | DC-01  | FS-01  | WKS-01 |      |  10:42:18 FS-01 started     |
|  |   OK   |   OK   |  WAIT  |      |  10:42:20 WKS-01 creating   |
|  +--------+--------+--------+      |  10:42:35 Artifact placed   |
|  +--------+--------+               |                             |
|  | WEB-01 | DNS-01 |               |                             |
|  |   OK   |  ERR   |               |                             |
|  +--------+--------+               |                             |
+------------------------------------+-----------------------------+
|  Console: DC-01                                       [Fullscreen]|
|  +--------------------------------------------------------------+|
|  | C:\Users\Administrator> _                                    ||
|  |                                                              ||
|  +--------------------------------------------------------------+|
+------------------------------------------------------------------+
```

### Key UI Patterns

- Drag-drop canvas for topology design
- Properties panel for selected component
- Real-time validation (subnet conflicts, IP duplicates)
- Color-coded status indicators
- Toast notifications for actions
- Modal dialogs for destructive confirmations

---

## Testing Strategy

### Testing Pyramid

| Level | Tool | Focus |
|-------|------|-------|
| Unit | pytest, Vitest | Business logic, validation, plugin interfaces |
| Integration | pytest + testcontainers | API endpoints, DB operations, Docker SDK |
| E2E | Playwright | Critical user journeys |

### Critical E2E Scenarios

1. Auth flow: Register -> Login -> Access dashboard
2. Template management: Create -> Edit -> Clone -> Delete
3. Range lifecycle: Build -> Deploy -> Verify -> Stop -> Teardown
4. Visual builder: Drag VM -> Connect network -> Configure -> Save
5. Artifact flow: Upload -> Assign -> Deploy -> Verify placement
6. Console access: Deploy VM -> Open console -> Execute command
7. Snapshot: Create -> Stop VM -> Restore -> Verify state

---

## Error Handling

### Error Categories

| Category | Strategy |
|----------|----------|
| User errors | 4xx responses, clear messages |
| VM failures | Retry with backoff, surface to UI, manual retry |
| Resource exhaustion | Pre-flight checks, graceful degradation |
| Network issues | Cleanup partial state, atomic operations |
| Plugin failures | Fallback behavior, circuit breaker |

### Deployment Resilience

- **Atomic where possible**: Network creation all-or-nothing
- **Partial success OK**: 9/10 VMs running better than rollback all
- **Clear status**: Every failure reflected in UI
- **Manual recovery**: "Retry failed VMs" button available
- **Cleanup on teardown**: Always attempt full cleanup

---

## Project Structure

```
cyroid/
├── docker-compose.yml
├── docker-compose.test.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/
│   ├── cyroid/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── plugins/
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   └── builtin/
│   │   ├── tasks/
│   │   └── utils/
│   └── tests/
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── services/
│       ├── stores/
│       ├── types/
│       └── utils/
│
├── e2e/
│   └── tests/
│
├── docs/
│   └── plans/
│
└── scripts/
```

---

## Implementation Order

1. **Foundation** - Project structure, Docker Compose, database, auth
2. **Templates** - VM template CRUD, image management
3. **Range Builder** - Data models, basic form-based creation
4. **Docker Integration** - VM lifecycle, Linux containers
5. **Networking** - Multi-segment networks, isolation
6. **Visual Builder** - React Flow canvas, drag-drop
7. **Windows Support** - dockur/windows integration
8. **Console** - WebSocket proxy, xterm.js
9. **Artifacts** - Repository, placement, verification
10. **Snapshots** - Create, restore, management
11. **Testing** - E2E test suite for all critical flows
12. **Polish** - Error handling, UI refinement, documentation

---

## Configuration Defaults

### VM Specs by Type

| Type | CPU | RAM | Disk |
|------|-----|-----|------|
| Windows Server | 4 | 8 GB | 80 GB |
| Windows Desktop | 2 | 4 GB | 60 GB |
| Linux Server | 2 | 4 GB | 40 GB |
| Linux Desktop | 2 | 2 GB | 30 GB |

### Network Defaults

- Pattern: `172.16.{segment_id}.0/24`
- Gateway: `.1` (e.g., `172.16.1.1`)
- Reserved: `172.16.0.0/24` (orchestrator), `172.16.255.0/24` (expansion)

### Naming Convention

- VM: `{range_name}-{hostname}-{short_uuid}`
- Network: `{range_name}-{network_name}-{short_uuid}`
- Container: Same as VM name

---

## Terminology

| Term | Meaning |
|------|---------|
| Range | Complete training environment (VMs + networks) |
| White Cell | Exercise facilitator/controller |
| Blue Team | Defenders |
| Red Team | Attackers |
| MSEL | Master Scenario Events List |
| Inject | Scheduled event in an exercise |
| AAR | After Action Review/Report |
