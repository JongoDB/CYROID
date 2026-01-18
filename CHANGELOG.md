# Changelog

All notable changes to CYROID will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-01-17

### Added

- **Range Blueprints** ([#18](../../issues/18)): Save ranges as reusable blueprints and deploy multiple isolated instances with auto-allocated subnets.
  - Save any range as a blueprint with "Save as Blueprint" button
  - Deploy instances from blueprints with automatic subnet offset (10.100 → 10.101 → 10.102)
  - Instance actions: reset (same version), redeploy (latest version), clone
  - Blueprints page with card grid showing all blueprints
  - Blueprint detail page with instances tab
  - Instance info banner on RangeDetail for blueprint-deployed ranges
  - New API endpoints: /blueprints, /instances
  - RangeBlueprint and RangeInstance database models

## [0.5.0] - 2026-01-17

### Added

- **Guided Range Builder Wizard** ([#19](../../issues/19)): New wizard-style interface for creating complete cyber training environments with minimal manual configuration.
  - 4 scenario presets: AD Enterprise Lab, Segmented Network (DMZ), Incident Response Lab, Penetration Testing Target
  - 5-step wizard flow: Scenario Selection → Zone Configuration → System Selection → Configuration Options → Review & Deploy
  - Auto-assigned subnets and IP addresses for each zone and system
  - AD configuration options: domain name, admin password, user count
  - Vulnerability level selection (cosmetic in v1)
  - Sequential deployment with progress indicator
  - "Guided Builder" button on Ranges page header
  - Empty state CTA prioritizes guided builder for first-time users
  - Template name-to-ID mapping for flexible preset definitions

## [0.4.11] - 2026-01-17

### Added

- **Student Lab Page with Walkthrough Panel** ([#8](../../issues/8)): New `/lab/:rangeId` page provides a student-focused experience with integrated step-by-step walkthrough alongside VNC consoles.
  - WalkthroughPanel: Collapsible left panel with phase navigation, step checklist, and markdown content
  - Progress tracking: Local storage + optional server sync with auto-save
  - VM integration: "Open VM" button switches console to referenced VM
  - Split-pane layout: Resizable panels with embedded VNC console
  - Markdown rendering: Code blocks, blockquotes (tips/warnings), headers
  - MSEL extension: Walkthrough content authored in YAML `walkthrough:` section
  - New WalkthroughProgress model for server-side progress persistence
  - "Open Lab" button on RangeDetail page for running ranges

## [0.4.10] - 2026-01-17

### Fixed

- **Delete Confirmation UX** ([#20](../../issues/20)): Replaced browser native `window.confirm()` popups with styled confirmation dialogs. Fixed double-click issue and improved visual consistency across all delete operations.
  - Created reusable ConfirmDialog component with danger/warning/info variants
  - Updated Range, Network, VM, Template, and Image Cache delete confirmations
  - Replaced `alert()` error messages with toast notifications

## [0.4.9] - 2026-01-17

### Added

- **Diagnostics Dashboard** ([#4](../../issues/4)): New "Diagnostics" tab on RangeDetail page provides visibility into component health, error history, and container logs without requiring SSH or Docker CLI access.
  - ComponentHealth: Collapsible status tree showing Range → Router → Networks → VMs with color-coded health indicators
  - ErrorTimeline: Chronological display of error events (vm_error, deployment_failed, inject_failed) with filtering
  - LogViewer: On-demand container log retrieval with refresh, copy-to-clipboard, and auto-scroll
  - Error badge on tab shows count of components in error state
  - `error_message` field added to VM and Range models to persist error details
  - New `GET /api/v1/vms/{id}/logs` endpoint for fetching container logs

## [0.4.8] - 2026-01-17

### Fixed

- **Traefik Network Connection** ([#17](../../issues/17)): Fixed bug where Traefik was only connected to isolated networks during deployment, causing VNC console access to fail for non-isolated networks. Traefik is now connected to all range networks regardless of isolation status.

## [0.4.7] - 2026-01-17

### Fixed

- **Console Connection Feedback** ([#15](../../issues/15)): Console windows now provide clear feedback when connections fail or timeout instead of showing blank screens.
  - VNC console shows 30-second timeout warning with troubleshooting options
  - Terminal console shows connection status and helpful error messages
  - Both consoles have a Help button with troubleshooting tips
  - Loading states clearly indicate connection progress
  - Error states provide actionable guidance (Retry, Keep Waiting, Close)

## [0.4.6] - 2026-01-17

### Added

- **AI-Friendly API Documentation** ([#12](../../issues/12)): Enhanced OpenAPI documentation with comprehensive descriptions, organized tags, and a dedicated `/api/v1/schema/ai-context` endpoint that provides a condensed API guide for AI assistants. Enables AI tools to generate valid CYROID configurations without source code access.

### Changed

- OpenAPI description now includes concepts guide, quick start, and authentication info
- API endpoints organized with descriptive tags in Swagger UI

## [0.4.5] - 2026-01-17

### Fixed

- **Console Opens in New Window** ([#13](../../issues/13)): Console button on Range Detail page now opens console in a new browser window by default (Shift+click for inline modal). Previously only worked from Execution Console.
- **Range Stop Cleans Up Router** ([#11](../../issues/11)): Stopping a range now properly stops the VyOS router container in addition to VMs. Starting a stopped range now starts the router before VMs.
- **Escape Key Closes Console** ([#14](../../issues/14)): Pressing Escape now closes the inline console modal and returns to the range view.

## [0.4.4] - 2026-01-16

### Added

- **Real-Time UI Updates via WebSocket** ([#5](../../issues/5)): Live status updates without page refresh. When deploying a range, starting VMs, or performing any operation, users now see status updates in real-time as they happen.
  - WebSocket event streaming with Redis pub/sub for scalable broadcasting
  - Selective subscription to specific ranges for efficient bandwidth usage
  - Toast notifications for significant events (deployment complete, VM errors)
  - Pulse animations on status badges when VM states change
  - Connection status indicator showing live update availability
  - `useRealtimeRange` React hook for easy integration

### Changed

- WebSocket endpoints enhanced with Redis pub/sub infrastructure
- EventService now broadcasts events to connected clients in real-time
- Added connection manager for WebSocket lifecycle and subscriptions

## [0.4.3] - 2026-01-16

### Added

- **Verbose Deployment Progress** ([#6](../../issues/6)): Real-time deployment status with visual stepper and expandable log panel. Shows step-by-step progress through router creation, network provisioning, and VM startup. Includes detailed event logging with timestamps and color-coded status indicators.

### Changed

- Added 9 new deployment event types for granular progress tracking
- Events API now supports filtering by event_types parameter
- Event log component updated with icons for all deployment events

## [0.4.2] - 2026-01-16

### Added

- **Multi-Architecture Support**: Native support for both x86_64 and ARM64 host systems with automatic architecture detection and emulation warnings for cross-architecture VMs

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
