from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(require_auth)])


@router.get("")
def list_feedback(
    gosb_id: int | None = Query(default=None),
    action: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return repository.list_feedback(
        gosb_id=gosb_id,
        action=action,
        limit=limit,
        offset=offset,
    )
