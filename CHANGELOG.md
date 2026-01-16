# Changelog

All notable changes to CYROID will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-01-16

### Added

- **Version Display in UI** ([#7](../../issues/7)): Application version is now displayed in the sidebar footer, showing version number and git commit hash when available. Added `/api/v1/version` endpoint returning version, commit, build date, and API version.

- **Console Pop-out as Default** ([#9](../../issues/9)): Clicking the console button on a running VM now opens the console in a dedicated browser window by default, providing a better multi-tasking experience. Use Shift+click to open inline (legacy behavior). Added standalone `/console/:vmId` route for pop-out windows with automatic console type detection (terminal vs VNC).

### Changed

- Console button icon changed from Terminal to ExternalLink to indicate pop-out behavior
- FastAPI app version now dynamically reads from config instead of hardcoded value

## [0.4.0] - 2026-01-15

### Added

- Execution Console with multi-panel dashboard
- MSEL (Master Scenario Events List) parser with Markdown/YAML support
- Manual inject execution from console
- Connection tracking for monitoring student activity
- Real-time event logging via WebSocket streaming
- Network interface management (add/remove NICs on running VMs)

## [0.3.0] - 2026-01-XX

### Added

- Range templating with import/export/clone
- Comprehensive range export with Docker images for offline deployment
- Range import with conflict detection and template resolution
- Artifact repository backed by MinIO with SHA256 verification
- Snapshot management and golden images for Windows VMs

## [0.2.0] - 2026-01-XX

### Added

- Multi-network support with custom subnets
- Visual range builder interface
- Range deployment orchestration
- VNC console access through Traefik proxy
- Dynamic network attachment for multi-homed VMs

## [0.1.0] - 2026-01-XX

### Added

- Initial release
- JWT authentication with user registration
- RBAC with 4 roles (Admin, Range Engineer, White Cell, Evaluator)
- ABAC with resource tags for fine-grained visibility
- VM template CRUD with 27+ OS templates
- Range CRUD with full lifecycle management
- Basic network management
