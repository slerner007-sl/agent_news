from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/gosbs", tags=["gosbs"], dependencies=[Depends(require_auth)])


@router.get("")
def list_gosbs(active_only: bool = Query(default=False)):
    return {"items": repository.list_gosbs(active_only=active_only)}


@router.get("/{gosb_id}")
def get_gosb(gosb_id: int):
    item = repository.get_gosb(gosb_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ГОСБ не найден")
    return item
