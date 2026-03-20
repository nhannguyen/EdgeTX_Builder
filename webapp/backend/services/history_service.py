"""
HistoryService — read/write build history to webapp/data/build_history.json.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from webapp.backend.models import BuildHistoryEntry, HistoryNotFoundError

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_HISTORY_FILE = _DATA_DIR / "build_history.json"
_LOGS_DIR = _DATA_DIR / "build_logs"


class HistoryService:
    """Manages build_history.json persistence and log file storage."""

    def __init__(
        self,
        history_path: Path = _HISTORY_FILE,
        logs_dir: Path = _LOGS_DIR,
    ) -> None:
        self._path = history_path
        self._logs_dir = logs_dir
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._logs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                return []
            return data
        except (json.JSONDecodeError, OSError):
            return []

    def _save_all(self, entries: list[dict]) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(entries, fh, indent=2, default=str)
            os.replace(tmp, self._path)
        except OSError:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def record(self, entry: BuildHistoryEntry) -> None:
        """Prepend a new build history entry (newest first)."""
        entries = self._load_all()
        entries.insert(0, entry.model_dump())
        self._save_all(entries)

    def save_log(self, build_id: str, lines: list[str]) -> Path:
        """Write build log lines to a file. Returns the path."""
        log_path = self._logs_dir / f"{build_id}.log"
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return log_path

    def get_log_path(self, build_id: str) -> Optional[Path]:
        """Return the log file path if it exists."""
        log_path = self._logs_dir / f"{build_id}.log"
        return log_path if log_path.exists() else None

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        model: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> tuple[list[BuildHistoryEntry], int]:
        """
        Return a paginated list of history entries with optional filters.
        Returns (items, total_count).
        """
        entries = self._load_all()

        # Apply filters
        filtered: list[dict] = []
        for e in entries:
            if model and model not in e.get("models", []):
                continue
            if status and e.get("status") != status:
                continue
            if date_from:
                try:
                    if e.get("timestamp", "") < date_from:
                        continue
                except TypeError:
                    pass
            if date_to:
                try:
                    if e.get("timestamp", "") > date_to:
                        continue
                except TypeError:
                    pass
            filtered.append(e)

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        result: list[BuildHistoryEntry] = []
        for e in page_items:
            try:
                result.append(BuildHistoryEntry(**e))
            except (TypeError, ValueError):
                pass
        return result, total

    def get(self, build_id: str) -> BuildHistoryEntry:
        """Fetch a single history entry. Raises HistoryNotFoundError if absent."""
        entries = self._load_all()
        for e in entries:
            if e.get("build_id") == build_id:
                try:
                    return BuildHistoryEntry(**e)
                except (TypeError, ValueError) as exc:
                    raise HistoryNotFoundError(
                        f"Build history entry '{build_id}' is corrupted."
                    ) from exc
        raise HistoryNotFoundError(f"Build history not found: '{build_id}'")

    def delete(self, build_id: str) -> None:
        """Remove a single history entry. Raises HistoryNotFoundError if absent."""
        entries = self._load_all()
        new_entries = [e for e in entries if e.get("build_id") != build_id]
        if len(new_entries) == len(entries):
            raise HistoryNotFoundError(f"Build history not found: '{build_id}'")
        self._save_all(new_entries)
        # Remove log file if present
        log_path = self._logs_dir / f"{build_id}.log"
        log_path.unlink(missing_ok=True)

    def clear_all(self) -> None:
        """Remove all history entries and their log files."""
        self._save_all([])
        for log_file in self._logs_dir.glob("*.log"):
            log_file.unlink(missing_ok=True)

    def apply_retention(self, retention_days: int) -> None:
        """Delete entries older than retention_days. 0 means keep forever."""
        if retention_days <= 0:
            return
        entries = self._load_all()
        cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
        keep: list[dict] = []
        for e in entries:
            ts_str = e.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str).timestamp()
                if ts >= cutoff:
                    keep.append(e)
                else:
                    log_path = self._logs_dir / f"{e.get('build_id', '')}.log"
                    log_path.unlink(missing_ok=True)
            except (ValueError, OSError):
                keep.append(e)
        self._save_all(keep)
