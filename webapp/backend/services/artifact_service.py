"""
ArtifactService — lists and serves firmware build artifacts from dist/.

Path traversal is prevented by resolving paths and asserting they remain
within the dist/ directory before returning them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from webapp.backend.models import (
    ArtifactInfo,
    ArtifactListResponse,
    ArtifactNotFoundError,
    InvalidPathError,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DIST_DIR = _PROJECT_ROOT / "dist"


class ArtifactService:
    """Reads firmware artifacts from the dist/ directory."""

    def __init__(self, dist_dir: Path = _DIST_DIR) -> None:
        self._dist = dist_dir.resolve()

    def list_artifacts(self, model_key: str) -> ArtifactListResponse:
        """List firmware files for a given model. Returns empty list if none found."""
        model_dir = self._dist / model_key
        files: list[ArtifactInfo] = []
        if model_dir.is_dir():
            for f in sorted(model_dir.iterdir()):
                if f.is_file() and f.suffix in {".bin", ".uf2", ".hex"}:
                    try:
                        stat = f.stat()
                        mtime = datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat()
                        files.append(
                            ArtifactInfo(
                                filename=f.name,
                                size_bytes=stat.st_size,
                                modified=mtime,
                            )
                        )
                    except OSError:
                        pass
        return ArtifactListResponse(model=model_key, files=files)

    def list_all_artifacts(self) -> dict[str, ArtifactListResponse]:
        """Return a mapping of model key to artifact list for all models in dist/."""
        result: dict[str, ArtifactListResponse] = {}
        if not self._dist.is_dir():
            return result
        for entry in self._dist.iterdir():
            if entry.is_dir():
                result[entry.name] = self.list_artifacts(entry.name)
        return result

    def get_artifact_path(self, model_key: str, filename: str) -> Path:
        """
        Resolve and validate the path to a specific artifact file.

        Raises:
            InvalidPathError: if the resolved path escapes dist/.
            ArtifactNotFoundError: if the file does not exist.
        """
        # Build the candidate path and resolve symlinks / .. sequences
        candidate = (self._dist / model_key / filename).resolve()

        # Path traversal check: candidate must be inside _dist
        try:
            candidate.relative_to(self._dist)
        except ValueError as exc:
            raise InvalidPathError(
                f"Invalid path: access outside dist/ directory is not permitted."
            ) from exc

        if not candidate.is_file():
            raise ArtifactNotFoundError(
                f"Firmware file not found: '{model_key}/{filename}'"
            )
        return candidate
