"""API routes for firmware artifact listing and download."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from webapp.backend.models import ArtifactListResponse, ArtifactNotFoundError, InvalidPathError
from webapp.backend.services.artifact_service import ArtifactService
from webapp.backend.dependencies import get_artifact_service

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{model_key}", response_model=ArtifactListResponse)
async def list_artifacts(
    model_key: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
):
    """List firmware artifacts for a given model (empty list if none found)."""
    return artifact_service.list_artifacts(model_key)


@router.get("/{model_key}/{filename}")
async def download_artifact(
    model_key: str,
    filename: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
):
    """Download a specific firmware artifact file."""
    try:
        path = artifact_service.get_artifact_path(model_key, filename)
    except InvalidPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    download_name = f"{model_key}_{filename}"
    return FileResponse(
        path=str(path),
        filename=download_name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
