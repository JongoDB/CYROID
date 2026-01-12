# Cyber Range Orchestrator - Claude Code Development Prompt

## Project Overview
Build a web-based cyber range orchestrator that automates the instantiation, management, and execution of Docker-based cyber training ranges for military/government cyber operations training. The system must support the complete lifecycle: planning → development → execution → teardown/archiving.

## Core Requirements

### Deployment Environment
- **Platform**: Docker on Ubuntu (deployment-agnostic: on-prem, cloud, baremetal, VM)
- **Containerization**: All services run in Docker containers
- **Offline-capable**: Cache VM images and dependencies for air-gapped operation
- **Architecture**: Microservices-based with clear separation of concerns

### Supported VM Types
- **Linux**: RHEL-based (Rocky/Alma) and Debian-based (Ubuntu) via standard Docker images
- **Windows**: Via dockur/windows (KVM/QEMU-based, understand this is VM-in-container)
  - Note: dockur/windows pulls Windows ISO and creates VM automatically
  - Support caching of ISOs and base images for offline deployment
  - No manual license/activation management required (handle via dockur configuration)

### Network Architecture
- **Segmentation**: Docker bridge networks with custom subnets (no VLAN needed)
- **Multi-segment ranges**: Support red team, blue team, eval server, white cell, remediation networks
- **Isolation**: Complete network isolation between concurrent ranges
- **Configurability**: Range engineer specifies subnets, gateway IPs, DNS, routing rules
- **Inter-segment routing**: Controlled connectivity between segments (e.g., student jump box → target network)

## System Architecture

### Technology Stack Recommendation
```
Frontend:
- React with TypeScript for type safety and scalability
- TailwindCSS for rapid UI development
- React Flow or similar for visual network topology designer
- Xterm.js for VM console access
- Recharts for metrics visualization

Backend:
- FastAPI (Python) for main API server
  - Async/await for concurrent operations
  - Pydantic for data validation
  - SQLAlchemy for ORM
- PostgreSQL for relational data (ranges, VMs, users, artifacts)
- Redis for caching and job queues
- Celery for async task processing (VM provisioning, snapshots)

Infrastructure:
- Docker Compose for local development
- Docker Swarm or K8s-ready architecture (start with Swarm)
- MinIO for object storage (VM images, artifacts, evidence)
- Nginx as reverse proxy and static file server
- Traefik alternative for dynamic routing

Monitoring:
- Prometheus for metrics collection from Docker stats
- Grafana for dashboards (optional, embed in app)
- Container logging with structured JSON output
```

### Core Components

#### 1. API Server (`api/`)
- RESTful API with FastAPI
- WebSocket support for real-time updates (VM console, metrics)
- Authentication/authorization (JWT + CAC/PKI support)
- Role-based access control (RBAC)

#### 2. Frontend (`frontend/`)
- Single-page application (SPA)
- Responsive design (desktop primary, tablet secondary)
- Real-time updates via WebSockets
- Intuitive drag-drop interfaces

#### 3. Docker Orchestration Service (`orchestrator/`)
- Docker SDK for Python integration
- VM lifecycle management (create, start, stop, snapshot, destroy)
- Network creation and management
- Volume management for persistence
- Resource monitoring and limits

#### 4. Artifact Management Service (`artifacts/`)
- Secure storage for IOCs, malware samples, tools
- Hash verification (SHA256)
- Chain of custody tracking
- Automated placement on VMs during provisioning
- Malware handling safety controls (encrypted at rest, access logging)

#### 5. MSEL Execution Engine (`msel/`)
- Parse MSEL documents (Markdown/YAML format)
- Time-based inject scheduling
- Manual inject triggering
- Inject verification and logging
- Integration with VM execution (run scripts, place files)

#### 6. Evidence Collection System (`evidence/`)
- Centralized repository for student submissions
- Automated manifest validation
- Hash verification
- Chain of custody enforcement
- Export functionality for grading

#### 7. Scoring Engine (`scoring/`)
- Automated checks (artifact detection, timeline accuracy)
- Evaluation form integration
- Evidence package validation
- Metrics export

## User Interface Requirements

### Dashboard Views by Role

#### Range Engineer Dashboard
- Active ranges overview (status, resource usage)
- Quick actions: Create range, clone template, view metrics
- System health indicators
- Recent activity log

#### White Cell Dashboard
- Assigned range(s) overview
- VM console access (one-click)
- MSEL inject timeline with trigger buttons
- Student progress indicators
- Network traffic monitor
- Evidence submission notifications

#### Evaluator Dashboard
- Scoring interface per student
- Evidence package review
- Automated check results
- Metrics and analytics
- AAR export functionality

#### Student Dashboard (Future)
- Assigned VMs and access info
- Task list from scenario
- Evidence submission interface
- Timer/countdown for exercise window

### Key UI Screens

#### 1. Range Builder (Visual Network Designer)
**Interface**: Drag-drop canvas with component palette

**Components Palette**:
- VM types (Windows Server, Windows Workstation, Linux Server, Linux Workstation)
- Network segments (with subnet configuration)
- Router/firewall (VyOS or simulated)
- Special nodes (Jump box, SIEM, C2 server, File server)

**Properties Panel** (when component selected):
- Hostname
- IP address (auto-suggest from subnet)
- VM specs (CPU cores, RAM, disk)
- OS/template selection from library
- Installed software packages
- Artifact placement schedule
- Snapshot points

**Network Configuration**:
- Subnet CIDR
- Gateway IP
- DNS servers
- Routing rules between segments
- Firewall rules

**Actions**:
- Save as template
- Estimate total resources
- Validate configuration
- Deploy range
- Export as diagram/documentation

#### 2. VM Template Library
**View Options**: Grid or list view

**Each Template Card Shows**:
- OS icon and name
- Base image size
- Pre-installed software list
- Tags (e.g., "Domain Controller", "Clean Baseline", "Compromised")
- Last updated date
- Usage count

**Actions**:
- Create new template from scratch
- Import template (JSON/YAML)
- Clone existing template
- Edit template configuration
- Delete template

**Template Editor**:
- Base image selection (pulls from Docker Hub or cached)
- Hostname pattern
- Default specs (CPU/RAM/disk)
- Software installation script (bash/PowerShell)
- Artifact pre-placement
- Snapshot configuration

#### 3. Artifact Repository
**Organization**: Hierarchical tree or tag-based

**Artifact Entry Contains**:
- File name and path
- File type (executable, script, document, registry key)
- SHA256 hash
- Malicious indicator (safe/suspicious/malicious)
- TTPs mapping (MITRE ATT&CK)
- Placement locations (which VMs, which paths)
- Chain of custody log

**Upload Interface**:
- Drag-drop file upload
- Bulk upload with manifest
- Automatic hashing
- Malware confirmation checkbox
- Metadata form (description, TTP tags, placement instructions)

**Safety Features**:
- Encrypted storage
- Access logging
- Download requires justification
- Automatic password-protected archive for malware samples

#### 4. Range Execution Console
**Layout**: Multi-panel dashboard

**Panels**:
- **Range Overview**: Status, uptime, resource usage
- **VM Grid**: All VMs with status indicators (running/stopped/error)
  - Click VM for console access
  - Right-click menu: Start, Stop, Restart, Snapshot, View logs
- **MSEL Timeline**: Inject schedule with status (pending/executed/verified)
  - Manual trigger buttons
  - Execution logs per inject
- **Network Monitor**: Live traffic visualization between segments
- **Student Tracking**: Connection logs, evidence submissions, progress indicators
- **Event Log**: Timestamped activity feed

**VM Console Access**:
- Browser-based terminal (xterm.js)
- Full keyboard/mouse support
- Copy/paste functionality
- Multiple concurrent console sessions
- Console recording for AAR

#### 5. Evidence Management
**Student Submission Interface**:
- Upload evidence package (zip/tar)
- Manifest.csv upload
- Chain of custody form
- SHA256 verification on upload
- Timestamp capture (UTC)

**Evaluator Review Interface**:
- Evidence package browser (tree view)
- Side-by-side: submitted vs. expected artifacts
- Automated validation results:
  - Hash matches
  - Manifest completeness
  - Chain of custody integrity
  - Timeline consistency
- Annotation/comments per artifact
- Scoring rubric integration

**Export Options**:
- Individual evidence packages
- Aggregated class results
- Formatted for AAR

#### 6. Metrics & Reporting
**Pre-built Dashboards**:
- Range utilization (CPU, RAM, disk, network)
- Student performance summary
- MSEL execution timeline
- Evidence collection status
- Automated scoring results

**Custom Reports**:
- Date range selection
- Metric selection (checkboxes)
- Export formats (PDF, CSV, JSON)
- Scheduled report generation

**Visualizations**:
- Time-series graphs (resource usage over time)
- Bar charts (student scores, inject success rate)
- Network topology diagram (auto-generated from range config)
- Heatmaps (artifact discovery rate)

## Data Models

### Range Configuration
```python
class Range:
    id: UUID
    name: str
    description: str
    phase: str  # "P1", "P2", etc.
    status: str  # "planning", "building", "ready", "executing", "archived"
    created_by: User
    created_at: datetime
    networks: List[Network]
    vms: List[VM]
    artifacts: List[ArtifactPlacement]
    msel: MSEL
    students: List[User]
    white_cell: List[User]
    evaluators: List[User]
    resource_limits: ResourceLimits
    
class Network:
    id: UUID
    range_id: UUID
    name: str  # "Blue Team Internal", "Red Team C2"
    subnet: str  # "172.16.1.0/24"
    gateway: str
    dns_servers: List[str]
    isolation_level: str  # "complete", "controlled", "open"
    firewall_rules: List[FirewallRule]
    
class VM:
    id: UUID
    range_id: UUID
    network_id: UUID
    hostname: str
    ip_address: str
    template_id: UUID
    specs: VMSpecs  # cpu, ram, disk
    status: str  # "stopped", "starting", "running", "error"
    docker_container_id: str
    snapshots: List[Snapshot]
    artifacts: List[ArtifactPlacement]
    console_sessions: List[ConsoleSession]
```

### VM Template
```python
class VMTemplate:
    id: UUID
    name: str
    description: str
    os_type: str  # "windows", "linux"
    os_version: str  # "Windows Server 2022", "Ubuntu 22.04"
    base_image: str  # Docker image or dockur config
    default_specs: VMSpecs
    software_packages: List[str]
    configuration_script: str  # bash or PowerShell
    tags: List[str]
    is_public: bool
    created_by: User
    version: int
```

### Artifact
```python
class Artifact:
    id: UUID
    name: str
    file_path: str  # in MinIO
    file_hash: str  # SHA256
    file_size: int
    artifact_type: str  # "executable", "script", "document", "registry"
    malicious_indicator: str  # "safe", "suspicious", "malicious"
    ttps: List[str]  # MITRE ATT&CK IDs
    description: str
    upload_date: datetime
    uploaded_by: User
    access_log: List[AccessLog]
    
class ArtifactPlacement:
    id: UUID
    artifact_id: UUID
    vm_id: UUID
    target_path: str  # Path on VM where artifact should be placed
    placement_time: datetime  # When to place (for MSEL)
    placement_status: str  # "pending", "placed", "verified", "failed"
    verification_method: str  # How to verify placement
```

### MSEL
```python
class MSEL:
    id: UUID
    range_id: UUID
    injects: List[Inject]
    
class Inject:
    id: UUID
    msel_id: UUID
    sequence_number: int
    inject_time: datetime  # Relative to exercise start or absolute
    inject_type: str  # "artifact_placement", "script_execution", "manual"
    title: str
    description: str
    target_vms: List[UUID]
    actions: List[InjectAction]
    verification_criteria: str
    status: str  # "pending", "executing", "completed", "failed"
    execution_log: List[LogEntry]
    
class InjectAction:
    action_type: str  # "place_file", "run_command", "modify_registry"
    parameters: dict
    timeout: int
```

### Evidence Package
```python
class EvidencePackage:
    id: UUID
    range_id: UUID
    student_id: UUID
    submission_time: datetime
    manifest: Manifest
    artifacts: List[EvidenceArtifact]
    chain_of_custody: ChainOfCustody
    validation_results: ValidationResults
    evaluator_comments: str
    score: float
    
class Manifest:
    entries: List[ManifestEntry]
    
class ManifestEntry:
    file_name: str
    source_host: str
    collection_time: datetime  # UTC
    sha256_hash: str
    collection_tool: str
    collection_command: str
    
class EvidenceArtifact:
    file_path: str  # in MinIO
    manifest_entry: ManifestEntry
    hash_verified: bool
    expected_artifact_id: UUID  # Link to placed artifact if applicable
```

## MVP Feature Prioritization (Phased Roadmap)

### Phase 1: Core Infrastructure (Weeks 1-3)
**Goal**: Basic range creation and VM management

**Features**:
1. **Authentication System**
   - User registration/login (username/password)
   - JWT-based auth
   - Basic RBAC (admin, range_engineer, white_cell roles)

2. **VM Template Library**
   - CRUD operations for templates
   - Support 2-3 base templates (Ubuntu 22.04, Rocky Linux 9, Windows Server 2022)
   - Template metadata storage
   - Image caching system

3. **Range Builder - Basic**
   - Form-based range creation (no drag-drop yet)
   - Add VMs from template library
   - Configure single network segment
   - Set VM specs (CPU, RAM, disk)
   - Save range configuration

4. **VM Lifecycle Management**
   - Start/stop VMs
   - View VM status
   - Delete VMs
   - Basic Docker integration

5. **Dashboard**
   - View all ranges (list/grid)
   - Filter by status, phase
   - Basic resource metrics (CPU, RAM usage)

**Deliverable**: Can create a simple range with 5-10 VMs on one network, start/stop them, see status

---

### Phase 2: Network & Deployment (Weeks 4-6)
**Goal**: Multi-segment networking and reliable deployment

**Features**:
1. **Multi-Segment Networking**
   - Create multiple Docker networks per range
   - Assign VMs to specific networks
   - Configure subnets and gateways
   - Basic routing between segments

2. **Visual Network Builder**
   - Drag-drop canvas for VM placement
   - Network segment visualization
   - Auto-generated network diagram
   - Export topology as PNG/SVG

3. **Range Deployment Engine**
   - One-click range deployment
   - Parallel VM provisioning (async with Celery)
   - Deployment progress tracking
   - Rollback on failure
   - Health checks post-deployment

4. **VM Console Access**
   - Web-based terminal (xterm.js)
   - Console authentication
   - Multiple concurrent sessions
   - Copy/paste support

5. **Resource Management**
   - Set resource limits per range
   - Prevent over-allocation
   - Resource usage monitoring
   - Alerts for resource exhaustion

**Deliverable**: Deploy a complete BIB-H Phase 1 range with proper network segmentation, access VMs via console

---

### Phase 3: Templates & Artifacts (Weeks 7-9)
**Goal**: Reusable templates and artifact management

**Features**:
1. **Range Templates**
   - Save range config as template
   - Template versioning
   - Clone from template
   - Import/export templates (JSON/YAML)
   - Public template library

2. **VM Configuration Scripts**
   - Upload PowerShell/Bash scripts to templates
   - Execute scripts during VM provisioning
   - Script execution logging
   - Script variables/parameters

3. **Artifact Repository**
   - Upload artifacts (files, scripts)
   - SHA256 automatic hashing
   - Metadata tagging (malicious indicator, TTPs)
   - Search/filter artifacts
   - Access logging

4. **Artifact Placement**
   - Assign artifacts to VMs during range build
   - Specify target paths
   - Schedule placement (immediate or delayed)
   - Verification of successful placement

5. **Snapshot Management**
   - Create VM snapshots
   - Restore from snapshots
   - Snapshot scheduling (pre-artifact, post-artifact)
   - Snapshot storage management

**Deliverable**: Create reusable "BIB-H P1 Domain Controller" template, place pre-configured artifacts on VMs

---

### Phase 4: Execution & Monitoring (Weeks 10-12)
**Goal**: Live range execution support for white cell

**Features**:
1. **Range Execution Console**
   - Multi-panel dashboard
   - VM grid with status
   - Quick actions (start, stop, restart VM)
   - Event log (timestamped activity)

2. **Network Traffic Monitoring**
   - Packet capture on Docker networks
   - Traffic visualization (flow diagram)
   - Filter by source/dest/protocol
   - Export PCAPs

3. **Student Tracking**
   - Log student connections to VMs
   - Track commands executed (if monitoring enabled)
   - Connection timeline
   - Access pattern visualization

4. **MSEL Parser (Basic)**
   - Import MSEL from Markdown
   - Parse inject timeline
   - Display injects in chronological order
   - Manual inject status updates

5. **Manual Inject Execution**
   - Trigger inject from console
   - Execute artifact placement
   - Run scripts on target VMs
   - Log inject execution

**Deliverable**: White cell can execute a range, monitor student activity, manually trigger injects

---

### Phase 5: Evidence & Scoring (Weeks 13-15)
**Goal**: Evidence collection and automated validation

**Features**:
1. **Evidence Submission Portal**
   - Upload evidence packages (zip/tar)
   - Manifest.csv upload
   - Chain of custody form
   - Automatic hash verification
   - Submission confirmation

2. **Evidence Validation Engine**
   - Compare submitted vs. expected artifacts
   - Hash verification
   - Manifest completeness check
   - Chain of custody integrity
   - Automated validation report

3. **Evaluator Interface**
   - Browse submitted evidence
   - View validation results
   - Add comments/annotations
   - Manual scoring interface
   - Export evidence packages

4. **Basic Automated Scoring**
   - Artifact detection (did they find it?)
   - Hash correctness
   - Manifest completeness
   - Submission timeliness
   - Score calculation from rubric

5. **Metrics Export**
   - Generate class summary report
   - Export individual student scores
   - Timeline accuracy metrics
   - Evidence quality metrics

**Deliverable**: Students submit evidence, system validates, evaluators can score and export results

---

### Phase 6: Automation & Intelligence (Weeks 16-18)
**Goal**: Automated inject execution and advanced features

**Features**:
1. **MSEL Execution Engine**
   - Time-based inject scheduling
   - Automatic inject triggering
   - Inject dependency chains (B waits for A)
   - Inject verification (success/fail)
   - Re-execution on failure

2. **Attack Scenario Automation**
   - Script-based attack sequences
   - Simulated C2 beacons
   - Lateral movement automation
   - Persistence mechanism deployment
   - Attack timeline logging

3. **Advanced Scoring**
   - Timeline reconstruction from evidence
   - Kill chain completion detection
   - Technique detection (MITRE ATT&CK mapping)
   - Comparison against ground truth
   - Confidence scoring

4. **CAC/PKI Authentication**
   - Certificate-based auth
   - CAC reader support (browser-based)
   - Certificate validation
   - Multi-factor option

5. **Offline Operation Mode**
   - Pre-download all VM images
   - Cache all dependencies
   - Air-gap deployment checklist
   - Local image registry

**Deliverable**: Fully automated range execution, advanced scoring, CAC auth, offline-capable

---

### Phase 7: Advanced Features (Weeks 19-21)
**Goal**: Purple team integration and collaboration features

**Features**:
1. **Purple Team Tool Integration**
   - Caldera connector (optional)
   - Atomic Red Team execution
   - MITRE ATT&CK navigator integration
   - Attack technique library

2. **Collaborative Features**
   - Range sharing between engineers
   - Template marketplace
   - Comments/notes on ranges
   - Team workspaces
   - Activity feed

3. **Advanced Monitoring**
   - EDR simulation integration
   - SIEM log forwarding
   - Anomaly detection
   - Threat hunting scenarios

4. **Reporting & Analytics**
   - Custom report builder
   - Scheduled reports
   - Trend analysis across cohorts
   - Performance benchmarking
   - AAR auto-generation

5. **Ticketing System**
   - Student question submission
   - White cell response tracking
   - Ticket prioritization
   - Integration with range console

**Deliverable**: Enterprise-grade cyber range platform with advanced automation and collaboration

---

## File Structure

```
cyber-range-orchestrator/
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   ├── user-guide.md
│   └── deployment-guide.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── ranges.py
│   │   ├── vms.py
│   │   ├── templates.py
│   │   ├── artifacts.py
│   │   ├── msel.py
│   │   ├── evidence.py
│   │   └── metrics.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── range.py
│   │   ├── vm.py
│   │   ├── template.py
│   │   ├── artifact.py
│   │   ├── msel.py
│   │   └── evidence.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── docker_orchestrator.py
│   │   ├── artifact_manager.py
│   │   ├── msel_executor.py
│   │   ├── evidence_validator.py
│   │   └── scoring_engine.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── vm_provisioning.py
│   │   ├── artifact_placement.py
│   │   ├── inject_execution.py
│   │   └── snapshot_management.py
│   └── utils/
│       ├── __init__.py
│       ├── hashing.py
│       ├── validation.py
│       └── logging.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── public/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.tsx
│   │   ├── components/
│   │   │   ├── Dashboard/
│   │   │   ├── RangeBuilder/
│   │   │   ├── VMConsole/
│   │   │   ├── TemplateLibrary/
│   │   │   ├── ArtifactRepo/
│   │   │   ├── MSELEditor/
│   │   │   ├── ExecutionConsole/
│   │   │   ├── EvidenceReview/
│   │   │   └── common/
│   │   ├── hooks/
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   ├── websocket.ts
│   │   │   └── auth.ts
│   │   ├── types/
│   │   ├── utils/
│   │   └── styles/
│   └── tailwind.config.js
│
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
│
├── database/
│   └── init.sql
│
└── scripts/
    ├── setup.sh
    ├── backup.sh
    ├── restore.sh
    └── offline-cache.sh
```

## Development Guidelines

### Code Quality
- **Type Safety**: Use TypeScript for frontend, Pydantic models for backend
- **Error Handling**: Comprehensive try/catch with meaningful error messages
- **Logging**: Structured JSON logging with correlation IDs
- **Testing**: Unit tests for services, integration tests for API endpoints
- **Documentation**: Inline comments for complex logic, docstrings for all functions

### Security Considerations
- **Input Validation**: All user input validated via Pydantic
- **SQL Injection**: Use parameterized queries (SQLAlchemy ORM)
- **XSS Prevention**: React escapes by default, but validate HTML inputs
- **CSRF Protection**: CSRF tokens for state-changing operations
- **Secrets Management**: Environment variables, never hardcoded
- **Artifact Isolation**: Malware samples encrypted at rest, isolated execution
- **Network Isolation**: Docker networks fully isolated by default
- **Access Control**: RBAC enforced at API layer and DB level

### Performance Optimization
- **Async Operations**: VM provisioning, snapshot creation via Celery
- **Caching**: Redis for frequently accessed data (templates, range configs)
- **Pagination**: All list endpoints support limit/offset
- **Database Indexing**: Index on foreign keys, search fields
- **WebSocket Efficiency**: Throttle updates to avoid overwhelming clients
- **Image Caching**: Pre-pull Docker images, use local registry

### UX Principles
- **Responsiveness**: All actions provide immediate feedback (loading spinners, progress bars)
- **Error Messages**: User-friendly, actionable error messages
- **Confirmation Dialogs**: Destructive actions require confirmation
- **Keyboard Shortcuts**: Common actions (save, cancel, deploy) accessible via keyboard
- **Tooltips**: Hover tooltips for complex UI elements
- **Progressive Disclosure**: Advanced options hidden behind "Advanced" toggles
- **Dark Mode**: Support dark/light theme toggle

## Initial Setup Instructions

### For Claude Code Development
1. Initialize project structure with proper directory hierarchy
2. Set up Docker Compose with services: PostgreSQL, Redis, MinIO, API, Frontend, Nginx
3. Implement authentication system first (foundation for all other features)
4. Build VM template library and basic CRUD operations
5. Integrate Docker SDK and test VM creation/deletion
6. Implement basic range builder (form-based)
7. Build dashboard UI with range list and status indicators
8. Test end-to-end: Create range → Add VMs → Deploy → View status → Destroy

### Environment Variables (.env)
```bash
# Database
POSTGRES_USER=rangeadmin
POSTGRES_PASSWORD=<generate_secure>
POSTGRES_DB=cyberrange
DATABASE_URL=postgresql://rangeadmin:<password>@db:5432/cyberrange

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ROOT_USER=rangeadmin
MINIO_ROOT_PASSWORD=<generate_secure>
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=cyberrange-artifacts

# JWT
JWT_SECRET_KEY=<generate_secure_key>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Docker
DOCKER_HOST=unix:///var/run/docker.sock

# App
API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

### Deployment Steps
```bash
# Initial setup
./scripts/setup.sh

# Start all services
docker-compose up -d

# Verify health
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:3000

# Access web UI
# Navigate to http://localhost:3000
```

## Success Criteria for MVP (Phase 1)
- [ ] User can register and log in
- [ ] User can create VM templates (at least Ubuntu, Rocky, Windows)
- [ ] User can create a range with 10 VMs across 2 networks
- [ ] User can deploy the range and all VMs start successfully
- [ ] User can access VM consoles via web browser
- [ ] User can stop, start, and delete individual VMs
- [ ] Dashboard shows real-time resource usage
- [ ] System handles range isolation (2 concurrent ranges don't interfere)
- [ ] All operations complete in reasonable time (<5 min for 10 VM deployment)
- [ ] System recovers gracefully from VM provisioning failures

## Long-term Vision
This orchestrator should eventually support:
- Multi-phase evaluation campaigns (BIB-H P1-P4) running concurrently
- 100+ concurrent VMs across 10+ ranges
- Full MSEL-driven automation (zero white cell intervention)
- AI-powered scoring and AAR generation
- Integration with external training platforms (PCTE, LMS)
- Mobile app for white cell monitoring
- API for third-party tool integration
- Marketplace for community-contributed templates and scenarios

---

## Questions for Initial Development

Before starting Phase 1, Claude Code should confirm:
1. Preferred default VM specs (CPU cores, RAM, disk) for each OS type?
2. Default network CIDR ranges for auto-generated subnets?
3. Maximum concurrent VMs per range (hard limit)?
4. Retention period for archived ranges and evidence?
5. VM naming convention (e.g., `{range_name}-{hostname}-{uuid}` or simpler)?
6. Should we use Docker Swarm or stay with standalone Docker for Phase 1?

Once these are answered, proceed with file structure creation and Phase 1 implementation.
