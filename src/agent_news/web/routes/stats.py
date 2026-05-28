from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/stats", tags=["stats"], dependencies=[Depends(require_auth)])


@router.get("/summary")
def summary(since_hours: int = Query(default=168, ge=1, le=24 * 365)):
    return repository.stats_summary(since_hours=since_hours)
