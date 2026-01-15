from __future__ import annotations

from typing import Any

try:
    # supabase-py
    from supabase import Client, create_client  # pyright: ignore[reportMissingImports]
except Exception as _e:  # pragma: no cover
    # Fallback for type checkers / alternate layouts
    from supabase._sync.client import Client  # type: ignore
    from supabase._sync.client import create_client  # type: ignore

from .settings import settings


class SupabaseRepo:
    def __init__(self) -> None:
        self._client: Client | None = None

    def enabled(self) -> bool:
        return bool(settings.supabase_url and settings.supabase_service_role_key)

    def client(self) -> Client:
        if not self.enabled():
            raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        if self._client is None:
            # enabled() guarantees these are set
            self._client = create_client(settings.supabase_url or "", settings.supabase_service_role_key or "")
        return self._client

    def upsert_session(
        self,
        *,
        session_id: str,
        agent_type: str,
        full_name: str | None,
        user_data: dict[str, Any],
        ai_output: dict[str, Any],
        webhook_sent: bool,
    ) -> None:
        if not self.enabled():
            return

        try:
            payload: dict[str, Any] = {
                "session_id": session_id,
                "agent_type": agent_type,
                "full_name": full_name,
                "user_data": user_data,
                "ai_output": ai_output,
                "webhook_sent": webhook_sent,
            }
            # First try to update existing record, then insert if not found
            # Note: session_id should have a UNIQUE constraint in the database
            try:
                # Try to update first
                result = self.client().table("career_sessions").update(payload).eq("session_id", session_id).execute()
                if not result.data:
                    # If no rows updated, insert new record
                    self.client().table("career_sessions").insert(payload).execute()
            except Exception:
                # Fallback: just insert (will fail if duplicate, but that's ok)
                self.client().table("career_sessions").insert(payload).execute()
        except Exception as e:
            # Log but don't crash the request if Supabase fails
            print(f"Supabase upsert failed (non-fatal): {e}")

