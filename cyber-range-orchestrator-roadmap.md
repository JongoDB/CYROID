# Cyber Range Orchestrator - Development Roadmap

## Timeline Overview (21 weeks)

```
Phase 1: Core Infrastructure (Weeks 1-3)
├─ Week 1: Project setup, auth, database
├─ Week 2: VM templates, Docker integration
└─ Week 3: Basic range builder, dashboard

Phase 2: Network & Deployment (Weeks 4-6)
├─ Week 4: Multi-segment networking
├─ Week 5: Visual network builder
└─ Week 6: Deployment engine, VM console

Phase 3: Templates & Artifacts (Weeks 7-9)
├─ Week 7: Range templates, versioning
├─ Week 8: Artifact repository
└─ Week 9: Artifact placement, snapshots

Phase 4: Execution & Monitoring (Weeks 10-12)
├─ Week 10: Execution console
├─ Week 11: Network monitoring, student tracking
└─ Week 12: MSEL parser, manual injects

Phase 5: Evidence & Scoring (Weeks 13-15)
├─ Week 13: Evidence submission portal
├─ Week 14: Validation engine, evaluator UI
└─ Week 15: Automated scoring, metrics export

Phase 6: Automation & Intelligence (Weeks 16-18)
├─ Week 16: MSEL automation
├─ Week 17: Attack scenarios, advanced scoring
└─ Week 18: CAC/PKI auth, offline mode

Phase 7: Advanced Features (Weeks 19-21)
├─ Week 19: Purple team integration
├─ Week 20: Collaborative features
└─ Week 21: Advanced reporting, ticketing
```

## Milestone Gates

### 🎯 Milestone 1: Foundation Complete (End Week 3)
**Demo**: Log in → Create template → Build 5-VM range → Deploy → View status

**Exit Criteria**:
- ✅ User authentication working
- ✅ At least 3 VM templates in library (Ubuntu, Rocky, Windows)
- ✅ Can create range with 5 VMs
- ✅ Can deploy and start all VMs
- ✅ Dashboard shows range status
- ✅ Can stop/destroy range

**Risk if not met**: Foundation unstable, delay all downstream work

---

### 🎯 Milestone 2: Networked Ranges (End Week 6)
**Demo**: Build BIB-H P1 topology → Deploy → Access VMs via console → Verify network segmentation

**Exit Criteria**:
- ✅ Visual network builder functional
- ✅ Multi-segment networks (3+ networks per range)
- ✅ 10+ VM range deploys successfully
- ✅ Web-based VM console access works
- ✅ Network isolation verified (cannot reach other range VMs)
- ✅ Resource limits enforced

**Risk if not met**: Cannot deploy realistic training scenarios

---

### 🎯 Milestone 3: Repeatable Scenarios (End Week 9)
**Demo**: Clone "BIB-H P1 Template" → Customize → Deploy → Artifacts auto-placed → Snapshots created

**Exit Criteria**:
- ✅ Range template save/clone/import works
- ✅ VM provisioning scripts execute successfully
- ✅ Artifact repository with 10+ test artifacts
- ✅ Artifacts auto-place on designated VMs
- ✅ Snapshot creation and restore functional
- ✅ Can rebuild identical range from template

**Risk if not met**: Cannot scale to multiple cohorts efficiently

---

### 🎯 Milestone 4: White Cell Operations (End Week 12)
**Demo**: White cell logs in → Opens execution console → Triggers manual inject → Monitors student activity → Exports logs

**Exit Criteria**:
- ✅ Execution console with VM grid and status
- ✅ Network traffic visualization
- ✅ Student connection tracking
- ✅ MSEL import and display working
- ✅ Manual inject execution (place file, run script)
- ✅ Event logging with timestamps

**Risk if not met**: Cannot execute live exercises

---

### 🎯 Milestone 5: Evidence Workflow (End Week 15)
**Demo**: Student submits evidence → System validates → Evaluator reviews → Exports scored package

**Exit Criteria**:
- ✅ Evidence upload interface functional
- ✅ Hash verification automatic
- ✅ Manifest validation working
- ✅ Evaluator can browse and annotate evidence
- ✅ Basic scoring calculations correct
- ✅ Export to PDF/CSV for grading

**Risk if not met**: Manual grading bottleneck, no metrics

---

### 🎯 Milestone 6: Full Automation (End Week 18)
**Demo**: Schedule MSEL → Auto-execute injects → System scores results → CAC login → Offline deployment

**Exit Criteria**:
- ✅ Time-based inject scheduling works
- ✅ Automated inject execution (no manual trigger)
- ✅ Attack scenario scripts execute on schedule
- ✅ Advanced scoring (timeline reconstruction)
- ✅ CAC authentication functional
- ✅ Offline image cache tested

**Risk if not met**: Still requires significant white cell intervention

---

### 🎯 Milestone 7: Enterprise Ready (End Week 21)
**Demo**: Full BIB-H P1-P4 campaign → Collaborative template building → Purple team scenario → Auto-generated AAR

**Exit Criteria**:
- ✅ Purple team tool integration (Caldera or Atomic Red Team)
- ✅ Multi-user collaboration on ranges
- ✅ Custom reporting functional
- ✅ Ticketing system operational
- ✅ AAR auto-generation from metrics
- ✅ System handles 100+ VMs across 10 ranges

**Risk if not met**: Not production-ready for large-scale operations

---

## Critical Path Dependencies

```
Auth System
    ↓
VM Templates ────────┐
    ↓                │
Range Builder        │
    ↓                │
VM Lifecycle Mgmt    │
    ↓                ↓
Dashboard ←──── Networks
    ↓                ↓
Deployment Engine ←──┘
    ↓
VM Console
    ↓
Range Templates
    ↓
Artifacts ──────┐
    ↓           │
Snapshots       │
    ↓           ↓
Execution Console
    ↓           ↓
MSEL Parser ←───┘
    ↓
Evidence System
    ↓
Scoring
    ↓
Automation
```

## Weekly Sprint Goals

### Week 1: Project Bootstrap
- [ ] Initialize Git repository with .gitignore
- [ ] Set up Docker Compose (PostgreSQL, Redis, MinIO, API, Frontend)
- [ ] Configure Nginx reverse proxy
- [ ] Implement user model and auth endpoints (register, login, logout)
- [ ] Build basic JWT middleware
- [ ] Create database migrations (Alembic)
- [ ] Build login/register UI pages
- [ ] Test: User can register, log in, see empty dashboard

**Deliverable**: Running stack with working authentication

---

### Week 2: VM Foundation
- [ ] Create VM Template data model
- [ ] Build template CRUD API endpoints
- [ ] Integrate Docker SDK for Python
- [ ] Implement VM creation from template (Ubuntu, Rocky)
- [ ] Test Windows VM via dockur/windows
- [ ] Build template library UI (grid view)
- [ ] Template editor form
- [ ] Test: Create template → Spin up VM → Verify container running

**Deliverable**: Can create and manage VM templates

---

### Week 3: Range Builder v1
- [ ] Create Range and VM data models with relationships
- [ ] Build range creation API (POST /ranges)
- [ ] Form-based range builder UI
- [ ] Add VMs to range (select template, set specs, assign IP)
- [ ] Deploy range endpoint (start all VMs)
- [ ] Range status endpoint (GET /ranges/{id}/status)
- [ ] Dashboard UI with range cards
- [ ] Test: Create 5-VM range → Deploy → See all running

**Deliverable**: MVP functional - create and deploy simple ranges

---

### Week 4: Networking
- [ ] Create Network data model
- [ ] Docker network creation via SDK
- [ ] API endpoints for network CRUD
- [ ] Assign VMs to networks during range build
- [ ] Implement subnet validation (CIDR, no overlap)
- [ ] Network configuration form in range builder
- [ ] Test: Create range with 3 networks, 10 VMs → Verify isolation

**Deliverable**: Multi-segment networking functional

---

### Week 5: Visual Builder
- [ ] Install and configure React Flow
- [ ] Build drag-drop canvas component
- [ ] Create VM node components (different icons per OS)
- [ ] Create network segment components
- [ ] Implement drag VM onto canvas → auto-assign IP
- [ ] Connection lines between VMs and networks
- [ ] Export topology as PNG
- [ ] Test: Build BIB-H P1 topology visually

**Deliverable**: Visual network designer working

---

### Week 6: Deployment & Console
- [ ] Implement Celery for async tasks
- [ ] Build VM provisioning task with progress tracking
- [ ] Parallel VM deployment (Celery group)
- [ ] Deployment status WebSocket endpoint
- [ ] Frontend WebSocket integration (real-time progress)
- [ ] Integrate xterm.js for console
- [ ] VM console WebSocket proxy (Docker exec -it)
- [ ] Test: Deploy 10-VM range → Watch progress → Open console

**Deliverable**: Robust deployment with live console access

---

### Week 7: Templates v2
- [ ] Range template save/clone functionality
- [ ] Template versioning system
- [ ] Import/export range config (JSON schema)
- [ ] VM configuration scripts (bash/PowerShell)
- [ ] Script execution during provisioning
- [ ] Template marketplace UI
- [ ] Test: Save BIB-H P1 as template → Clone → Deploy

**Deliverable**: Reusable range templates

---

### Week 8: Artifact Repository
- [ ] Create Artifact data model
- [ ] MinIO integration for file storage
- [ ] Artifact upload API with SHA256 hashing
- [ ] Malicious indicator flagging
- [ ] MITRE ATT&CK TTP tagging
- [ ] Artifact browser UI (grid + list views)
- [ ] Search/filter by tags
- [ ] Test: Upload 10 artifacts → Tag → Search → Download

**Deliverable**: Secure artifact management

---

### Week 9: Artifact Placement & Snapshots
- [ ] ArtifactPlacement data model
- [ ] Placement scheduling (immediate vs. delayed)
- [ ] Celery task for artifact placement (copy to VM volume)
- [ ] Placement verification (file exists + hash match)
- [ ] Docker volume snapshot creation
- [ ] Snapshot restore functionality
- [ ] UI for assigning artifacts to VMs
- [ ] Test: Assign artifacts → Deploy → Verify placement → Create snapshot

**Deliverable**: Automated artifact deployment

---

### Week 10: Execution Console
- [ ] Execution console layout (multi-panel)
- [ ] VM grid with real-time status updates
- [ ] Quick actions menu (start, stop, restart, snapshot)
- [ ] Event log component (timestamped feed)
- [ ] Range overview metrics panel
- [ ] WebSocket for real-time event streaming
- [ ] Test: Open console → Start/stop VMs → See events

**Deliverable**: White cell command center

---

### Week 11: Monitoring
- [ ] Docker stats API integration
- [ ] Network traffic capture (tcpdump in network namespace)
- [ ] Traffic visualization component (flow diagram)
- [ ] Student connection logging (track WinRM/SSH)
- [ ] Connection timeline visualization
- [ ] Export PCAPs functionality
- [ ] Test: Student connects → See in monitoring → Export traffic

**Deliverable**: Real-time range observability

---

### Week 12: MSEL v1
- [ ] MSEL and Inject data models
- [ ] Markdown MSEL parser (parse headings, timestamps)
- [ ] MSEL import API endpoint
- [ ] MSEL timeline UI component
- [ ] Manual inject trigger button
- [ ] Inject execution: artifact placement
- [ ] Inject execution: script on VM
- [ ] Inject logging
- [ ] Test: Import MSEL → Trigger inject → Verify execution

**Deliverable**: Manual inject execution

---

### Week 13: Evidence Portal
- [ ] EvidencePackage data model
- [ ] Evidence upload API (zip/tar support)
- [ ] Manifest.csv parser
- [ ] Chain of custody form
- [ ] Automatic hash verification on upload
- [ ] Student submission UI
- [ ] Evidence storage in MinIO
- [ ] Test: Student uploads package → System accepts → Hashes verified

**Deliverable**: Evidence collection system

---

### Week 14: Validation & Review
- [ ] Evidence validation engine (manifest completeness)
- [ ] Hash mismatch detection
- [ ] Chain of custody integrity checks
- [ ] Validation report generation
- [ ] Evaluator evidence browser UI
- [ ] Side-by-side comparison (submitted vs. expected)
- [ ] Annotation system for evaluators
- [ ] Test: Upload evidence → See validation results → Add comments

**Deliverable**: Automated evidence validation

---

### Week 15: Scoring & Export
- [ ] Scoring rubric data model
- [ ] Automated scoring engine (artifact detection, hash correctness)
- [ ] Score calculation from rubric weights
- [ ] Evaluator scoring interface
- [ ] Export evidence package as zip
- [ ] Export class summary (CSV, PDF)
- [ ] Metrics dashboard for instructors
- [ ] Test: Score students → Export results → Generate report

**Deliverable**: End-to-end scoring workflow

---

### Week 16: MSEL Automation
- [ ] Time-based inject scheduler (cron-like)
- [ ] Inject dependency chains (wait for completion)
- [ ] Automatic inject triggering
- [ ] Inject verification (success/fail detection)
- [ ] Retry logic on failure
- [ ] MSEL execution timeline tracking
- [ ] Test: Schedule MSEL → Auto-execute → Verify all injects

**Deliverable**: Fully automated MSEL execution

---

### Week 17: Attack Scenarios
- [ ] Attack script library (bash, PowerShell)
- [ ] C2 beacon simulation (periodic HTTP requests)
- [ ] Lateral movement automation (psexec, WMI)
- [ ] Persistence deployment (scheduled tasks, services)
- [ ] Attack timeline logging (MITRE ATT&CK mapping)
- [ ] Advanced scoring: kill chain detection
- [ ] Timeline reconstruction from evidence
- [ ] Test: Execute attack scenario → Student detects → Score accuracy

**Deliverable**: Automated adversary emulation

---

### Week 18: CAC & Offline
- [ ] CAC/PKI authentication middleware
- [ ] Certificate validation against DoD CAs
- [ ] Browser-based CAC reader integration
- [ ] Offline image cache script (pull all images)
- [ ] Local Docker registry setup
- [ ] Air-gap deployment checklist
- [ ] Test: Log in with CAC → Deploy offline → All images cached

**Deliverable**: Enterprise auth and offline capability

---

### Week 19: Purple Team
- [ ] Caldera REST API integration (optional)
- [ ] Atomic Red Team executor
- [ ] MITRE ATT&CK navigator export
- [ ] Attack technique library
- [ ] Technique-to-inject mapping
- [ ] Test: Execute ATT&CK technique → Map to inject → Score detection

**Deliverable**: Purple team tooling

---

### Week 20: Collaboration
- [ ] Team workspaces (multi-user range editing)
- [ ] Range sharing permissions
- [ ] Template marketplace with ratings
- [ ] Comments/notes on range components
- [ ] Activity feed for team
- [ ] Real-time collaborative editing (WebSocket)
- [ ] Test: Multiple users edit range → See live updates

**Deliverable**: Multi-user collaboration

---

### Week 21: Advanced Reporting
- [ ] Custom report builder UI (drag-drop widgets)
- [ ] Scheduled report generation (cron)
- [ ] Trend analysis (compare cohorts over time)
- [ ] Performance benchmarking
- [ ] AAR auto-generation from MSEL + evidence
- [ ] Ticketing system for student questions
- [ ] Test: Generate AAR → Export PDF → Submit ticket

**Deliverable**: Production-ready platform

---

## Resource Estimates

### Development Team
- **Phase 1-2** (Weeks 1-6): 1 full-stack engineer + 1 DevOps
- **Phase 3-5** (Weeks 7-15): 2 full-stack engineers + 1 DevOps
- **Phase 6-7** (Weeks 16-21): 2 full-stack + 1 backend + 1 DevOps

### Infrastructure (Development)
- **Single host**: 32 CPU cores, 128 GB RAM, 2 TB NVMe SSD
- **Rationale**: Support 2 concurrent 10-VM ranges + orchestrator services

### Infrastructure (Production)
- **Minimum**: 64 CPU cores, 256 GB RAM, 4 TB SSD
- **Recommended**: 128 cores, 512 GB RAM, 8 TB NVMe (for 10 concurrent ranges)

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| dockur/windows instability | High | High | Test early (Week 2), consider alternatives if issues |
| VM provisioning too slow | Medium | Medium | Implement parallel deployment (Week 6) |
| Network isolation failures | Low | High | Extensive testing (Week 4), automated validation |
| Evidence validation complexity | Medium | Medium | Start simple (Week 13), iterate based on feedback |
| Scope creep (purple team features) | High | Medium | Stick to roadmap, defer non-essentials to Phase 7 |
| CAC auth browser compatibility | Medium | Low | Test multiple browsers (Week 18), provide fallback |
| Offline mode incomplete | Low | Medium | Maintain dependency list (Week 18), test air-gap |

---

## Success Metrics (KPIs)

### Technical Performance
- Range deployment time: <5 minutes for 10 VMs
- VM console latency: <500ms
- System uptime: >99.5%
- Concurrent ranges supported: 10+ without degradation

### User Experience
- Time to create range from template: <2 minutes
- Artifact placement success rate: >95%
- Evidence validation accuracy: >98%
- User satisfaction score: >4/5

### Business Impact
- Range preparation time reduction: 75% vs. manual setup
- Evaluator grading time reduction: 50% vs. manual
- Range reuse rate: 80% of ranges built from templates
- White cell workload reduction: 60% with automation

---

## Next Steps for Claude Code

1. **Review this roadmap** with Jon for approval
2. **Answer the 6 questions** in the main prompt document
3. **Create project repository** structure
4. **Begin Week 1 sprint**: Docker Compose + auth system
5. **Daily standup**: Report progress, blockers, questions

Once Week 1 is complete, we'll have a solid foundation to accelerate through the remaining phases.
