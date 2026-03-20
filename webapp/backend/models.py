"""
Pydantic models and domain exceptions for the EdgeTX Firmware Web Builder.
"""
from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

MODEL_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CMAKE_FLAG_RE = re.compile(r"^-D[A-Z0-9_]+=\S+$")
# Firmware version: allow digits, dots, letters, hyphens, and underscores only.
# Examples of valid values: "2.12", "2.12.0", "v2.12-rc1", "nightly-20260101".
# This prevents shell metacharacters, path separators, and control characters
# from entering the value that is written back to targets.json and passed to
# custom_build.py as a subprocess argument.
FIRMWARE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")

VALID_COMPONENTS = {"all", "firmware", "simulator"}
VALID_STATUSES = {"running", "success", "failed", "aborted"}


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class ModelNotFoundError(Exception):
    """Raised when a requested model key does not exist in the configuration."""


class ModelAlreadyExistsError(Exception):
    """Raised when attempting to add a model whose key already exists."""


class InvalidConfigError(Exception):
    """Raised when targets.json is malformed or fails schema validation."""


class BuildAlreadyRunningError(Exception):
    """Raised when a new build is requested while one is already in progress."""


class BuildNotFoundError(Exception):
    """Raised when a build ID cannot be found in active or completed builds."""


class BuildNotRunningError(Exception):
    """Raised when an abort is requested for a build that is not running."""


class HistoryNotFoundError(Exception):
    """Raised when a history entry cannot be found."""


class ArtifactNotFoundError(Exception):
    """Raised when a requested artifact file does not exist."""


class InvalidPathError(Exception):
    """Raised when a path traversal attempt is detected."""


# ---------------------------------------------------------------------------
# Radio model schema
# ---------------------------------------------------------------------------


class ModelCreate(BaseModel):
    key: str
    pcb: str
    pcbrev: Optional[str] = None
    enabled: bool = False
    extra_flags: list[str] = []

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Model name is required.")
        if not MODEL_KEY_RE.match(v):
            raise ValueError(
                "Model key must be lowercase alphanumeric and may contain hyphens or underscores."
            )
        return v

    @field_validator("pcb")
    @classmethod
    def validate_pcb(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("PCB type is required.")
        return v

    @field_validator("extra_flags", mode="before")
    @classmethod
    def validate_extra_flags(cls, v: list) -> list[str]:
        errors: list[str] = []
        for flag in v:
            flag = str(flag).strip()
            if flag and not CMAKE_FLAG_RE.match(flag):
                errors.append(
                    f"Invalid CMake flag format: '{flag}'. Expected format: -DFLAG_NAME=VALUE"
                )
        if errors:
            raise ValueError("; ".join(errors))
        return [str(f).strip() for f in v if str(f).strip()]


class ModelUpdate(BaseModel):
    pcb: Optional[str] = None
    pcbrev: Optional[str] = None
    enabled: Optional[bool] = None
    extra_flags: Optional[list[str]] = None

    @field_validator("pcb")
    @classmethod
    def validate_pcb(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("PCB type is required.")
        return v

    @field_validator("extra_flags", mode="before")
    @classmethod
    def validate_extra_flags(cls, v: Optional[list]) -> Optional[list[str]]:
        if v is None:
            return v
        errors: list[str] = []
        for flag in v:
            flag = str(flag).strip()
            if flag and not CMAKE_FLAG_RE.match(flag):
                errors.append(
                    f"Invalid CMake flag format: '{flag}'. Expected format: -DFLAG_NAME=VALUE"
                )
        if errors:
            raise ValueError("; ".join(errors))
        return [str(f).strip() for f in v if str(f).strip()]


class ModelResponse(BaseModel):
    key: str
    pcb: str
    pcbrev: Optional[str] = None
    enabled: bool
    extra_flags: list[str]


# ---------------------------------------------------------------------------
# Build request / status
# ---------------------------------------------------------------------------


class BuildRequest(BaseModel):
    selected_models: list[str]
    component: str = "all"
    firmware_version: Optional[str] = None
    clean: bool = False
    jobs: int = 0  # 0 means use CPU count

    @field_validator("selected_models")
    @classmethod
    def validate_selected_models(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Please select at least one model to build.")
        validated: list[str] = []
        for key in v:
            key = key.strip()
            if not MODEL_KEY_RE.match(key):
                raise ValueError(
                    f"Invalid model key '{key}'. Keys must be lowercase alphanumeric with optional hyphens/underscores."
                )
            validated.append(key)
        return validated

    @field_validator("component")
    @classmethod
    def validate_component(cls, v: str) -> str:
        if v not in VALID_COMPONENTS:
            raise ValueError(f"Component must be one of: {', '.join(VALID_COMPONENTS)}")
        return v

    @field_validator("firmware_version")
    @classmethod
    def validate_firmware_version(cls, v: Optional[str]) -> Optional[str]:
        """
        Reject firmware version strings that contain shell metacharacters,
        path separators, whitespace, or other characters that should never
        appear in a version tag.  The value is written to targets.json and
        passed as a subprocess argument; keeping the allowed character set
        narrow is the safest approach.
        """
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not FIRMWARE_VERSION_RE.match(v):
            raise ValueError(
                "Firmware version must start with an alphanumeric character and "
                "may only contain letters, digits, dots, hyphens, and underscores "
                "(max 64 characters). Example: '2.12.0' or 'nightly-20260101'."
            )
        return v

    @field_validator("jobs")
    @classmethod
    def validate_jobs(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Parallel jobs must be a positive integer (minimum 1).")
        return v


class BuildStatusResponse(BaseModel):
    build_id: str
    status: str
    timestamp: str
    selected_models: list[str]
    current_model: Optional[str] = None
    progress: int = 0
    artifacts: dict[str, list[str]] = {}
    error: Optional[str] = None
    end_time: Optional[str] = None


# ---------------------------------------------------------------------------
# Build history
# ---------------------------------------------------------------------------


class BuildHistoryEntry(BaseModel):
    build_id: str
    timestamp: str
    end_time: str
    models: list[str]
    status: str
    firmware_version: str
    component: str
    clean: bool
    jobs: int
    duration_ms: int
    log_file: str


class HistoryListResponse(BaseModel):
    items: list[BuildHistoryEntry]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# App settings
# ---------------------------------------------------------------------------


class AppSettings(BaseModel):
    toolchain_path: str = ""
    build_output_directory: str = "./dist"
    logs_directory: str = "./logs"
    auto_clean_old_builds: bool = False
    build_history_retention_days: int = 0


class AppSettingsUpdate(BaseModel):
    toolchain_path: Optional[str] = None
    build_output_directory: Optional[str] = None
    logs_directory: Optional[str] = None
    auto_clean_old_builds: Optional[bool] = None
    build_history_retention_days: Optional[int] = None


# ---------------------------------------------------------------------------
# Config import/export
# ---------------------------------------------------------------------------


class ConfigImportResponse(BaseModel):
    message: str
    model_count: int


# ---------------------------------------------------------------------------
# Artifact info
# ---------------------------------------------------------------------------


class ArtifactInfo(BaseModel):
    filename: str
    size_bytes: int
    modified: str


class ArtifactListResponse(BaseModel):
    model: str
    files: list[ArtifactInfo]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class CheckResult(BaseModel):
    ok: bool
    message: Optional[str] = None


class ToolchainCheckResult(CheckResult):
    path: str = ""


class CmakeCheckResult(CheckResult):
    version: Optional[str] = None


class GitRepoCheckResult(CheckResult):
    path: str = ""


class HealthReport(BaseModel):
    status: str  # "ok" | "degraded" | "error"
    checks: dict
