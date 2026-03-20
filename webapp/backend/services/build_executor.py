"""
BuildExecutor — asyncio subprocess wrapper around custom_build.py.

Never imports custom_build.py directly. Spawns it as a subprocess using
asyncio.create_subprocess_exec (no shell=True) and streams stdout/stderr
line by line through an async generator.
"""
from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path
from typing import AsyncGenerator, Optional


class BuildHandle:
    """
    Wraps a running asyncio subprocess.

    Provides:
    - An async generator `lines()` that yields log lines as they arrive.
    - Access to the accumulated log buffer for replay/reconnect.
    - `terminate()` for graceful shutdown with SIGKILL fallback.
    - `wait()` for the final exit code.
    """

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process
        self._buffer: list[str] = []
        self._done = asyncio.Event()
        self._exit_code: Optional[int] = None
        # Condition used to wake up consumers waiting for new lines
        self._new_line_event = asyncio.Event()

    @property
    def buffer(self) -> list[str]:
        """Read-only view of the accumulated log lines."""
        return self._buffer

    @property
    def exit_code(self) -> Optional[int]:
        return self._exit_code

    @property
    def is_done(self) -> bool:
        return self._done.is_set()

    async def _read_output(self) -> None:
        """
        Internal coroutine: reads lines from the process stdout and appends to
        the buffer. Signals `_done` when the stream is exhausted.
        """
        assert self._process.stdout is not None
        try:
            while True:
                line_bytes = await self._process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
                self._buffer.append(line)
                self._new_line_event.set()
                self._new_line_event.clear()
        finally:
            self._exit_code = await self._process.wait()
            self._done.set()
            # Wake any waiting consumers so they can detect completion
            self._new_line_event.set()

    async def lines(self, from_index: int = 0) -> AsyncGenerator[str, None]:
        """
        Async generator that yields log lines starting from `from_index`.

        Supports reconnect: pass `from_index` equal to the last received
        line index + 1 to replay from that position.

        Yields lines as they arrive, then exits when the process completes
        and all buffered lines have been yielded.
        """
        current = from_index
        while True:
            # Yield any buffered lines we haven't sent yet
            while current < len(self._buffer):
                yield self._buffer[current]
                current += 1

            # If the process is done and we have sent all lines, we're done
            if self._done.is_set() and current >= len(self._buffer):
                return

            # Wait for more lines or process completion
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._wait_for_new_line()), timeout=1.0
                )
            except asyncio.TimeoutError:
                pass  # Poll again on timeout

    async def _wait_for_new_line(self) -> None:
        """Wait until a new line is available or the process finishes."""
        if not self._done.is_set() and len(self._buffer) == 0:
            await self._new_line_event.wait()
        elif self._done.is_set():
            return
        else:
            await self._new_line_event.wait()

    async def wait(self) -> int:
        """Wait for the process to finish and return the exit code."""
        await self._done.wait()
        return self._exit_code if self._exit_code is not None else -1

    def terminate(self) -> None:
        """Send SIGTERM to the process group. BuildService handles the SIGKILL fallback."""
        if self._process.returncode is None:
            try:
                # Try to kill the entire process group
                pgid = os.getpgid(self._process.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    self._process.terminate()
                except ProcessLookupError:
                    pass


class BuildExecutor:
    """
    Spawns custom_build.py as an async subprocess and returns a BuildHandle.
    """

    @staticmethod
    async def execute(cmd: list[str], cwd: Path) -> BuildHandle:
        """
        Launch the command as an async subprocess.

        - Uses asyncio.create_subprocess_exec (no shell=True).
        - Merges stderr into stdout via subprocess.STDOUT.
        - Returns a BuildHandle immediately; reading starts in a background task.
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(cwd),
            # Create a new process group so we can kill descendants
            start_new_session=True,
        )
        handle = BuildHandle(process)
        # Start the background reader task
        asyncio.create_task(handle._read_output())
        return handle
