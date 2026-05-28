from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(require_auth)])


class FeedbackBody(BaseModel):
    action: str  # useful | boring | comment
    comment: str | None = None


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


@router.post("/news/{news_id}")
def submit_news_feedback(
    news_id: int,
    body: FeedbackBody,
    username: str = Depends(require_auth),
):
    user_id = f"web:{username}"
    return repository.save_feedback(
        news_id=news_id,
        user_id=user_id,
        username=username,
        action=body.action,
        comment=body.comment,
    )


@router.get("/news/{news_id}/counts")
def news_feedback_counts(news_id: int):
    return repository.get_feedback_counts(news_id)


@router.post("/insights/{insight_id}")
def submit_insight_feedback(
    insight_id: int,
    body: FeedbackBody,
    username: str = Depends(require_auth),
):
    user_id = f"web:{username}"
    return repository.save_insight_feedback(
        insight_id=insight_id,
        user_id=user_id,
        username=username,
        action=body.action,
        comment=body.comment,
    )


@router.get("/insights/{insight_id}/counts")
def insight_feedback_counts(insight_id: int):
    return repository.get_insight_feedback_counts(insight_id)
