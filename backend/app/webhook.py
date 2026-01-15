from __future__ import annotations

from typing import Any

import httpx

from .settings import settings


async def send_webhook(payload: dict[str, Any]) -> tuple[bool, str | None]:
    if not settings.webhook_url:
        return False, "WEBHOOK_URL not configured"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.webhook_url, json=payload)
            resp.raise_for_status()
        return True, None
    except Exception as e:  # keep minimal; caller stores failure reason if needed
        return False, str(e)

