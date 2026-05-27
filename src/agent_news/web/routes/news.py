from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/news", tags=["news"], dependencies=[Depends(require_auth)])


@router.get("")
def list_news(
    gosb_id: int | None = Query(default=None),
    only_relevant: bool = Query(default=False),
    since_hours: int | None = Query(default=None, ge=1, le=24 * 365),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return repository.list_news(
        gosb_id=gosb_id,
        only_relevant=only_relevant,
        since_hours=since_hours,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/{news_id}")
def get_news(news_id: int):
    item = repository.get_news(news_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News not found")
    return item
