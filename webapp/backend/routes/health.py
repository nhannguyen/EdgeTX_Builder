"""API route for system health check."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from webapp.backend.models import HealthReport
from webapp.backend.services.health_service import HealthService
from webapp.backend.dependencies import get_health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthReport)
async def health_check(
    health_service: HealthService = Depends(get_health_service),
):
    """Run system health checks and return a report."""
    return health_service.check()
