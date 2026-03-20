"""API routes for application settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from webapp.backend.models import AppSettings, AppSettingsUpdate
from webapp.backend.services.settings_service import SettingsService
from webapp.backend.dependencies import get_settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
async def get_settings(
    settings_service: SettingsService = Depends(get_settings_service),
):
    """Return current application settings."""
    return settings_service.get()


@router.patch("", response_model=AppSettings)
async def update_settings(
    body: AppSettingsUpdate,
    settings_service: SettingsService = Depends(get_settings_service),
):
    """Apply a partial update to application settings."""
    # Validate toolchain path if provided
    if body.toolchain_path is not None:
        if body.toolchain_path and not settings_service.validate_toolchain(
            body.toolchain_path
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Toolchain path not found or missing arm-none-eabi-gcc",
            )
    try:
        return settings_service.update(body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
