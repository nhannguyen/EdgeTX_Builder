"""
ConfigService — atomic read/write of targets.json.

This is the single source of truth for radio model configuration. All reads
and writes go through this service. Writes use a temp-file-then-rename pattern
to ensure atomicity (no partial writes corrupt the config).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from webapp.backend.models import (
    InvalidConfigError,
    ModelAlreadyExistsError,
    ModelNotFoundError,
    ModelCreate,
    ModelUpdate,
    ModelResponse,
    MODEL_KEY_RE,
    CMAKE_FLAG_RE,
)

# targets.json lives at the project root (two levels up from this file)
_TARGETS_JSON = Path(__file__).resolve().parent.parent.parent.parent / "targets.json"


class ConfigService:
    """Manages the targets.json configuration file."""

    def __init__(self, targets_path: Path = _TARGETS_JSON) -> None:
        self._path = targets_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_raw(self) -> dict[str, Any]:
        """Load and parse targets.json. Raises InvalidConfigError on failure."""
        if not self._path.exists():
            raise InvalidConfigError(
                f"Configuration file not found: {self._path}. "
                "Please ensure targets.json exists in the project root."
            )
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise InvalidConfigError(
                f"Configuration file is invalid or corrupted. Please check targets.json. "
                f"JSON error: {exc}"
            ) from exc
        except OSError as exc:
            raise InvalidConfigError(
                f"Cannot read configuration file: {exc}"
            ) from exc
        return data

    def _validate_structure(self, data: dict[str, Any]) -> None:
        """Verify that data has the expected top-level shape."""
        if not isinstance(data, dict):
            raise InvalidConfigError("Invalid JSON structure. Expected: {firmware_version, targets}")
        if "firmware_version" not in data or "targets" not in data:
            raise InvalidConfigError("Invalid JSON structure. Expected: {firmware_version, targets}")
        if not isinstance(data["targets"], dict):
            raise InvalidConfigError("Invalid JSON structure: 'targets' must be a JSON object.")

    def _save_raw(self, data: dict[str, Any]) -> None:
        """Atomically write data to targets.json (temp file + rename)."""
        tmp_path = self._path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=4)
            os.replace(tmp_path, self._path)
        except OSError as exc:
            # Attempt cleanup of temp file
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise InvalidConfigError(
                f"Permission denied: Cannot write to configuration file. "
                f"Please check folder permissions. Error: {exc}"
            ) from exc

    @staticmethod
    def _model_dict_to_response(key: str, target: dict[str, Any]) -> ModelResponse:
        return ModelResponse(
            key=key,
            pcb=target.get("pcb", ""),
            pcbrev=target.get("pcbrev") or None,
            enabled=bool(target.get("enabled", False)),
            extra_flags=list(target.get("extra_flags", [])),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_full_config(self) -> dict[str, Any]:
        """Return the full parsed targets.json structure."""
        data = self._load_raw()
        self._validate_structure(data)
        return data

    def get_firmware_version(self) -> str:
        """Return the firmware_version field from targets.json."""
        return self.get_full_config().get("firmware_version", "")

    def set_firmware_version(self, version: str) -> None:
        """Update only the firmware_version field in targets.json."""
        data = self._load_raw()
        self._validate_structure(data)
        data["firmware_version"] = version
        self._save_raw(data)

    def list_models(self) -> dict[str, ModelResponse]:
        """Return all models keyed by their model key."""
        data = self.get_full_config()
        return {
            key: self._model_dict_to_response(key, target)
            for key, target in data["targets"].items()
        }

    def get_model(self, key: str) -> ModelResponse:
        """Fetch a single model by key. Raises ModelNotFoundError if absent."""
        data = self.get_full_config()
        if key not in data["targets"]:
            raise ModelNotFoundError(f"Model not found: '{key}'")
        return self._model_dict_to_response(key, data["targets"][key])

    def add_model(self, model: ModelCreate) -> ModelResponse:
        """Add a new model. Raises ModelAlreadyExistsError on duplicate key."""
        data = self._load_raw()
        self._validate_structure(data)
        if model.key in data["targets"]:
            raise ModelAlreadyExistsError(
                f"Model name already exists: '{model.key}'. Please choose a unique name."
            )
        entry: dict[str, Any] = {
            "pcb": model.pcb,
            "enabled": model.enabled,
            "extra_flags": model.extra_flags,
        }
        if model.pcbrev:
            entry["pcbrev"] = model.pcbrev
        data["targets"][model.key] = entry
        self._save_raw(data)
        return self._model_dict_to_response(model.key, entry)

    def update_model(self, key: str, update: ModelUpdate) -> ModelResponse:
        """Apply a partial update to an existing model. Raises ModelNotFoundError if absent."""
        data = self._load_raw()
        self._validate_structure(data)
        if key not in data["targets"]:
            raise ModelNotFoundError(f"Model not found: '{key}'")
        target = data["targets"][key]
        if update.pcb is not None:
            target["pcb"] = update.pcb
        if update.pcbrev is not None:
            target["pcbrev"] = update.pcbrev if update.pcbrev else None
            if not update.pcbrev:
                target.pop("pcbrev", None)
        if update.enabled is not None:
            target["enabled"] = update.enabled
        if update.extra_flags is not None:
            target["extra_flags"] = update.extra_flags
        data["targets"][key] = target
        self._save_raw(data)
        return self._model_dict_to_response(key, target)

    def delete_model(self, key: str) -> None:
        """Remove a model by key. Raises ModelNotFoundError if absent."""
        data = self._load_raw()
        self._validate_structure(data)
        if key not in data["targets"]:
            raise ModelNotFoundError(f"Model not found: '{key}'")
        del data["targets"][key]
        self._save_raw(data)

    def replace_config(self, new_data: dict[str, Any]) -> int:
        """Replace the entire configuration with new_data. Returns model count."""
        self._validate_structure(new_data)
        self._save_raw(new_data)
        return len(new_data["targets"])

    def validate_model_keys_exist(self, keys: list[str]) -> list[str]:
        """
        Check that all provided keys exist in the current configuration.
        Returns a list of error messages for missing keys (empty list = all valid).
        """
        data = self.get_full_config()
        existing = set(data["targets"].keys())
        errors: list[str] = []
        for key in keys:
            if key not in existing:
                errors.append(f"Model '{key}' not found in configuration.")
        return errors
