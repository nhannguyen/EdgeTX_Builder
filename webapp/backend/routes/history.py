"""API routes for build history."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from webapp.backend.models import BuildHistoryEntry, HistoryListResponse, HistoryNotFoundError
from webapp.backend.services.history_service import HistoryService
from webapp.backend.dependencies import get_history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
async def list_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    model: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    history: HistoryService = Depends(get_history_service),
):
    """Return paginated build history with optional filters."""
    items, total = history.list(
        page=page,
        page_size=page_size,
        model=model,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
    )
    return HistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{build_id}", response_model=BuildHistoryEntry)
async def get_history_entry(
    build_id: str,
    history: HistoryService = Depends(get_history_service),
):
    """Get a single history entry with its full log content."""
    try:
        return history.get(build_id)
    except HistoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{build_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    build_id: str,
    history: HistoryService = Depends(get_history_service),
):
    """Delete a single history entry and its log file."""
    try:
        history.delete(build_id)
    except HistoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_history(
    history: HistoryService = Depends(get_history_service),
):
    """Delete all build history entries and log files."""
    history.clear_all()
    return {"message": "History cleared"}


@router.get("/{build_id}/log")
async def get_build_log(
    build_id: str,
    history: HistoryService = Depends(get_history_service),
):
    """Return the raw build log content for a history entry."""
    try:
        history.get(build_id)  # Verify the entry exists
    except HistoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    log_path = history.get_log_path(build_id)
    if log_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log file not found for build '{build_id}'",
        )
    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="build_{build_id}.log"',
        },
    )
