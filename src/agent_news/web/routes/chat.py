"""Chat endpoint — sends a message to the OpenClaw agent and returns the response."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..security import require_auth

router = APIRouter(prefix="/chat", tags=["chat"])

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "/home/user1/.npm-global/bin/openclaw")
OPENCLAW_MODEL = os.getenv("OPENCLAW_MODEL", "openai/gpt-5.5")
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TIMEOUT", "240"))
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # src/agent_news/web/routes -> repo root

# Limit concurrent openclaw invocations to avoid overloading the VPS.
_semaphore = asyncio.Semaphore(2)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    duration_seconds: float


def _strip_code_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _extract_response_text(stdout: str) -> str:
    """Extract assistant text from openclaw JSON output."""
    payload = json.loads(stdout)
    meta = payload.get("result", {}).get("meta", {})
    content = meta.get("finalAssistantVisibleText") or meta.get("finalAssistantRawText")
    if not content:
        payloads = payload.get("result", {}).get("payloads", [])
        if payloads:
            content = payloads[0].get("text")
    if not content:
        raise ValueError("openclaw returned no assistant text")
    return _strip_code_fences(content)


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, username: str = Depends(require_auth)):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    async with _semaphore:
        t0 = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                OPENCLAW_BIN,
                "agent",
                "--agent", "main",
                "--model", OPENCLAW_MODEL,
                "--message", body.message,
                "--timeout", str(OPENCLAW_TIMEOUT),
                "--json",
                cwd=str(PROJECT_ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=OPENCLAW_TIMEOUT + 30,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Таймаут ответа от агента")
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail=f"OpenClaw binary not found at {OPENCLAW_BIN}",
            )

        duration = time.monotonic() - t0
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            detail = (stderr or stdout).strip()[:500] or f"openclaw exited with {proc.returncode}"
            raise HTTPException(status_code=502, detail=detail)

        try:
            text = _extract_response_text(stdout)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Cannot parse agent response: {exc}")

    return ChatResponse(response=text, duration_seconds=round(duration, 2))
