from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected_token = settings.admin_api_token.strip()
    if not expected_token:
        return
    if x_admin_token == expected_token:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token required")