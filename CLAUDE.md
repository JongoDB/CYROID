# CYROID - Claude Code Project Context

> **Purpose**: This file provides persistent context for Claude Code to understand the CYROID project across sessions. It should be updated as the project progresses to maintain accurate documentation and README.

---

## Project Identity

- **Name**: CYROID (Cyber Range Orchestrator In Docker)
- **Type**: Web-based cyber range orchestration platform
- **Domain**: Military/government cyber training, educational institutions
- **Current Version**: 0.27.6
- **Repository**: /Users/JonWFH/jondev/CYROID

---

## Quick Context

CYROID automates Docker-based cyber training environments with:
- Multi-OS VM support (Linux containers, Linux VMs via QEMU, Windows VMs via dockur, macOS)
- DinD (Docker-in-Docker) isolation for range deployments (no IP conflicts between ranges)
- VM Library with snapshot-based VM creation
- Network isolation with custom Docker networks and iptables rules
- VNC console access through Traefik (with DinD proxy routing)
- MSEL (Master Scenario Events List) for scenario execution
- Pre-deployment validation for ranges
- Content Library with Student Lab walkthroughs
- Blueprint export/import with Dockerfiles for reproducible environments
- Global notifications system (toast + bell dropdown)
- Training Events for scheduling exercises
- Evidence collection and scoring (in development)

---

## Architecture Summary

```
Frontend (React/TypeScript) → Traefik → FastAPI Backend → Docker Engine
                                ↓
                    PostgreSQL + Redis + MinIO
```

**Key Services**:
- `api`: FastAPI backend (port 8000)
- `frontend`: React app (port 3000/80)
- `db`: PostgreSQL 16 (port 5432)
- `redis`: Redis 7 (port 6379)
- `minio`: Object storage (ports 9000/9001)
- `worker`: Dramatiq task processor
- `traefik`: Reverse proxy (ports 80/443/8080)

---

## CRITICAL: Local Development Commands

**ALWAYS use this command to rebuild/restart services locally:**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

**Why:** The base `docker-compose.yml` pulls pre-built images from GHCR with old versions baked in. The `docker-compose.dev.yml` overlay builds from local source code and reads the VERSION file correctly.

**NEVER use:** `docker compose up -d --build` alone - this will run stale code!

---

## CRITICAL: Git Workflow

**NEVER push directly to master.** Always create a feature branch and open a PR:

```bash
git checkout -b feat/your-feature-name
# ... make changes ...
git add <specific-files>
git commit -m "feat: description"
git push -u origin feat/your-feature-name
gh pr create --title "feat: description" --body "## Summary\n- Change 1\n- Change 2"
```

**Why:** PRs allow for code review and maintain a clean history. Direct pushes to master bypass review.

---

## Development Roadmap Status

### UPDATE THIS SECTION AS DEVELOPMENT PROGRESSES

Current overall progress: **Phase 4 of 7 Complete (57%)**

| Phase | Name | Status | Completion |
|-------|------|--------|------------|
| 1 | Core Infrastructure | ✅ Complete | 100% |
| 2 | Network & Deployment | ✅ Complete | 100% |
| 3 | Templates & Artifacts | ✅ Complete | 100% |
| 4 | Execution & Monitoring | ✅ Complete | 100% |
| 5 | Evidence & Scoring | 🟡 In Progress | 40% |
| 6 | Automation & Intelligence | 🟡 In Progress | 17% |
| 7 | Advanced Features | ⏳ Planned | 0% |

### Phase 5 Checklist (Current Focus)

- [ ] Evidence submission portal UI
- [ ] Manifest.csv parser
- [ ] Chain of custody form
- [ ] Automated hash verification
- [ ] Evaluator review interface
- [ ] Basic automated scoring engine
- [ ] Scoring rubric configuration
- [ ] Export to CSV/PDF

### Phase 6 Planned Items

- [ ] MSEL time-based scheduling
- [ ] Automated inject execution
- [ ] Attack scenario automation (scripts)
- [ ] Advanced scoring (timeline reconstruction)
- [ ] CAC/PKI authentication
- [x] Offline/air-gap deployment mode (via comprehensive export with Docker images)

### Phase 7 Planned Items

- [ ] Purple team integration (Caldera)
- [ ] Atomic Red Team executor
- [ ] Collaborative range editing
- [ ] Custom report builder
- [ ] AAR auto-generation
- [ ] Advanced analytics dashboard
- [ ] Windows ARM64 VM support (Win11 ARM)

---

## Feature Implementation Status

### UPDATE THIS TABLE WHEN FEATURES ARE COMPLETED

| Feature | Status | Notes |
|---------|--------|-------|
| JWT Authentication | ✅ | Fully working |
| User Registration | ✅ | With approval workflow |
| RBAC (4 roles) | ✅ | Admin, Range Engineer, White Cell, Evaluator |
| ABAC (resource tags) | 🟡 | Fine-grained visibility control (in progress) |
| VM Template CRUD | ✅ | 27+ OS templates |
| Range CRUD | ✅ | Full lifecycle |
| Network Management | ✅ | Custom subnets, multi-homed VMs |
| VM Lifecycle | ✅ | Create/start/stop/restart/delete |
| Dynamic Network Attach | ✅ | Add/remove NICs on running VMs |
| VNC Console | ✅ | Via Traefik proxy |
| Range Templating | ✅ | Import/export/clone |
| Comprehensive Range Export | ✅ | Full config, artifacts, MSEL, offline Docker images |
| Range Import with Validation | ✅ | Conflict detection, template resolution |
| Artifact Repository | ✅ | MinIO-backed with SHA256 |
| Snapshot Management | ✅ | Golden images for Windows |
| Event Logging | ✅ | Real-time WebSocket streaming |
| Execution Console | ✅ | Multi-panel dashboard |
| MSEL Parser | ✅ | Markdown/YAML support |
| Manual Inject Execution | ✅ | Trigger from console |
| Connection Tracking | ✅ | Monitor student activity |
| Version Display | ✅ | API endpoint + UI footer |
| Console Pop-out | ✅ | Default new window, Shift+click for inline |
| DinD Range Isolation | ✅ | Each range in separate Docker-in-Docker container |
| VM Library | ✅ | Snapshot-based VM creation, renamed from Templates |
| Pre-deployment Validation | ✅ | Image, architecture, disk space checks |
| Promote to Library | ✅ | Promote cached images to VM Library |
| Content Library | ✅ | Student Lab walkthroughs with markdown support |
| Blueprint Export/Import | ✅ | v3.0 format with Dockerfiles for reproducibility |
| Global Notifications | ✅ | Toast notifications + bell dropdown history |
| Training Events | ✅ | Event scheduling with range associations |
| Deployment Progress | ✅ | Real-time progress tracking during range deployment |
| Clipboard Sync | ✅ | Copy from walkthrough to VNC console |
| macOS VM Support | ✅ | macOS ISOs and container creation |
| Evidence Submission | 🟡 | In development |
| Evidence Validation | 🟡 | In development |
| Scoring Engine | 🟡 | In development |
| Network Visualization | 🟡 | Framework in place |
| MSEL Automation | ⏳ | Phase 6 |
| Attack Automation | ⏳ | Phase 6 |
| CAC/PKI Auth | ⏳ | Phase 6 |
| Purple Team Integration | ⏳ | Phase 7 |
| Multi-Architecture Support | ✅ | x86_64 + ARM64 native, emulation warnings |

---

## Code Conventions

### Backend (Python)

- **Framework**: FastAPI with async/await
- **ORM**: SQLAlchemy 2.0 with Alembic migrations
- **Validation**: Pydantic schemas
- **Task Queue**: Dramatiq with Redis broker
- **Style**: Black, isort, flake8
- **Location**: `backend/cyroid/`

### Frontend (TypeScript)

- **Framework**: React 18 with TypeScript
- **Build**: Vite
- **Styling**: Tailwind CSS
- **State**: Zustand
- **Routing**: React Router 6
- **Style**: ESLint, Prettier
- **Location**: `frontend/src/`

### Git Commits

Use semantic prefixes:
- `feat:` - New features
- `fix:` - Bug fixes
- `perf:` - Performance improvements
- `refactor:` - Code restructuring
- `docs:` - Documentation
- `test:` - Tests
- `chore:` - Maintenance

---

## Key Files Reference

### Backend
- `backend/cyroid/main.py` - FastAPI app initialization
- `backend/cyroid/config.py` - Environment configuration
- `backend/cyroid/api/ranges.py` - Range endpoints
- `backend/cyroid/api/vms.py` - VM endpoints
- `backend/cyroid/api/cache.py` - Image cache and promote-to-library
- `backend/cyroid/services/docker_service.py` - Docker orchestration
- `backend/cyroid/services/dind_service.py` - DinD container management
- `backend/cyroid/services/vnc_proxy_service.py` - VNC proxy for DinD console access
- `backend/cyroid/services/deployment_validator.py` - Pre-deployment validation
- `backend/cyroid/services/range_deployment_service.py` - Range lifecycle
- `backend/cyroid/models/` - SQLAlchemy models

### Frontend
- `frontend/src/App.tsx` - Route configuration
- `frontend/src/pages/RangeDetail.tsx` - Range builder (with snapshot selection)
- `frontend/src/pages/VMLibrary.tsx` - VM Library (snapshots + base images)
- `frontend/src/pages/ImageCache.tsx` - Docker image cache with promote feature
- `frontend/src/pages/ExecutionConsole.tsx` - Live console
- `frontend/src/services/api.ts` - API client

### Configuration
- `docker-compose.yml` - Service definitions
- `traefik-dynamic.yml` - Routing rules
- `.env` - Environment variables

---

## README Update Instructions

**IMPORTANT**: When completing features or phases, update the README.md to reflect progress:

### 1. Update Version Badge
In README.md header, update:
```markdown
<img src="https://img.shields.io/badge/Version-X.X.X--alpha-orange" alt="Version">
```

### 2. Update Phase Badge
```markdown
<img src="https://img.shields.io/badge/Phase-X%20of%207-blue" alt="Phase">
```

### 3. Update Feature Tables
Move features from "In Development" to "Implemented" when complete:
```markdown
| Feature | Status |
|---------|--------|
| Feature Name | ✅ Complete |
```

### 4. Update Roadmap Progress Bars
```markdown
Phase X: Name                       ████████████████████ 100% ✅
Phase Y: Name                       ████████░░░░░░░░░░░░  40% 🟡
Phase Z: Name                       ░░░░░░░░░░░░░░░░░░░░   0% ⏳
```

### 5. Update Project Statistics
At bottom of README, update:
- Backend LoC
- Frontend LoC
- Database Models count
- API Endpoints count
- Development Phase progress

---

## Version History

| Version | Date | Phase | Major Changes |
|---------|------|-------|---------------|
| 0.1.0 | 2026-01-11 | 1 | Initial auth, templates, basic ranges |
| 0.2.0 | 2026-01-12 | 2 | Multi-network, visual builder, deployment |
| 0.3.0 | 2026-01-13 | 3 | Range templates, artifacts, snapshots |
| 0.4.0 | 2026-01-15 | 4 | Execution console, MSEL, monitoring |
| 0.11.0 | 2026-01-19 | 4 | DinD isolation, VM Library, pre-deployment validation |
| 0.20.0 | 2026-01-21 | 4 | Image Cache consolidation, GHCR publishing |
| 0.21.x | 2026-01-22 | 4 | VNC fixes, DinD container config, ISO VM support |
| 0.22.0 | 2026-01-23 | 5 | Content Library integration for Student Lab walkthroughs |
| 0.23.0 | 2026-01-24 | 5 | Feature consolidation (notifications, clipboard, deployment progress) |
| 0.23.1 | 2026-01-24 | 5 | Blueprint export/import v3.0 with Dockerfiles |
| 0.23.3 | 2026-01-25 | 5 | Moved docker-images to data/images |
| 0.23.5 | 2026-01-25 | 5 | Notification dropdown positioning fix |
| 1.0.0 | TBD | 7 | Production release |

---

## Common Development Tasks

### Adding a New API Endpoint
1. Create route in `backend/cyroid/api/<module>.py`
2. Add Pydantic schemas in `backend/cyroid/schemas/`
3. Add model if needed in `backend/cyroid/models/`
4. Run migration: `alembic revision --autogenerate -m "Description"`
5. Apply: `alembic upgrade head`
6. Add frontend API call in `frontend/src/services/api.ts`

### Adding a New Page
1. Create component in `frontend/src/pages/<Page>.tsx`
2. Add route in `frontend/src/App.tsx`
3. Add navigation link in layout component

### Database Changes
1. Modify model in `backend/cyroid/models/`
2. Create migration: `docker-compose exec api alembic revision --autogenerate -m "Description"`
3. Apply: `docker-compose exec api alembic upgrade head`

---

## Testing Checklist

Before marking a feature complete:
- [ ] Unit tests pass
- [ ] Integration tests pass (if applicable)
- [ ] Manual testing in UI
- [ ] Error handling verified
- [ ] Loading states work
- [ ] Permissions checked (RBAC/ABAC)
- [ ] Documentation updated

---

## Reference Documents

- `cyber-range-orchestrator-prompt.md` - Original requirements
- `cyber-range-orchestrator-roadmap.md` - Detailed roadmap
- `cyber-range-orchestrator-quickstart.md` - Configuration reference
- `docs/plans/` - Implementation plans

---

## Notes for Future Sessions

### Current Priority
Phase 5: Evidence & Scoring system

### Known Issues
- (Add issues here as discovered)

### Technical Debt
- (Add items here as identified)

### User Feedback
- (Add feedback here as received)

---

*Last Updated: 2026-01-25*
*Update this file whenever significant progress is made or context changes*
