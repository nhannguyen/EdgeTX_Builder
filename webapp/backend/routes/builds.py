"""API routes for build management and SSE log streaming."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from webapp.backend.models import (
    BuildAlreadyRunningError,
    BuildNotFoundError,
    BuildNotRunningError,
    BuildRequest,
    BuildStatusResponse,
    ModelNotFoundError,
)
from webapp.backend.services.build_service import BuildService
from webapp.backend.dependencies import get_build_service

router = APIRouter(prefix="/builds", tags=["builds"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def start_build(
    body: BuildRequest,
    build_service: BuildService = Depends(get_build_service),
):
    """Trigger a new firmware build."""
    try:
        result = await build_service.start_build(body)
        return result
    except BuildAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.get("/active")
async def get_active_build(
    build_service: BuildService = Depends(get_build_service),
):
    """Return the currently active build, or 204 if none."""
    result = build_service.get_active_build()
    if result is None:
        from fastapi.responses import Response
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return result


@router.get("/{build_id}", response_model=BuildStatusResponse)
async def get_build(
    build_id: str,
    build_service: BuildService = Depends(get_build_service),
):
    """Get status of a specific build by ID."""
    try:
        return build_service.get_build(build_id)
    except BuildNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{build_id}")
async def abort_build(
    build_id: str,
    build_service: BuildService = Depends(get_build_service),
):
    """Abort a running build."""
    try:
        await build_service.abort_build(build_id)
        return {"message": "Build abort requested"}
    except BuildNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BuildNotRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/{build_id}/logs")
async def stream_build_logs(
    build_id: str,
    request: Request,
    build_service: BuildService = Depends(get_build_service),
):
    """
    SSE endpoint for real-time build log streaming.

    Supports reconnect via Last-Event-ID header (replays from that line index + 1).
    """
    # Parse Last-Event-ID for reconnect support
    last_event_id = request.headers.get("last-event-id", "")
    from_index = 0
    if last_event_id:
        try:
            from_index = int(last_event_id) + 1
        except ValueError:
            from_index = 0

    # Validate that the build exists BEFORE creating a StreamingResponse.
    # Once the StreamingResponse is returned (headers sent), exceptions from
    # the async generator can no longer be translated to HTTP error responses.
    try:
        build_service.validate_build_exists(build_id)
    except BuildNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    log_generator = build_service.stream_logs_from(build_id, from_index=from_index)

    return StreamingResponse(
        log_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
