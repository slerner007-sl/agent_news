from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from .. import repository
from ..security import require_auth

router = APIRouter(prefix="/knowledge", tags=["knowledge"], dependencies=[Depends(require_auth)])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


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


@router.post("/upload")
async def upload_knowledge(
    kind: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    username: str = Depends(require_auth),
):
    """Upload a knowledge document (metrics or methodology).

    Either ``text`` or ``file`` must be provided.  For file uploads the
    raw text content is extracted on the server side.
    """
    if kind not in ("metrics", "methodology"):
        raise HTTPException(status_code=400, detail="kind must be 'metrics' or 'methodology'")

    content_text: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    source_type = "text"

    if file is not None:
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 10 МБ)")
        content_text = raw.decode("utf-8", errors="replace")
        file_name = file.filename
        mime_type = file.content_type
        source_type = "file"
    elif text:
        content_text = text.strip()
    else:
        raise HTTPException(status_code=400, detail="Укажите text или загрузите file")

    if not content_text:
        raise HTTPException(status_code=400, detail="Пустой документ")

    source_key = file_name or hashlib.sha256(content_text.encode()).hexdigest()[:16]

    result = repository.save_knowledge_document(
        kind=kind,
        content_text=content_text,
        source_type=source_type,
        sender_id=f"web:{username}",
        username=username,
        file_name=file_name,
        mime_type=mime_type,
        source_key=source_key,
    )
    return result
