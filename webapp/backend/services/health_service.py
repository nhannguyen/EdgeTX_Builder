"""
HealthService — checks system prerequisites (toolchain, cmake, git repo, disk access).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from webapp.backend.models import HealthReport
from webapp.backend.services.settings_service import SettingsService

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DIST_DIR = _PROJECT_ROOT / "dist"
_LOGS_DIR = _PROJECT_ROOT / "logs"
_EDGETX_DIR = _PROJECT_ROOT / "edgetx"


class HealthService:
    """Checks system health on demand."""

    def __init__(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    def check(self) -> HealthReport:
        """Run all health checks and return a report."""
        settings = self._settings.get()
        checks: dict = {}
        any_error = False
        any_warning = False

        # --- Toolchain check ---
        toolchain_path = settings.toolchain_path
        if not toolchain_path:
            # Try auto-detection
            found = shutil.which("arm-none-eabi-gcc")
            if found:
                detected_dir = str(Path(found).parent)
                checks["toolchain"] = {
                    "ok": True,
                    "path": detected_dir,
                    "message": f"Auto-detected: {detected_dir}",
                }
            else:
                checks["toolchain"] = {
                    "ok": False,
                    "path": "",
                    "message": "ARM toolchain not found. Please configure the toolchain path in Settings.",
                }
                any_warning = True
        else:
            binary = Path(toolchain_path) / "arm-none-eabi-gcc"
            if binary.exists():
                checks["toolchain"] = {
                    "ok": True,
                    "path": toolchain_path,
                    "message": None,
                }
            else:
                checks["toolchain"] = {
                    "ok": False,
                    "path": toolchain_path,
                    "message": f"arm-none-eabi-gcc not found in: {toolchain_path}",
                }
                any_warning = True

        # --- CMake check ---
        cmake_bin = shutil.which("cmake")
        if cmake_bin:
            try:
                result = subprocess.run(
                    ["cmake", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                version_line = result.stdout.splitlines()[0] if result.stdout else ""
                version = version_line.replace("cmake version", "").strip()
                checks["cmake"] = {"ok": True, "version": version}
            except (subprocess.SubprocessError, OSError, IndexError):
                checks["cmake"] = {"ok": True, "version": None}
        else:
            checks["cmake"] = {
                "ok": False,
                "version": None,
                "message": "CMake is not installed or not in PATH. Please install CMake.",
            }
            any_error = True

        # --- Git repo check ---
        git_ok = (_EDGETX_DIR / ".git").exists() or _EDGETX_DIR.is_dir()
        checks["git_repo"] = {
            "ok": git_ok,
            "path": str(_EDGETX_DIR),
            "message": None if git_ok else "EdgeTX source directory not found.",
        }
        if not git_ok:
            any_warning = True

        # --- dist/ writable check ---
        try:
            _DIST_DIR.mkdir(parents=True, exist_ok=True)
            test_file = _DIST_DIR / ".write_test"
            test_file.touch()
            test_file.unlink()
            checks["dist_writable"] = {"ok": True}
        except OSError:
            checks["dist_writable"] = {"ok": False, "message": "dist/ is not writable."}
            any_error = True

        # --- logs/ writable check ---
        try:
            _LOGS_DIR.mkdir(parents=True, exist_ok=True)
            test_file = _LOGS_DIR / ".write_test"
            test_file.touch()
            test_file.unlink()
            checks["logs_writable"] = {"ok": True}
        except OSError:
            checks["logs_writable"] = {"ok": False, "message": "logs/ is not writable."}
            any_error = True

        if any_error:
            overall = "error"
        elif any_warning:
            overall = "degraded"
        else:
            overall = "ok"

        return HealthReport(status=overall, checks=checks)
