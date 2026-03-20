"""
BuildService — manages the lifecycle of firmware builds.

Enforces the single-build constraint, constructs subprocess arguments,
manages the active BuildStatus, streams SSE log lines, and persists
completed builds to HistoryService.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

from webapp.backend.models import (
    BuildAlreadyRunningError,
    BuildNotFoundError,
    BuildNotRunningError,
    BuildRequest,
    BuildStatusResponse,
    BuildHistoryEntry,
)
from webapp.backend.services.build_executor import BuildExecutor, BuildHandle
from webapp.backend.services.config_service import ConfigService
from webapp.backend.services.history_service import HistoryService
from webapp.backend.services.settings_service import SettingsService
from webapp.backend.services.artifact_service import ArtifactService

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CUSTOM_BUILD = _PROJECT_ROOT / "custom_build.py"

# Maximum lines to stream live over SSE; beyond this, serve a truncation notice
_MAX_STREAM_LINES = 5000


class _BuildState:
    """In-memory state for one build run."""

    def __init__(
        self,
        build_id: str,
        request: BuildRequest,
        firmware_version: str,
        jobs: int,
    ) -> None:
        self.build_id = build_id
        self.request = request
        self.firmware_version = firmware_version
        self.jobs = jobs
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.status = "running"
        self.current_model: Optional[str] = None
        self.progress = 0
        self.artifacts: dict[str, list[str]] = {}
        self.error: Optional[str] = None
        self.end_time: Optional[str] = None
        self.handle: Optional[BuildHandle] = None

    def to_response(self) -> BuildStatusResponse:
        return BuildStatusResponse(
            build_id=self.build_id,
            status=self.status,
            timestamp=self.timestamp,
            selected_models=self.request.selected_models,
            current_model=self.current_model,
            progress=self.progress,
            artifacts=self.artifacts,
            error=self.error,
            end_time=self.end_time,
        )


class BuildService:
    """Owns the single active build and provides log streaming."""

    def __init__(
        self,
        config_service: ConfigService,
        history_service: HistoryService,
        settings_service: SettingsService,
        artifact_service: ArtifactService,
    ) -> None:
        self._config = config_service
        self._history = history_service
        self._settings = settings_service
        self._artifacts = artifact_service
        self._active: Optional[_BuildState] = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_build(self, request: BuildRequest) -> BuildStatusResponse:
        """
        Start a new build. Raises BuildAlreadyRunningError if one is in progress.
        """
        async with self._lock:
            if self._active is not None and self._active.status == "running":
                raise BuildAlreadyRunningError(
                    "A build is already in progress. Please wait or view the current build status."
                )

            # Validate all selected models exist
            errors = self._config.validate_model_keys_exist(request.selected_models)
            if errors:
                from webapp.backend.models import ModelNotFoundError
                raise ModelNotFoundError(errors[0])

            # Resolve firmware version
            firmware_version = request.firmware_version or self._config.get_firmware_version()

            # Resolve jobs
            jobs = request.jobs if request.jobs > 0 else os.cpu_count() or 4

            build_id = str(uuid.uuid4())
            state = _BuildState(
                build_id=build_id,
                request=request,
                firmware_version=firmware_version,
                jobs=jobs,
            )
            self._active = state

        # Launch the build as a background task (outside the lock to avoid blocking)
        asyncio.create_task(self._run_build(state))
        return state.to_response()

    def get_active_build(self) -> Optional[BuildStatusResponse]:
        """Return the active build status, or None if no build is running."""
        if self._active is None:
            return None
        return self._active.to_response()

    def get_build(self, build_id: str) -> BuildStatusResponse:
        """
        Return build status by ID.
        Checks active build first, then history.
        """
        if self._active and self._active.build_id == build_id:
            return self._active.to_response()
        # Check history
        try:
            entry = self._history.get(build_id)
            return BuildStatusResponse(
                build_id=entry.build_id,
                status=entry.status,
                timestamp=entry.timestamp,
                selected_models=entry.models,
                end_time=entry.end_time,
                progress=100 if entry.status == "success" else 0,
            )
        except Exception:
            raise BuildNotFoundError(f"Build not found: '{build_id}'")

    async def abort_build(self, build_id: str) -> None:
        """
        Request graceful abort. Raises BuildNotFoundError or BuildNotRunningError
        as appropriate.
        """
        if self._active is None or self._active.build_id != build_id:
            # Check if it's in history (completed)
            try:
                self._history.get(build_id)
                raise BuildNotRunningError("Build is not in progress.")
            except Exception as exc:
                if isinstance(exc, BuildNotRunningError):
                    raise
                raise BuildNotFoundError(f"Build not found: '{build_id}'") from exc

        state = self._active
        if state.status != "running":
            raise BuildNotRunningError("Build is not in progress.")

        if state.handle:
            state.handle.terminate()
            # SIGKILL fallback after 5 seconds
            asyncio.create_task(self._sigkill_fallback(state))

    # ------------------------------------------------------------------
    # SSE log streaming
    # ------------------------------------------------------------------

    async def subscribe_logs(
        self, build_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Yield SSE-formatted log lines for the given build ID.

        Supports reconnect via Last-Event-ID: the caller passes from_index
        (already handled by the route layer which calls this with the right offset).
        """
        async for sse_event in self._stream_logs(build_id, from_index=0):
            yield sse_event

    def validate_build_exists(self, build_id: str) -> None:
        """
        Raise BuildNotFoundError synchronously if the build_id is unknown.

        This must be called BEFORE creating a StreamingResponse so that the
        404 can be returned as a proper HTTP error response.  The async
        generator itself cannot raise a catchable exception after the response
        headers have already been sent.
        """
        if self._active and self._active.build_id == build_id:
            return  # active build — exists
        log_path = self._history.get_log_path(build_id)
        if log_path is None:
            raise BuildNotFoundError(f"Build not found: '{build_id}'")

    async def stream_logs_from(
        self, build_id: str, from_index: int = 0
    ) -> AsyncGenerator[str, None]:
        """Stream SSE log events starting from the given line index."""
        async for sse_event in self._stream_logs(build_id, from_index):
            yield sse_event

    async def _stream_logs(
        self, build_id: str, from_index: int = 0
    ) -> AsyncGenerator[str, None]:
        """Internal: yields SSE-formatted strings."""
        # Determine the source of log lines
        state = self._active if (self._active and self._active.build_id == build_id) else None

        if state is None:
            # Build may be finished — serve from history log file
            log_path = self._history.get_log_path(build_id)
            if log_path is None:
                raise BuildNotFoundError(f"Build not found: '{build_id}'")

            with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()

            for idx, line in enumerate(lines[from_index:], start=from_index):
                yield f"id: {idx}\ndata: {line}\n\n"

            # Determine final status from history
            try:
                entry = self._history.get(build_id)
                final_status = entry.status
            except Exception:
                final_status = "success"
            yield f"event: done\ndata: {{\"status\": \"{final_status}\", \"exit_code\": 0}}\n\n"
            return

        if state.handle is None:
            # Build started but handle not yet assigned — wait briefly
            for _ in range(20):
                await asyncio.sleep(0.1)
                if state.handle is not None:
                    break

        if state.handle is None:
            yield f"event: done\ndata: {{\"status\": \"failed\", \"exit_code\": -1}}\n\n"
            return

        handle = state.handle
        line_count = 0
        truncation_sent = False

        async for line in handle.lines(from_index=from_index):
            line_index = from_index + line_count

            # Truncation notice for very large logs
            if line_index >= _MAX_STREAM_LINES and not truncation_sent:
                truncation_sent = True
                yield (
                    f"event: truncated\n"
                    f"data: Showing last {_MAX_STREAM_LINES} lines. "
                    f"Download full log from history.\n\n"
                )
            else:
                yield f"id: {line_index}\ndata: {line}\n\n"

            line_count += 1

        # Build finished — send done event
        exit_code = handle.exit_code if handle.exit_code is not None else 0
        final_status = state.status
        yield f"event: done\ndata: {{\"status\": \"{final_status}\", \"exit_code\": {exit_code}}}\n\n"

    # ------------------------------------------------------------------
    # Build runner (background task)
    # ------------------------------------------------------------------

    async def _run_build(self, state: _BuildState) -> None:
        """
        Background task that executes the build subprocess and updates state.
        """
        start_ts = datetime.now(timezone.utc)
        original_version: Optional[str] = None

        try:
            settings = self._settings.get()

            # If a specific firmware version was requested, temporarily update targets.json
            current_version = self._config.get_firmware_version()
            if state.firmware_version != current_version:
                original_version = current_version
                self._config.set_firmware_version(state.firmware_version)

            # Build the command list (no shell=True)
            cmd = self._build_command(state, settings)

            # Update current_model to first model
            if state.request.selected_models:
                state.current_model = state.request.selected_models[0]

            # Spawn subprocess
            handle = await BuildExecutor.execute(cmd, cwd=_PROJECT_ROOT)
            state.handle = handle

            # Wait for completion
            exit_code = await handle.wait()

            state.end_time = datetime.now(timezone.utc).isoformat()
            end_ts = datetime.now(timezone.utc)
            duration_ms = int((end_ts - start_ts).total_seconds() * 1000)

            if exit_code == 0:
                state.status = "success"
                state.progress = 100
                state.current_model = None
                # Collect artifacts
                for model_key in state.request.selected_models:
                    artifact_response = self._artifacts.list_artifacts(model_key)
                    state.artifacts[model_key] = [
                        f.filename for f in artifact_response.files
                    ]
            else:
                state.status = "failed"
                state.error = f"Build failed with exit code {exit_code}. See logs for details."

        except asyncio.CancelledError:
            state.status = "aborted"
            state.end_time = datetime.now(timezone.utc).isoformat()
            end_ts = datetime.now(timezone.utc)
            duration_ms = int((end_ts - start_ts).total_seconds() * 1000)
            raise
        except Exception as exc:
            state.status = "failed"
            state.error = f"Build error: {exc}"
            state.end_time = datetime.now(timezone.utc).isoformat()
            end_ts = datetime.now(timezone.utc)
            duration_ms = int((end_ts - start_ts).total_seconds() * 1000)
        finally:
            # Restore original firmware version if we changed it
            if original_version is not None:
                try:
                    self._config.set_firmware_version(original_version)
                except Exception:
                    pass

            # Save log to disk
            log_file = ""
            if state.handle and state.handle.buffer:
                try:
                    log_path = self._history.save_log(
                        state.build_id, state.handle.buffer
                    )
                    log_file = str(log_path.relative_to(_PROJECT_ROOT))
                except Exception:
                    pass

            # Compute duration (handle case where start didn't complete)
            try:
                end_dt = datetime.fromisoformat(state.end_time) if state.end_time else datetime.now(timezone.utc)
                _duration_ms = int((end_dt - start_ts).total_seconds() * 1000)
            except Exception:
                _duration_ms = 0

            # Persist history entry (only for terminal states)
            if state.status in {"success", "failed", "aborted"}:
                try:
                    entry = BuildHistoryEntry(
                        build_id=state.build_id,
                        timestamp=state.timestamp,
                        end_time=state.end_time or datetime.now(timezone.utc).isoformat(),
                        models=state.request.selected_models,
                        status=state.status,
                        firmware_version=state.firmware_version,
                        component=state.request.component,
                        clean=state.request.clean,
                        jobs=state.jobs,
                        duration_ms=_duration_ms,
                        log_file=log_file,
                    )
                    self._history.record(entry)
                except Exception:
                    pass

            # Clear active build reference
            self._active = None

    def _build_command(self, state: _BuildState, settings) -> list[str]:
        """
        Construct the custom_build.py argument list.
        No shell interpolation — all values are discrete list elements.
        """
        cmd: list[str] = [sys.executable, str(_CUSTOM_BUILD)]
        cmd += [state.request.component]
        cmd += state.request.selected_models
        if state.request.clean:
            cmd += ["--clean"]
        if settings.toolchain_path:
            cmd += ["--toolchain", settings.toolchain_path]
        if state.jobs > 0:
            cmd += ["--jobs", str(state.jobs)]
        return cmd

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _sigkill_fallback(self, state: _BuildState) -> None:
        """Send SIGKILL if the process hasn't terminated 5 seconds after SIGTERM."""
        await asyncio.sleep(5)
        if state.handle and not state.handle.is_done:
            try:
                process = state.handle._process
                if process.returncode is None:
                    try:
                        pgid = os.getpgid(process.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, OSError):
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
            except Exception:
                pass
