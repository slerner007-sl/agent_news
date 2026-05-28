from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/insights", tags=["insights"], dependencies=[Depends(require_auth)])


@router.get("")
def list_insights(
    gosb_id: int | None = Query(default=None),
    priority: str | None = Query(default=None, pattern="^(high|medium|low)$"),
    insight_type: str | None = Query(default=None, max_length=60),
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return repository.list_insights(
        gosb_id=gosb_id,
        priority=priority,
        insight_type=insight_type,
        status=status,
        limit=limit,
        offset=offset,
    )
