"""API routes for radio model management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from webapp.backend.models import (
    ModelAlreadyExistsError,
    ModelCreate,
    ModelNotFoundError,
    ModelResponse,
    ModelUpdate,
)
from webapp.backend.services.config_service import ConfigService
from webapp.backend.dependencies import get_config_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=dict)
async def list_models(
    config: ConfigService = Depends(get_config_service),
):
    """Return all models and the current firmware version."""
    try:
        full = config.get_full_config()
        models = config.list_models()
        return {
            "firmware_version": full.get("firmware_version", ""),
            "targets": {k: v.model_dump() for k, v in models.items()},
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.post("", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: ModelCreate,
    config: ConfigService = Depends(get_config_service),
):
    """Add a new radio model to the configuration."""
    try:
        return config.add_model(body)
    except ModelAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.get("/{key}", response_model=ModelResponse)
async def get_model(
    key: str,
    config: ConfigService = Depends(get_config_service),
):
    """Retrieve a single model by key."""
    try:
        return config.get_model(key)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{key}", response_model=ModelResponse)
async def update_model(
    key: str,
    body: ModelUpdate,
    config: ConfigService = Depends(get_config_service),
):
    """Apply a partial update to a model."""
    try:
        return config.update_model(key, body)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    key: str,
    config: ConfigService = Depends(get_config_service),
):
    """Remove a model from the configuration."""
    try:
        config.delete_model(key)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
