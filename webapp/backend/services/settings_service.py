"""
SettingsService — read/write application settings to webapp/data/app_settings.json.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from webapp.backend.models import AppSettings, AppSettingsUpdate

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_SETTINGS_FILE = _DATA_DIR / "app_settings.json"


class SettingsService:
    """Manages app_settings.json persistence."""

    def __init__(self, settings_path: Path = _SETTINGS_FILE) -> None:
        self._path = settings_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> AppSettings:
        """Load settings from disk, returning defaults if the file does not exist."""
        if not self._path.exists():
            return AppSettings()
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return AppSettings(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return AppSettings()

    def update(self, update: AppSettingsUpdate) -> AppSettings:
        """Apply a partial update to settings and persist."""
        current = self.get()
        patch = update.model_dump(exclude_none=True)
        merged = current.model_dump()
        merged.update(patch)
        new_settings = AppSettings(**merged)
        self._save(new_settings)
        return new_settings

    def _save(self, settings: AppSettings) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(settings.model_dump(), fh, indent=4)
            os.replace(tmp, self._path)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise exc

    def validate_toolchain(self, path: str) -> bool:
        """Return True if arm-none-eabi-gcc is found in the given path."""
        if not path:
            return bool(shutil.which("arm-none-eabi-gcc"))
        toolchain_dir = Path(path)
        if not toolchain_dir.is_dir():
            return False
        binary = toolchain_dir / "arm-none-eabi-gcc"
        if binary.exists():
            return True
        # Also check with .exe extension on Windows (not primary target, but defensive)
        binary_exe = toolchain_dir / "arm-none-eabi-gcc.exe"
        if binary_exe.exists():
            return True
        return False
