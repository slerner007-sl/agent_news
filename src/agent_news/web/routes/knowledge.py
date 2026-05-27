from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(require_auth)])


@router.get("")
def list_knowledge(
    kind: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return repository.list_knowledge(kind=kind, limit=limit, offset=offset)


@router.get("/{doc_id}")
def get_knowledge(doc_id: int):
    item = repository.get_knowledge(doc_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return item
