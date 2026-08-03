# CYROID - Claude Code Project Context

> **Purpose**: This file provides persistent context for Claude Code to understand the CYROID project across sessions. It should be updated as the project progresses to maintain accurate documentation and README.

---

## Project Identity

- **Name**: CYROID (Cyber Range Orchestrator In Docker)
- **Type**: Web-based cyber range orchestration platform
- **Domain**: Military/government cyber training, educational institutions
- **Current Version**: 0.38.4
- **License**: AGPL-3.0 (see `LICENSE`)
- **Repository**: /Users/JonWFH/jondev/CYROID

> **Version note**: `VERSION` at the repo root is the source of truth and is bumped
> automatically on PR merge by CI. Read it rather than trusting this file.

---

## Quick Context

CYROID automates Docker-based cyber training environments with:
- Multi-OS VM support (Linux containers, Linux VMs via QEMU, Windows VMs via dockur, macOS)
- Multi-architecture support (x86_64 + ARM64 native, per-VM `arch` selection, multi-platform digest resolution)
- DinD (Docker-in-Docker) isolation for range deployments (no IP conflicts between ranges)
- VM Library with snapshot-based VM creation
- Network isolation with custom Docker networks and iptables rules
- Multi-NIC VMs with a visual blueprint editor
- VNC console access through Traefik (with DinD proxy routing)
- MSEL (Master Scenario Events List) for scenario execution
- Pre-deployment validation for ranges
- Content Library with Student Lab walkthroughs (markdown + PDF export)
- Blueprint export/import with Dockerfiles, async progress tracking, and offline image tarballs
- Catalog for browsing and installing shared blueprints/content from remote sources
- Local Docker Registry with pull-through cache for fast, offline-capable image distribution
- Global notifications system (user-scoped, toast + bell dropdown)
- Training Events with per-student range deployment and console visibility controls
- ABAC + RBAC access control
- `deploy.sh` full-screen TUI for production install, backup/restore, and factory reset
- Evidence collection and scoring (in development)

---

## Architecture Summary

```
Frontend (React/TypeScript) → Traefik → FastAPI Backend → Docker Engine
                                ↓
                    PostgreSQL + Redis + MinIO
```

**Key Services** (see `docker-compose.yml`):
- `api`: FastAPI backend (port 8000)
- `frontend`: React app (port 3000/80)
- `db`: PostgreSQL 16 (port 5432)
- `redis`: Redis 7 (port 6379)
- `minio`: Object storage (ports 9000/9001)
- `worker`: Dramatiq task processor
- `registry`: Local Docker registry with pull-through cache
- `traefik`: Reverse proxy (ports 80/443/8080)

**Scale reference** (as of 0.38.4): 23 SQLAlchemy models, 26 API modules with ~285 routes,
21 services, 4 Dramatiq task modules.

---

## CRITICAL: Local Development Setup

**FIRST TIME or NEW WORKTREE:** Run the dev setup script:

```bash
./scripts/dev-setup.sh
```

This creates required files that are gitignored (SSL certs, macOS overrides, data directories).

---

## CRITICAL: Local Development Commands

**ALWAYS use this command to rebuild/restart services locally (both macOS and Linux):**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.override.yml up -d --build
```

**Why:** The base `docker-compose.yml` pulls pre-built images from GHCR with old versions baked in. The `docker-compose.dev.yml` overlay builds from local source code. The `docker-compose.override.yml` maps volume paths to local `./data/cyroid` for development convenience.

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
| 5 | Evidence & Scoring | 🟡 In Progress | see note |
| 6 | Automation & Intelligence | 🟡 In Progress | ~30% |
| 7 | Advanced Features | ⏳ Planned | 0% |

> **Phase 5 accuracy note (verified 2026-08-03)**: the *content/delivery* half of Phase 5
> shipped (Content Library, walkthroughs, PDF export, Training Events, per-student
> deployment, ABAC). The *evidence & scoring* half has *no implementation at all* —
> there is no evidence or scoring model, API module, or UI component in the tree.
> Treat every unchecked box below as genuinely not started, not partially done.

### Phase 5 Checklist (Current Focus)

Delivered:
- [x] Content Library + Student Lab walkthroughs (markdown, PDF export)
- [x] Training Events with per-student range deployment
- [x] ABAC resource tagging (`models/resource_tag.py`, enforced in `api/deps.py`)

Not started — no code exists for any of these:
- [ ] Evidence submission portal UI
- [ ] Manifest.csv parser
- [ ] Chain of custody form
- [ ] Automated hash verification
- [ ] Evaluator review interface
- [ ] Basic automated scoring engine
- [ ] Scoring rubric configuration
- [ ] Export to CSV/PDF

### Phase 6 Planned Items

- [ ] MSEL time-based scheduling *(not started — no scheduler code)*
- [ ] Automated inject execution *(manual trigger only)*
- [ ] Attack scenario automation (scripts)
- [ ] Advanced scoring (timeline reconstruction)
- [ ] CAC/PKI authentication *(not started — no x509/PKCS#11 code)*
- [x] Offline/air-gap deployment mode (comprehensive export + local registry pull-through cache)
- [x] Local Docker Registry distribution with push-on-demand
- [x] `deploy.sh` self-update and TUI-driven install/backup/restore

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
| ABAC (resource tags) | ✅ | `models/resource_tag.py`, enforced in `api/deps.py` + `api/ranges.py` |
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
| Multi-NIC VMs | ✅ | Range builder + visual blueprint editor |
| Catalog | ✅ | Browse/install blueprints + content from remote sources |
| Local Docker Registry | ✅ | Pull-through cache, push-on-demand, admin tab |
| Async Blueprint Import/Export | ✅ | Real-time progress, parallel image export |
| VM Provisioning Progress | ✅ | Live status, provision/start split, auto-start on running ranges |
| Cross-Arch VM Pulls | ✅ | Per-VM `arch`, multi-platform digest resolution |
| Per-Student Range Deployment | ✅ | Training Events, console visibility controls |
| Content PDF Export | ✅ | Content Library → PDF |
| deploy.sh TUI | ✅ | Full-screen dashboard, backup/restore, factory reset, self-update |
| Network Visualization | 🟡 | Framework in place |
| Evidence Submission | ⏳ | Phase 5 — not started, no code in tree |
| Evidence Validation | ⏳ | Phase 5 — not started, no code in tree |
| Scoring Engine | ⏳ | Phase 5 — not started, no code in tree |
| MSEL Automation | ⏳ | Phase 6 |
| Attack Automation | ⏳ | Phase 6 |
| CAC/PKI Auth | ⏳ | Phase 6 |
| Purple Team Integration | ⏳ | Phase 7 |
| Multi-Architecture Support | ✅ | x86_64 + ARM64 native CI builds, emulation warnings |

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
- `backend/cyroid/api/blueprints.py` - Blueprint export/import
- `backend/cyroid/api/catalog.py` - Catalog sources, browse, install
- `backend/cyroid/api/registry.py` - Local registry management
- `backend/cyroid/api/deps.py` - Auth dependencies + ABAC enforcement
- `backend/cyroid/services/docker_service.py` - Docker orchestration
- `backend/cyroid/services/dind_service.py` - DinD container management
- `backend/cyroid/services/deployment_validator.py` - Pre-deployment validation
- `backend/cyroid/services/range_deployment_service.py` - Range lifecycle
- `backend/cyroid/services/blueprint_service.py` - Blueprint import/build
- `backend/cyroid/services/blueprint_export_service.py` - Blueprint export + image tarballs
- `backend/cyroid/services/catalog_service.py` - Catalog sync/browse/install
- `backend/cyroid/services/registry_service.py` - Registry push/pull, pull-through cache
- `backend/cyroid/services/traefik_route_service.py` - Generates `traefik/dynamic/range-*.yml`
- `backend/cyroid/tasks/` - Dramatiq tasks (`blueprint_import`, `blueprint_export`, `deployment`, `vm_tasks`)
- `backend/cyroid/models/` - SQLAlchemy models (23)

### Frontend
- `frontend/src/App.tsx` - Route configuration
- `frontend/src/pages/RangeDetail.tsx` - Range builder (snapshot selection, multi-NIC)
- `frontend/src/pages/VMLibrary.tsx` - VM Library (snapshots + base images)
- `frontend/src/pages/ImageCache.tsx` - Docker image cache with promote feature
- `frontend/src/pages/ExecutionConsole.tsx` - Live console
- `frontend/src/pages/CatalogBrowser.tsx` - Catalog browse/install UI
- `frontend/src/components/blueprints/VisualBlueprintEditor.tsx` - Visual blueprint editor (multi-NIC, arch selector)
- `frontend/src/components/blueprints/ImportBlueprintModal.tsx` - Async import with progress
- `frontend/src/services/api.ts` - API client

### Configuration
- `VERSION` - Source of truth for version (auto-bumped by CI on PR merge)
- `LICENSE` - AGPL-3.0
- `docker-compose.yml` - Service definitions
- `docker-compose.dev.yml` - Local source build overlay (see dev commands above)
- `traefik-dynamic.yml` - Routing rules
- `traefik/dynamic/range-*.yml` - Per-range VNC routes, generated at runtime (gitignored)
- `scripts/dev-setup.sh` - Creates gitignored local dev files (certs, overrides, data dirs)
- `scripts/deploy.sh` - Standalone production installer + TUI dashboard
- `.env` - Environment variables (gitignored; contains JWT + MinIO secrets)

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
| 0.24-0.29 | 2026-01-25 | 5 | ABAC, user-scoped notifications, Training Events (per-student deployment, console visibility), Content PDF export, production deployment system |
| 0.30.0 | 2026-01-28 | 5 | **Catalog**: sources, browse, install; CatalogService + models + UI |
| 0.31.0 | 2026-01-28 | 5 | Blueprint export consolidated with Docker image tarballs (#131) |
| 0.32-0.33 | 2026-01-29 | 5 | **Multi-NIC** blueprints + visual editor; **local Docker Registry** with pull-through cache, push-on-demand, admin tab |
| 0.34-0.35 | 2026-01-30 | 6 | `deploy.sh` full-screen TUI (dashboard, backup/restore, factory reset, seed students, self-update); native ARM64 CI builds; auto version bump on merge |
| 0.36.x | 2026-02-13 | 6 | Concurrent user scalability fixes (login failures at scale) |
| 0.37.x | 2026-02-21 | 6 | **Cross-architecture** VM support: per-VM `arch` through blueprint pipeline, multi-platform digest resolution, arch selector |
| 0.38.0 | 2026-02-22 | 6 | Async blueprint import with progress; VM provisioning progress; provision/start split; auto-start VMs on running ranges |
| 0.38.4 | 2026-02-22 | 6 | AGPL-3.0 license; DinD inter-network routing; VM size revalidation fix |
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
Phase 5: Evidence & Scoring — this is the **largest remaining gap**. Nothing has been
built yet (no models, API, or UI), so it starts from a blank slate rather than
continuing partial work.

### Known Issues
- (Add issues here as discovered)

### Technical Debt
- **Never commit VM disk images or ISOs.** An installer ISO was `git add`-ed at some
  point; it was later removed from history but left a **4.5 GB unreachable blob** in
  `.git`, pinned by the reflog and therefore immune to routine `git gc`. Repo size was
  4.4 GB when the real packed history is ~2.5 MB. Cleaned 2026-08-03 with:
  `git reflog expire --expire=now --expire-unreachable=now --all && git gc --prune=now`.
  `.gitignore` now blocks `*.iso`, `*.img`, `*.qcow2`, `*.vmdk`, `*.vhd*`, `*.raw`, and
  `*.tar*`. If `.git` ever looks oversized again, diagnose with:
  `git count-objects -vH` then `git fsck --unreachable | awk '$2=="blob"{print $3}' | git cat-file --batch-check='%(objectsize) %(objectname)' | sort -rn | head`
- This file drifted ~11 minor versions behind reality (claimed 0.27.6 at actual 0.38.4)
  and referenced a deleted `services/vnc_proxy_service.py`. Prefer reading `VERSION` and
  the tree over trusting prose here.

### User Feedback
- (Add feedback here as received)

---

*Last Updated: 2026-08-03 (verified against tree at v0.38.4)*
*Update this file whenever significant progress is made or context changes*
