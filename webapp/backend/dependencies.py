"""
FastAPI dependency providers for service instances.

All services are created once at application startup and shared via module-level
singletons. Dependencies resolve them via these provider functions.
"""
from __future__ import annotations

from webapp.backend.services.artifact_service import ArtifactService
from webapp.backend.services.build_service import BuildService
from webapp.backend.services.config_service import ConfigService
from webapp.backend.services.health_service import HealthService
from webapp.backend.services.history_service import HistoryService
from webapp.backend.services.settings_service import SettingsService

# ---------------------------------------------------------------------------
# Singleton instances (created at module import time)
# ---------------------------------------------------------------------------

_config_service = ConfigService()
_settings_service = SettingsService()
_history_service = HistoryService()
_artifact_service = ArtifactService()
_health_service = HealthService(settings_service=_settings_service)
_build_service = BuildService(
    config_service=_config_service,
    history_service=_history_service,
    settings_service=_settings_service,
    artifact_service=_artifact_service,
)

# ---------------------------------------------------------------------------
# Dependency provider functions
# ---------------------------------------------------------------------------


def get_config_service() -> ConfigService:
    return _config_service


def get_settings_service() -> SettingsService:
    return _settings_service


def get_history_service() -> HistoryService:
    return _history_service


def get_artifact_service() -> ArtifactService:
    return _artifact_service


def get_health_service() -> HealthService:
    return _health_service


def get_build_service() -> BuildService:
    return _build_service
