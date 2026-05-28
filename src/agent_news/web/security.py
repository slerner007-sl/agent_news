"""Optional HTTP Basic auth for the dashboard API.

If ``AGENT_NEWS_WEB_USER`` and ``AGENT_NEWS_WEB_PASSWORD`` are set, every
non-health endpoint requires Basic auth. If they are unset, the API is
open (intended for use behind nginx with its own auth, or for local
development).
"""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def _expected() -> tuple[str, str] | None:
    user = os.getenv("AGENT_NEWS_WEB_USER", "").strip()
    password = os.getenv("AGENT_NEWS_WEB_PASSWORD", "").strip()
    if user and password:
        return user, password
    return None


def require_auth(
    credentials: HTTPBasicCredentials | None = Depends(_security),
) -> str:
    expected = _expected()
    if expected is None:
        return "anonymous"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, expected[0])
    pwd_ok = secrets.compare_digest(credentials.password, expected[1])
    if not (user_ok and pwd_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
