from __future__ import annotations

import os

from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]


load_dotenv()


class Settings:
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    supabase_url: str | None = os.getenv("SUPABASE_URL") or "https://kmmioqdjirmdfvjygjiq.supabase.co/"
    supabase_service_role_key: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "sb_publishable_pma-DnUyDlvdpic192ecRg_MO1XXv-B"
    webhook_url: str | None = os.getenv("WEBHOOK_URL") or "https://webhook.site/29eef80f-717e-4b01-bdb9-62fa65081fb1"


settings = Settings()

