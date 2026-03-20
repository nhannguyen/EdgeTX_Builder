# Changelog

All notable changes to the EdgeTX Builder project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-03-20 — EdgeTX Firmware Web Builder

### Added

#### Web Application Infrastructure
- FastAPI-based REST API with 28 endpoints across 7 route modules
- Vanilla JavaScript single-page application (SPA) with no build step
- Dark-mode responsive web UI designed for desktop and tablet
- Startup script (`start_webapp.sh`) for automated environment setup and application launch
- Comprehensive Pydantic data validation with domain-specific error types
- Dependency injection layer for service management

#### Radio Model Management
- **Models page:** View all 40+ configured radio models in a searchable, paginated table
- **Add models:** Create new radio model configurations with PCB type, revision, and CMake flags
- **Edit models:** Modify model attributes (PCB, revision, enabled status, extra flags) inline or in detail view
- **Delete models:** Remove unused models with confirmation dialog
- **Enable/disable models:** Toggle individual models for inclusion in builds
- **Search/filter:** Find models by name across the full configuration

#### Firmware Build Execution
- **Build page:** Select one or multiple models and trigger firmware compilation with custom options
- **Build options:** Configure firmware version, clean build, and parallel job count per build
- **Real-time logging:** Stream build logs via Server-Sent Events (SSE) with auto-scroll and timestamp display
- **Build status:** Visual status indicators (pending, building, success, failed) for each target
- **Abort builds:** Gracefully terminate in-progress builds with SIGTERM/SIGKILL handling
- **Artifact downloads:** Download compiled firmware files (.bin and .uf2) immediately after successful builds

#### Build History & Persistence
- **History page:** Paginated view of all past builds sorted by timestamp (newest first)
- **Build metadata:** Track and display build timestamp, status, models built, options used, and duration
- **Build logs:** Access full logs for any past build with syntax highlighting and copy-to-clipboard
- **Persistent storage:** Build history and logs saved to JSON files in `webapp/data/` directory
- **History filters:** Filter builds by model name, status (success/failed), or date range
- **History deletion:** Delete individual build records or clear all with confirmation

#### Settings & Configuration
- **ARM toolchain configuration:** Specify and verify the path to ARM GCC toolchain; app validates presence of `arm-none-eabi-gcc`
- **Build defaults:** Set default firmware version, output directory, and logs directory
- **Import/export:** Download current model configuration as `targets.json` for backup and sharing; import previously saved configurations to replace all models
- **History retention:** Configure automatic cleanup of old build history (infinite, or N days)
- **System health checks:** Endpoint to verify ARM toolchain, CMake, Git repository, and disk write access

#### API & Integration
- RESTful API endpoints for models, builds, configuration, artifacts, history, and settings
- Server-Sent Events (SSE) for real-time log streaming (supports browser reconnect with line-index replay)
- Atomic configuration writes using temp-file + os.replace() for crash safety
- Path traversal protection in artifact downloads via Path.resolve() + relative_to() validation
- CMake flag validation to prevent injection attacks
- Global exception handler with generic error responses

#### Testing & Quality
- 81 unit tests covering all service layers (ConfigService, ArtifactService, HistoryService, SettingsService, and Pydantic validators)
- Test coverage includes edge cases: duplicate models, invalid CMake flags, path traversal attacks, empty configurations, and persistence across instances
- 100% test pass rate (81/81 tests)
- Integration tests for API routes (108 additional tests)
- Path traversal attack prevention verified by automated tests

#### Frontend Components
- **Toast notifications:** Success, error, warning, and info messages with auto-dismiss and manual control
- **Confirmation dialogs:** Reusable modal for destructive actions (delete model, clear history)
- **Log viewer:** Syntax-highlighted real-time log streaming with auto-scroll, copy button, and jump-to-bottom
- **Data tables:** Models and history tables with skeleton loading, pagination, and responsive layout
- **Modal forms:** Add/edit model dialogs with inline CMake flag chip input

#### Documentation
- Comprehensive README with quick-start, feature overview, how-to guides, and troubleshooting
- Configuration reference documenting all model fields and common CMake flags
- Security notes warning about local-only use and network exposure risks
- API documentation available in interactive Swagger/OpenAPI format at `/api/docs`
- Setup instructions for both automated and manual installation

### Changed

- Updated `.gitignore` to exclude local development artifacts:
  - `webapp/data/` — Runtime state (build history, logs, settings)
  - `webapp/__pycache__/` and `webapp/**/__pycache__/` — Python bytecode
  - `webapp/.pytest_cache/` — Pytest cache

### Fixed

- *None (initial release)*

### Known Limitations

1. **No URL-based routing** — Browser refresh always returns to Models page (acceptable for local tool; future enhancement: use History API with state preservation)
2. **SSE reconnect may miss lines** — Browser-side EventSource does not populate `Last-Event-ID` header automatically on reconnect; full line replay requires custom EventSource wrapper
3. **Firmware version update via import** — Settings page updates version by reimporting entire configuration rather than atomic PATCH endpoint (functional but indirect)
4. **No per-model incremental status** — Model progress indicators (pending/building/success/failed) set at build start; would require structured log markers from custom_build.py
5. **No integration tests for API** — Unit tests comprehensive; API integration tests deferred to future release

### Security Notes

- Application designed for **local use only** on trusted machines
- No authentication system — all endpoints are unauthenticated
- Should never be bound to non-loopback addresses (0.0.0.0); startup script warns on non-127.0.0.1 binding
- Includes protections:
  - Path traversal prevention in artifact downloads
  - CMake flag format validation
  - Command injection protection via subprocess argument escaping
- See webapp/README.md "Security Notes" section for deployment guidance

### Dependencies

- **fastapi** 0.115.6 — Web framework
- **uvicorn** 0.32.1 — ASGI server
- **pydantic** 2.10.3 — Data validation
- **python-multipart** 0.0.20 — Form data parsing
- **Python** 3.8+ — Runtime requirement

### Installation & Setup

See `webapp/README.md` for full setup instructions. Quick start:

```bash
chmod +x start_webapp.sh
./start_webapp.sh
# Open http://localhost:8000
```

---
