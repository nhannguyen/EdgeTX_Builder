"""API routes for configuration export/import."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, Response

from webapp.backend.models import ConfigImportResponse, InvalidConfigError
from webapp.backend.services.config_service import ConfigService
from webapp.backend.dependencies import get_config_service

router = APIRouter(prefix="/config", tags=["config"])

# Maximum size accepted for an uploaded targets.json file (1 MiB).
# A legitimate targets.json is measured in kilobytes; refusing oversized
# uploads prevents a trivial memory-exhaustion DoS against the local server.
_MAX_UPLOAD_BYTES = 1 * 1024 * 1024  # 1 MiB


@router.get("")
async def get_config(
    config: ConfigService = Depends(get_config_service),
):
    """Return the full targets.json structure."""
    try:
        return config.get_full_config()
    except InvalidConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.get("/export")
async def export_config(
    config: ConfigService = Depends(get_config_service),
):
    """Download targets.json as a file."""
    try:
        data = config.get_full_config()
        content = json.dumps(data, indent=4)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="targets.json"',
            },
        )
    except InvalidConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.post("/import", response_model=ConfigImportResponse)
async def import_config(
    file: UploadFile = File(...),
    config: ConfigService = Depends(get_config_service),
):
    """Replace the current configuration with an uploaded targets.json."""
    # Read with an explicit size cap to prevent memory-exhaustion DoS.
    raw = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds the maximum allowed size of {_MAX_UPLOAD_BYTES // 1024} KiB.",
        )

    try:
        data: Any = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format",
        )

    try:
        model_count = config.replace_config(data)
    except InvalidConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )

    return ConfigImportResponse(
        message="Configuration imported successfully",
        model_count=model_count,
    )
